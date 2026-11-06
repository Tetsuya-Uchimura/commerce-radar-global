from pathlib import Path
import subprocess
from scripts.audit_publication import audit

def prepare(tmp_path):
    tmp_path.joinpath('.gitignore').write_text(Path('.gitignore').read_text(encoding='utf-8'),encoding='utf-8')
    tmp_path.joinpath('.env').write_text('CHANNEL3_API_KEY=unit-test-secret-should-stay-local\n',encoding='utf-8')
    for name in ['frontend/node_modules/example.js','data/global_radar.db','backend.zip']:
        p=tmp_path/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_text('local only')
    return tmp_path

def test_publish_candidates_exclude_dependencies_database_archive_and_env(tmp_path):
    result=audit(prepare(tmp_path))
    assert result['passed'] and result['missing_ignore_rules']==[]
    assert result['forbidden_publish_files']==[] and result['credential_or_private_key_files']==[]

def test_copied_secret_in_ordinary_source_is_detected_without_printing_value(tmp_path):
    root=prepare(tmp_path);root.joinpath('unsafe.py').write_text("key='unit-test-secret-should-stay-local'\n")
    result=audit(root)
    assert not result['passed'] and result['credential_or_private_key_files']==['unsafe.py']

def test_ignore_does_not_hide_an_already_tracked_env_file(tmp_path):
    root=prepare(tmp_path)
    subprocess.run(['git','init','--quiet',str(root)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(root),'add','-f','.env'],check=True,capture_output=True)
    result=audit(root)
    assert not result['passed'] and '.env' in result['forbidden_publish_files']
    assert '.env' in result['credential_or_private_key_files']
