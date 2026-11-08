"""Actual clean Compose build, proxy/session/routing/persistence verification.

Run with .venv Python and Docker Desktop (Linux containers) / Compose >=2.30.
Copies only publication-audited source files. Never reads developer credentials
into containers. Only a labelled simulation is captured; no Sandbox API call.
Containers are stopped at the end unless --keep-running; volumes are preserved.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,shutil,socket,subprocess,sys,time
from uuid import uuid4
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_publication import audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keep-running',action='store_true')
    args=parser.parse_args()
    assert audit(ROOT)['passed'],'Publication audit must pass before copying files.'
    with socket.socket() as port:
        assert port.connect_ex(('127.0.0.1',5173))!=0,'Port 5173 is in use; stop that local service before verification.'
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    target=ROOT/'.verification'/f'docker-clean-{stamp}';target.mkdir(parents=True)
    project=f'radar-verify-{stamp}';report={'project':project,'checkout':str(target.relative_to(ROOT)),'checks':{},'sandbox_api_calls':0}
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    for name in sorted(set(filter(None,names))):
        src=ROOT/name
        if src.is_file():
            dst=target/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    for name in ('.env','.env.docker.local','.venv','data','frontend/node_modules','frontend/dist','.git','demo-video'):
        assert not (target/name).exists(),f'Private/dependency artifact copied: {name}'
    report['checks']['clean_source_only']=True
    base=['docker','compose','-p',project]
    def run(*cmd,capture=False,input=None):
        return subprocess.run(list(cmd),cwd=target,check=True,text=True,input=input,stdout=subprocess.PIPE if capture else None)
    def compose(*cmd,capture=False):return run(*base,*cmd,capture=capture)
    def wait_health():
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            try:
                if httpx.get('http://localhost:5173/api/health',timeout=4,trust_env=False).status_code==200:return
            except httpx.HTTPError:pass
            time.sleep(1)
        raise RuntimeError('Frontend proxy health did not recover.')
    def require(response,status=200):
        assert response.status_code==status,f'Unexpected HTTP status {response.status_code} for {response.request.url.path}'
        return response.json()
    def containers():
        rows=compose('ps','--format','json',capture=True).stdout.strip()
        # Compose v2 emits one JSON object per line.
        return [json.loads(line) for line in rows.splitlines() if line.strip()]
    try:
        compose('config','--quiet');report['checks']['compose_config']=True
        compose('up','--build','-d','--wait','--wait-timeout','180')
        services=containers();assert len(services)==2 and all(c['Health']=='healthy' for c in services)
        report['checks']['build_and_healthy_startup']=True
        # Full resolved config is parsed in memory, never printed or saved.
        config=json.loads(compose('config','--format','json',capture=True).stdout)
        assert 'ports' not in config['services']['backend']
        assert config['services']['frontend']['ports'][0]['host_ip']=='127.0.0.1'
        assert config['services']['backend']['environment']['DATABASE_URL']=='sqlite:////app/data/global_radar.db'
        report['checks']['loopback_frontend_only_and_named_database']=True
        compose('exec','-T','backend','python','-c',"import os,pathlib; assert all(not os.getenv(k) for k in ('CLIENT_ID','CLIENT_SECRET','OPENAI_API_KEY','CHANNEL3_API_KEY')); assert not pathlib.Path('/app/.env').exists(); print('No credentials or developer env in backend.')")
        compose('exec','-T','frontend','sh','-c','test ! -e /usr/share/nginx/html/.env && test ! -d /usr/share/nginx/html/node_modules')
        report['checks']['runtime_images_no_developer_env_or_keys']=True
        with httpx.Client(base_url='http://localhost:5173',headers={'X-Commerce-Radar':'1','Origin':'http://localhost:5173'},timeout=120,trust_env=False) as c:
            assert c.get('/').status_code==200
            assert require(c.get('/api/health'))['status']=='ok'
            status=require(c.get('/api/demo/status'));assert not status['sandbox_configured'] and not status['currencies_sandbox_verified']
            assert c.get('/world-110m.json').status_code==200
            session=c.post('/api/demo/session',json={'persona':'coffee'});require(session)
            assert 'httponly' in session.headers['set-cookie'].lower() and 'samesite=lax' in session.headers['set-cookie'].lower()
            assert require(c.get('/api/products/status'))['status']=='unconfigured'
            assert require(c.get('/api/profile'))['home_currency']=='USD'
            strategy=require(c.get('/api/strategy/initial'));assert strategy['display_name']
            products=require(c.post('/api/products/automatic',json={}));assert products['mode']=='Demo Products'
            offers=require(c.get('/api/discovery?fx_mode=demo'))['offers'];assert offers
            assert require(c.get('/api/fx/opportunities?mode=historical'))['mode']=='historical'
            assert c.get('/api/nonexistent').status_code==404
            assert c.get('/assets/nonexistent.js').status_code==404
            denied=c.post('/api/demo/session',json={'persona':'coffee'},headers={'Origin':'https://untrusted.example'});assert denied.status_code==403
            with httpx.Client(base_url='http://localhost:5173',trust_env=False) as unmarked:
                assert unmarked.post('/api/demo/session',json={'persona':'coffee'}).status_code==403
            report['checks']['proxy_session_usd_persona_strategy_demo_map_history']=True
            report['checks']['historical_fixture_and_origin_marker_guards']=True
            # No Sandbox credentials or network payment endpoints involved.
            item=next(p for p in offers if p['checkout_available'])
            order=require(c.post('/api/checkout/orders',json={'offer_id':item['id'],'quantity':1,'mode':'simulation','currency':'USD','idempotency_key':str(uuid4())}))
            assert order['mode']=='simulation' and not order['paypal_order_id']
            path=f"/payment/{order['id']}?approved=1"
            assert c.get(path).status_code==200 and c.get(path).text==c.get('/').text
            for _ in range(2):assert require(c.post(f"/api/checkout/orders/{order['id']}/capture",json={}))['status']=='COMPLETED'
            history=require(c.get('/api/history'));assert len([p for p in history if p['source']=='simulation'])==1
            assert not any(p['source']=='sandbox' for p in history)
            require(c.post('/api/profile',json={'interests':['Coffee'],'budget_usd':12345}))
            report['simulation_order_path']=f"/payment/{order['id']}"
            report['checks']['direct_payment_spa_and_simulation_idempotency']=True
            compose('restart','backend');wait_health()
            assert c.get('/api/profile').status_code==401
            require(c.post('/api/demo/session',json={'persona':'coffee'}))
            assert require(c.get('/api/profile'))['budget_usd']==12345
            assert require(c.get(f"/api/checkout/orders/{order['id']}"))['status']=='COMPLETED'
            report['checks']['restart_persistence_and_session_renewal']=True
            # Status is key presence, NOT proof of authentication. Dummy values only.
            local=target/'.env.docker.local'
            local.write_text('CLIENT_ID=docker-fixture-not-real\nCLIENT_SECRET=literal-$value#not-real\n',encoding='utf-8')
            compose('up','-d','--force-recreate','--wait','backend');wait_health()
            assert require(c.get('/api/demo/status'))['sandbox_configured'] is True
            require(c.post('/api/demo/session',json={'persona':'coffee'}))
            assert not require(c.get('/api/products/status'))['configured']
            literal=compose('exec','-T','backend','python','-c',"import os; assert os.environ['CLIENT_SECRET']=='literal-$value#not-real'; print('Raw optional env values preserved; no authentication request.')",capture=True).stdout
            assert 'preserved' in literal
            report['checks']['optional_paypal_only_status_and_raw_env']=True
            local.unlink() # Only the fixture this script created inside its own clean checkout.
            compose('up','-d','--force-recreate','--wait','backend');wait_health()
            assert not require(c.get('/api/demo/status'))['sandbox_configured']
        # Test the actual default-deny Docker context with COPY ., not .gitignore.
        sentinels=['.env','.env.docker.local','data/private.db','frontend/node_modules/local.js','frontend/dist/local.js','.git/private-marker','.venv/private-marker','backend/__pycache__/local.pyc','demo-video/private.png','.verification/private.json','.paypal-order.json','local.zip']
        for name in sentinels:
            fixture=target/name;assert not fixture.exists();fixture.parent.mkdir(parents=True,exist_ok=True)
            fixture.write_text('PRIVATE_CONTEXT_SENTINEL=synthetic-not-a-credential\n',encoding='utf-8')
        exported=target/'.verification/context-export'
        run('docker','build','--file','-','--output',f'type=local,dest={exported}',str(target),input='FROM scratch\nCOPY . /context/\n')
        context_files=[p.relative_to(exported/'context').as_posix() for p in (exported/'context').rglob('*') if p.is_file()]
        assert 'backend/main.py' in context_files and 'frontend/package-lock.json' in context_files
        forbidden={'.env','.env.docker.local','.git','.venv','data','node_modules','dist','__pycache__','.verification','demo-video','.paypal-order.json'}
        assert not any(forbidden.intersection(Path(n).parts) or n.endswith(('.db','.zip','.log')) for n in context_files)
        assert not set(sentinels).intersection(context_files)
        for name in sentinels:
            fixture=target/name;fixture.unlink()
            parent=fixture.parent
            while parent!=target:
                try:parent.rmdir() # Empty fixture directories only; no recursive deletion.
                except OSError:break
                parent=parent.parent
        report['checks']['actual_docker_context_export']=True;report['context_file_count']=len(context_files)
        report['passed']=True
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        output=ROOT/'.verification/docker-judge/result.json';output.parent.mkdir(exist_ok=True,parents=True)
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        if not args.keep_running or not report.get('passed'):compose('down') # Never --volumes; preserve isolated test state.
        print(json.dumps(report,indent=2))


if __name__=='__main__':main()
