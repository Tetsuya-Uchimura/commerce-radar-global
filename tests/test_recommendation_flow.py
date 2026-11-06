import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from backend import analysis,products,discovery,conversation,fx,channel3
from backend.models import PaymentOrder
from backend.search_plan import build
from tests.test_us_enhancements import fake_ai,intelligence,purchase
from tests.test_checkout import payload

def listing(title='Photography creative course',currency='EUR',price=3500):
    return {'id':'observed','name':title,'description':'Camera photography workshop','merchant':'observed-store.com',
        'merchant_country':None,'price_minor':price,'currency':currency,'url':'https://observed-store.com/products/course',
        'verified_at':'2026-11-04T00:00:00Z','source':'Channel3 product API','kind':'external','estimated_total_usd':None}

def test_history_analysis_plan_and_real_recommendations_form_one_flow(client,db,monkeypatch):
    old=build(db,1)
    row=client.post('/api/history',json=purchase(category='Education')).json()
    fake=fake_ai(monkeypatch)
    result=analysis.run(db,1)
    plan=client.get('/api/products/plan').json()
    assert plan['signature']!=old['signature'] and plan['current_ai']
    assert plan['queries'][0]['category']=='Photography'
    assert {'top_interests','emerging_interests','potential_purchase_intentions','novel_product_opportunities'}<=set(origin for q in plan['queries'] for origin in q['origin'].split('+'))
    person=discovery.profile(db,1)
    assert person['search_plan']['signature']==plan['signature']
    assert person['search_plan']['ai_category_scores']['Photography']==70
    monkeypatch.setattr(products.provider,'search',lambda *a:{'items':[listing(currency='USD')],'error':None,'source':'Observed mock'})
    products._calls.clear()
    found=client.post('/api/products/search',json={}).json()
    assert 'photography' in found['query']
    assert found['items'][0]['analysis_version']==result['applied_version']
    assert found['items'][0]['score_factors']['interest']>0
    # A later edit makes old AI ineligible immediately, until the new version completes.
    client.post(f'/api/history/{row["id"]}/edit',json=purchase(category='Outdoor',product_name='Hiking Course'))
    pending=build(db,1)
    assert not pending['current_ai'] and pending['ai_category_scores']=={}
    output=intelligence();output.top_interests=[analysis.Interest(category='Outdoor',level='Strong',reason='Edited hiking purchase')]
    output.emerging_interests=['Outdoor'];output.preferred_product_categories=['Outdoor']
    output.potential_purchase_intentions=['hiking workshop'];output.novel_product_opportunities=['camping equipment']
    fake.responses.parse.return_value=SimpleNamespace(output_parsed=output,usage=None)
    analysis.run(db,1)
    edited=build(db,1)
    assert edited['queries'][0]['category']=='Outdoor'
    assert edited['signature']!=plan['signature']

def test_external_fx_rounding_and_unknown_costs(db,monkeypatch):
    monkeypatch.setattr(fx,'bundle',lambda *a,**k:{'rates':{'EUR':{'rate':'1.125','source':fx.provider.source,'rate_date':'2026-11-04','stale':False}}})
    p=products.enrich(db,1,[listing(price=399)],'photography',10000)[0]
    assert p['listing_usd_minor']==449 and p['fx']['rate_date']=='2026-11-04'
    assert p['estimated_total_usd'] is None and p['budget_status']=='unverified_total'
    assert products.recommendation([p],'cheapest',10000)['winner'] is None
    assert products.enrich(db,1,[listing(price=20000)],budget_minor=10000)==[]
    monkeypatch.setattr(fx,'bundle',lambda *a,**k:{'rates':{'EUR':{'rate':'1.1','source':'Synthetic Demo FX'}}})
    assert products.enrich(db,1,[listing()])[0]['listing_usd_minor'] is None

def test_channel3_multiple_offer_schema_and_unknowns():
    data={'products':[{'id':'p1','title':'Japanese Coffee Dripper','offers':[
        {'url':'https://store.com/products/dripper','domain':'store.com','price':{'price':29.95,'currency':'EUR'},'availability':'InStock'},
        {'url':'https://other.com/products/dripper','domain':'other.com','price':{'amount':3000,'currency':'JPY'}},
        {'url':'http://127.0.0.1/secret','price':{'price':0,'currency':'USD'}}]}]}
    found=channel3.normalize(data)
    assert len(found)==2 and [p['price_minor'] for p in found]==[2995,3000]
    assert found[0]['merchant']=='store.com' and found[0]['price_verified_at']
    assert all(p['merchant_country'] is None and p['shipping_available'] is None and p['taxes'] is None and not p['paypal_checkout'] for p in found)

