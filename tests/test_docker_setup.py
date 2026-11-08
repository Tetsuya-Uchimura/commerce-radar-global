"""Offline checkout/origin contracts for the same-origin Docker deployment."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest
from dotenv import dotenv_values
from backend.paypal import PayPal, SANDBOX


def test_examples_default_to_no_credentials_and_never_request_buyer_password():
    for path in ('.env.example','docker/env.example'):
        values=dotenv_values(path)
        assert all(not values.get(k) for k in ('CLIENT_ID','CLIENT_SECRET','OPENAI_API_KEY','CHANNEL3_API_KEY'))
        assert not any('PASSWORD' in k or 'PERSONAL_' in k for k in values)


def test_sandbox_client_preserves_canonical_docker_callback_and_idempotency(monkeypatch):
    paypal=PayPal();calls=[]
    monkeypatch.setattr(paypal,'call',lambda *args: calls.append(args) or {'id':'MOCK-ORDER'})
    order=SimpleNamespace(id=str(uuid4()),currency='USD',amount=3166,request_key=str(uuid4()))
    paypal.create(order,SimpleNamespace(name='Fictional Demo Merchant product'),'http://localhost:5173')
    method,path,body,key=calls[0]
    assert method=='POST' and path=='/v2/checkout/orders' and key==order.request_key
    experience=body['payment_source']['paypal']['experience_context']
    assert experience['return_url']==f'http://localhost:5173/payment/{order.id}?approved=1'
    assert experience['cancel_url']==f'http://localhost:5173/payment/{order.id}?cancelled=1'
    assert body['purchase_units'][0]['amount']=={'currency_code':'USD','value':'31.66'}
    assert SANDBOX=='https://api-m.sandbox.paypal.com'


@pytest.mark.parametrize('client_id,secret',[('',''),('configured-id',''),('','configured-secret')])
def test_missing_credential_does_not_enable_sandbox(client,monkeypatch,client_id,secret):
    monkeypatch.setenv('CLIENT_ID',client_id);monkeypatch.setenv('CLIENT_SECRET',secret)
    assert client.get('/api/demo/status').json()['sandbox_configured'] is False


def test_same_origin_session_cookie_and_write_guard_retained(client,mock_paypal):
    headers={'Origin':'http://localhost:5173','X-Commerce-Radar':'1'}
    session=client.post('/api/demo/session',json={'persona':'coffee'},headers=headers)
    cookie=session.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie and 'path=/' in cookie
    assert client.get('/api/profile').json()['home_currency']=='USD'
    payload={'offer_id':2,'quantity':1,'mode':'sandbox','currency':'USD','idempotency_key':str(uuid4())}
    assert client.post('/api/checkout/orders',json=payload,headers={**headers,'Origin':'https://untrusted.example'}).status_code==403
    client.headers.pop('X-Commerce-Radar',None)
    assert client.post('/api/checkout/orders',json=payload,headers={'Origin':headers['Origin']}).status_code==403
    response=client.post('/api/checkout/orders',json=payload,headers=headers)
    assert response.status_code==200 and response.json()['currency']=='USD'
    # A create request alone never captures, even when the mocked buyer is approved.
    assert mock_paypal['creates']==1 and mock_paypal['captures']==0


def test_docker_context_is_default_deny_and_local_credentials_are_not_build_inputs():
    rules=Path('.dockerignore').read_text().splitlines()
    assert next(s for s in rules if s and not s.startswith('#'))=='**'
    assert '!backend/*.py' in rules and '!frontend/src/**' in rules
    for rule in ('**/.env','**/.env.*','**/node_modules/**','**/*.db*','**/demo-video/**'):
        assert rule in rules
    compose=Path('compose.yaml').read_text()
    assert '${' not in compose # developer .env / shell keys cannot interpolate into services
    assert 'format: raw' in compose and 'required: false' in compose
    assert compose.count('ports:')==1 and '127.0.0.1:5173:8080' in compose
    frontend=compose.split('  frontend:',1)[1]
    assert 'env_file:' not in frontend and 'CLIENT_SECRET' not in frontend
    assert 'sqlite:////app/data/global_radar.db' in compose and './data:' not in compose
    assert '"--workers", "1"' in Path('docker/backend.Dockerfile').read_text()
    nginx=Path('docker/nginx.conf').read_text()
    assert 'try_files $uri $uri/ /index.html' in nginx
    assert 'proxy_pass http://$backend$request_uri' in nginx and 'access_log off' in nginx
