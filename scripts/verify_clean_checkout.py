"""Verify documented installs and first startup without developer .env/data/node_modules.

Run with .venv Python. A temporary checkout is kept under .verification for inspection.
No credentials or payment records are copied. Network is used only by package installers.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
from datetime import datetime

root=Path(__file__).resolve().parent.parent
target=root/'.verification'/('clean-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
target.mkdir(parents=True)
for name in ['backend','frontend','tests','scripts']:
    shutil.copytree(root/name,target/name,ignore=shutil.ignore_patterns('node_modules','dist','__pycache__','*.tsbuildinfo'))
for name in ['requirements.txt','requirements-lock.txt','.env.example','README.md']:
    shutil.copy2(root/name,target/name)
env=os.environ.copy()
for key in ['OPENAI_API_KEY','CLIENT_ID','CLIENT_SECRET','CHANNEL3_API_KEY','DATABASE_URL']:
    env.pop(key,None)
env['ANALYSIS_AUTORUN']='false';env['DEMO_MODE']='true'
def run(args):
    subprocess.run(args,cwd=target,env=env,check=True)
run([sys.executable,'-m','venv',str(target/'.venv')])
python=str(target/'.venv'/'Scripts'/'python.exe' if os.name=='nt' else target/'.venv'/'bin'/'python')
run([python,'-m','pip','install','--disable-pip-version-check','-r','requirements-lock.txt'])
npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
run([npm,'--prefix','frontend','ci','--no-audit','--no-fund'])
run([npm,'--prefix','frontend','run','build'])
smoke="""
from fastapi.testclient import TestClient
from backend.main import app
from backend import fx
# Dependency installs use the network; first-start verification is deterministic
# and must also pass without Frankfurter or product-service connectivity.
fx.provider.fetch=lambda *args: []
with TestClient(app) as c:
 c.headers['X-Commerce-Radar']='1'
 assert c.get('/api/health').status_code==200
 assert c.post('/api/demo/session',json={'persona':'coffee'}).status_code==200
 d=c.get('/api/discovery?fx_mode=demo').json()
 assert d['profile']['home_currency']=='USD' and len(d['countries'])==10
 assert d['profile']['search_plan']['queries']
 assert c.get('/api/demo/status').json()['currencies_sandbox_verified']==[]
 assert c.get('/api/products/plan').status_code==200
 assert c.post('/api/products/automatic',json={}).json()['mode']=='Demo Products'
 assert c.get('/api/products/status').json()['status']=='unconfigured'
 assert c.get('/api/fx/opportunities').json()['favorable_currencies']==[]
 assert c.get('/api/fx/opportunities?mode=historical').json()['mode']=='historical'
print('Clean first startup: health, session, seeded USD discovery, search plan and empty payment verification passed.')
"""
run([python,'-c',smoke])
print('Clean install verification passed:',target.relative_to(root))
