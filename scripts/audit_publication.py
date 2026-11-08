"""Audit Git-visible files without initializing/changing this workspace's Git index.

Uses an ignored temporary Git index/worktree view to evaluate actual .gitignore rules.
Never prints credentials, modifies .env, commits, uploads or deletes source files.
"""
from pathlib import Path
import json,re,subprocess,sys,tempfile
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]

def audit(root=ROOT):
    work=root/'.verification';work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='publish-audit-',dir=work) as temporary:
        repo=Path(temporary)
        subprocess.run(['git','init','--quiet',str(repo)],check=True,capture_output=True)
        command=['git','--git-dir',str(repo/'.git'),'--work-tree',str(root)]
        raw=subprocess.run(command+['ls-files','--others','--exclude-standard','-z'],capture_output=True,check=True).stdout
        candidates=[name.decode('utf-8') for name in raw.split(b'\0') if name]
        examples=['.env','.env.docker.local','docker/secrets/client-secret.txt','test/.env','frontend/node_modules/example.js','data/global_radar.db','copy.db','backend.zip','.verification/result.json','.migration-backups/source.zip','frontend/dist/index.html','backend/__pycache__/main.pyc','test/.paypal-order.json','snapshot.sqlite3-wal','.cache/result.json','demo-video/private-capture.png']
        checked=subprocess.run(command+['check-ignore','-z','--stdin'],input=('\0'.join(examples)+'\0').encode(),capture_output=True)
        ignored={name.decode() for name in checked.stdout.split(b'\0') if name}
    values=dotenv_values(root/'.env') if (root/'.env').exists() else {}
    secrets=[v for k,v in values.items() if v and len(v)>=8 and any(t in k.upper() for t in ('SECRET','PASSWORD','EMAIL','CLIENT_ID','API_KEY'))]
    suspicious=[];forbidden=[]
    # Ignore rules do not protect already tracked files. Include the real index
    # when present, without changing it; never rely only on .gitignore.
    tracked=[]
    if (root/'.git').exists():
        raw=subprocess.run(['git','-C',str(root),'ls-files','-z'],capture_output=True,check=True).stdout
        tracked=[name.decode('utf-8') for name in raw.split(b'\0') if name]
    for name in sorted(set(candidates+tracked)):
        p=root/name
        if not p.is_file():continue
        if (any(part in ('node_modules','data','.venv','__pycache__','.verification','.migration-backups','.pytest_cache','.cache','dist','coverage','htmlcov','demo-video','.ssh','.aws') for part in Path(name).parts)
            or name.startswith('docker/secrets/') or p.name.startswith('.paypal-order')
            or p.name.startswith('.env') and p.name!='.env.example'
            or p.suffix in ('.db','.sqlite','.sqlite3','.zip') or any(mark in p.name for mark in ('.db-','.sqlite-','.sqlite3-'))):
            forbidden.append(name)
        data=p.read_bytes()
        if any(value.encode() in data for value in secrets) or re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data) or re.search(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}',data):
            suspicious.append(name)
    return {'candidate_files':len(candidates),'tested_ignored_paths':len(ignored),'missing_ignore_rules':sorted(set(examples)-ignored),
        'forbidden_publish_files':sorted(set(forbidden)),'credential_or_private_key_files':sorted(set(suspicious)),
        'existing_git_index':bool((root/'.git').exists()),'passed':not(forbidden or suspicious or set(examples)-ignored)}

if __name__=='__main__':
    result=audit();print(json.dumps(result,ensure_ascii=True))
    sys.exit(0 if result['passed'] else 1)
