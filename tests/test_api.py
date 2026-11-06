from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.main import app
from backend.models import SavedOpportunity,InterestProfile
from tests.test_checkout import payload


def test_personas_and_access_separation(client):
    first=client.get('/api/profile').json()
    assert first['interests'][0]['category']=='Coffee'
    oid=client.post('/api/checkout/orders',json=payload(mode='simulation')).json()['id']
    assert client.post('/api/demo/session',json={'persona':'outdoor'}).status_code==200
    assert client.get('/api/profile').json()['interests'][0]['category']=='Outdoor'
    assert client.get(f'/api/checkout/orders/{oid}').status_code==404
    assert client.post(f'/api/checkout/orders/{oid}/capture',json={}).status_code==404
    client.post('/api/demo/session',json={'persona':'creator'})
    assert client.get('/api/profile').json()['user_id']==4
    assert all(t['category'] in ('Photography','Education','Digital Experiences') for t in client.get('/api/history').json())
    assert TestClient(app).get('/api/profile').status_code==401
    assert client.post('/api/demo/session',json={'user_id':30,'persona':'coffee'}).status_code==422


def test_retired_endpoints_and_csrf(client):
    assert client.get('/api/merchant/dashboard').status_code==404
    assert client.get('/api/consumer/predictions').status_code==404
    client.headers.pop('X-Commerce-Radar')
    assert client.post('/api/demo/reset',json={}).status_code==403
    assert client.post('/api/demo/session',json={'persona':'coffee'},headers={'X-Commerce-Radar':'1','Origin':'https://untrusted.example'}).status_code==403


def test_map_country_filters_budget_and_sorts(client):
    all_data=client.get('/api/discovery').json()
    assert len(all_data['countries'])==10
    pt=client.get('/api/discovery?country=PT').json()
    assert pt['offers'] and all(p['country_code']=='PT' for p in pt['offers'])
    assert len(pt['countries'])==10
    assert client.get('/api/discovery?country=ZZ').json()['offers']==[]
    digital=client.get('/api/discovery?digital_only=true&max_budget=5000').json()['offers']
    assert digital and all(p['digital'] and p['cost']['complete'] and p['cost']['total_usd']<=5000 for p in digital)
    sorted_items=client.get('/api/discovery?sort=cost').json()['offers']
    totals=[p['cost']['total_usd'] for p in sorted_items if p['cost']['total_usd'] is not None]
    assert totals==sorted(totals)
    assert client.get('/api/discovery?adjustment=100').status_code==422


def test_profile_edit_and_saved_isolation(client,db):
    assert client.post('/api/profile',json={'interests':['Outdoor'],'budget_usd':7000}).status_code==200
    assert client.get('/api/profile').json()['interests']==[{'category':'Outdoor','score':70,'purchases':0}]
    assert client.post('/api/saved/1',json={'saved':True}).status_code==200
    assert [p['id'] for p in client.get('/api/discovery?saved_only=true').json()['offers']]==[1]
    client.post('/api/demo/session',json={'persona':'creator'})
    assert client.get('/api/discovery?saved_only=true').json()['offers']==[]
    assert client.post('/api/profile',json={'interests':['Invented Personal Attribute'],'budget_usd':5000}).status_code==422


def test_concierge_actions_not_payments(client):
    result=client.post('/api/concierge',json={'message':'Show digital coffee products from Portugal under 50 dollars including shipping'}).json()
    assert result['source']=='Statistical template · no LLM'
    assert {'type':'select_country','country':'PT'} in result['actions']
    filters=next(a['filters'] for a in result['actions'] if a['type']=='set_filters')
    assert filters=={'digital_only':True,'max_budget':5000,'category':'Coffee'}
    assert all(p['id'] in result['offer_ids'] for p in client.get('/api/discovery?country=PT&category=Coffee&digital_only=true&max_budget=5000').json()['offers'])
    buy=client.post('/api/concierge',json={'message':'I want to buy this product','offer_id':2}).json()
    assert {'type':'open_offer','offer_id':2} in buy['actions']
    assert not any('capture' in a['type'] or 'checkout' in a['type'] for a in buy['actions'])
    assert client.post('/api/concierge',json={'message':' '}).status_code==422
    assert client.post('/api/concierge',json={'message':'x'*801}).status_code==422
    answer=client.post('/api/concierge',json={'message':'Which countries offer better USD purchasing power?'}).json()
    assert 'Synthetic Demo FX' in answer['explanation']
    assert any(a['type']=='set_filters' and a['filters'].get('sort')=='fx' for a in answer['actions'])