def test_channel3_missing_key_and_malformed_response(monkeypatch):
    monkeypatch.delenv('CHANNEL3_API_KEY',raising=False)
    assert 'CHANNEL3_API_KEY' in channel3.provider.search('coffee')['error']
    monkeypatch.setenv('CHANNEL3_API_KEY','unit-test-only-key')
    client=MagicMock();client.__enter__.return_value=client
    client.post.return_value.json.return_value={'bad':'schema'}
    monkeypatch.setattr(channel3.httpx,'Client',lambda **k:client)
    result=channel3.provider.search('coffee')
    assert result['items']==[] and result['error']
    assert client.post.call_args.kwargs['headers']['x-api-key']=='unit-test-only-key'

def intent(**changes):
    return conversation.Intent(budget_usd=100,category='Coffee',country='JP',excluded_countries=[],kind='physical',compare_countries=[],fx_currency=None,fx_period=None,search_query='Japanese coffee brewing equipment',goal='best',open_details=False,feedback=None,requires_search=True,search_provider='web',**changes)

def test_japanese_structured_chat_updates_search_budget_country_and_ranking(client,db,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-only-key');conversation._calls.clear();products._calls.clear()
    ai=MagicMock();ai.responses.parse.return_value=SimpleNamespace(output_parsed=intent(),usage=None)
    monkeypatch.setattr(conversation,'OpenAI',lambda **k:ai)
    monkeypatch.setattr('backend.ai.explain',lambda db,scope,instructions,facts,fallback:{'explanation':fallback,'source':'Offline explanation'})
    observed=[]
    def provider(query,country):
        observed.append((query,country));return {'items':[listing(title='Japanese Coffee Dripper',currency='USD',price=2500)],'error':None,'source':'Observed mock'}
    monkeypatch.setattr(products.provider,'search',provider)
    result=client.post('/api/concierge',json={'message':'日本のコーヒー器具を100ドル以内で探したい'}).json()
    assert result['intent_source']=='OpenAI structured intent'
    assert {'type':'select_country','country':'JP'} in result['actions']
    filters=next(a['filters'] for a in result['actions'] if a['type']=='set_filters')
    assert filters['max_budget']==10000 and filters['category']=='Coffee' and filters['physical_only']
    action=next(a for a in result['actions'] if a['type']=='search_products')
    assert action['budget_minor']==10000 and action['country']=='JP'
    assert observed[0][1]=='JP' and result['real_products'][0]['listing_usd_minor']==2500
    assert result['recommendation']['winner'] is None
    # A refinement with no keyword must still search when structured intent requests it.
    conversation._calls.clear();products._calls.clear()
    revised=intent();revised.budget_usd=50;revised.search_query='Japanese compact coffee dripper'
    ai.responses.parse.return_value=SimpleNamespace(output_parsed=revised,usage=None)
    second=client.post('/api/concierge',json={'message':'もっとコンパクトなものを50ドルまでで'}).json()
    assert second['conditions']['max_budget']==5000 and len(observed)==2
    assert any(a['type']=='search_products' for a in second['actions'])
    # Product keywords alone cannot override a successful no-search structured intent.
    conversation._calls.clear();revised.requires_search=False
    ai.responses.parse.return_value=SimpleNamespace(output_parsed=revised,usage=None)
    third=client.post('/api/concierge',json={'message':'この商品検索の考え方を説明して'}).json()
    assert not any(a['type']=='search_products' for a in third['actions']) and len(observed)==2

def test_sandbox_verified_currency_is_derived_from_completed_capture(client,db,mock_paypal):
    assert client.get('/api/demo/status').json()['currencies_sandbox_verified']==[]
    simulated=client.post('/api/checkout/orders',json=payload(mode='simulation')).json()
    client.post(f'/api/checkout/orders/{simulated["id"]}/capture',json={})
    assert client.get('/api/demo/status').json()['currencies_sandbox_verified']==[]
    order=client.post('/api/checkout/orders',json=payload()).json()
    client.post(f'/api/checkout/orders/{order["id"]}/capture',json={})
    assert client.get('/api/demo/status').json()['currencies_sandbox_verified']==['USD']
