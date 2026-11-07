from datetime import datetime,timedelta,timezone
from copy import deepcopy
from unittest.mock import MagicMock
from types import SimpleNamespace
import json
import pytest
from backend import products,analysis,channel3,conversation,curated
from backend.shopping_strategy import decide,current,thresholds,observed_market,market_sections,explanation
from backend.search_plan import build
from backend.models import ChatState
from tests.test_fx_opportunities import observations,listing
from tests.test_us_enhancements import purchase,fake_ai

def candidate(db,currency='EUR',price=10000,us=False,title='Coffee brewing dripper'):
    raw=listing(title=title,currency=currency,price=price)
    if us:raw.update(storefront_market='US',storefront_market_evidence={'source':'https://observed-store.com/us-market','observed_at':datetime.now(timezone.utc).isoformat(),'basis':'Mocked publisher explicitly states US storefront market'})
    return products.enrich(db,1,[raw],'coffee')[0]

def test_meaningful_fx_and_relevant_price_select_overseas(db):
    observations(db);p=candidate(db)
    r=decide(build(db,1),[p])
    assert r['strategy']=='explore_overseas' and r['recommended_currencies']==['EUR']
    assert r['primary_interest']=='Coffee' and r['recommended_sources'][0]['url']==p['url']
    assert r['recommended_sources'][0]['seller_country'] is None
    assert 'meaningful_absolute_difference' in r['reason_codes']

def test_unrelated_goods_cannot_force_overseas(db):
    observations(db);p=candidate(db,title='Outdoor hiking tent')
    assert decide(build(db,1),[p])['strategy']=='compare_both'

@pytest.mark.parametrize('current_rate,reference',[('1.05','1.05'),('1.2','1.05')])
def test_neutral_or_negative_fx_and_us_market_proof_choose_domestic(db,current_rate,reference):
    observations(db,current=current_rate,reference=reference)
    r=decide(build(db,1),[candidate(db,currency='USD',us=True)])
    assert r['strategy']=='us_stores_first' and r['recommended_sources'][0]['storefront_market']=='US'
    assert 'not establish that US prices are lower' in r['summary']

def test_no_us_proof_produces_honest_search_suggestion(db):
    observations(db,current='1.05',reference='1.05')
    p=candidate(db,currency='USD');p['merchant_country']='JP'
    r=decide(build(db,1),[p])
    assert observed_market(p) is None and not p['fx_opportunity']['favorable']
    assert r['strategy']=='us_stores_first' and r['recommended_sources']==[]
    assert 'domestic_search_suggestion_only' in r['reason_codes']

def test_mixed_fx_without_usable_foreign_price_compares_both(db):
    observations(db);observations(db,'JPY','0.007','0.006')
    p=candidate(db);p['price_minor']=None;p['fx_opportunity']['verified']=False
    assert decide(build(db,1),[p])['strategy']=='compare_both'

def test_tiny_absolute_difference_does_not_create_strong_message(db):
    observations(db);p=candidate(db,price=100)
    assert p['fx_opportunity']['favorable']
    r=decide(build(db,1),[p]);assert r['strategy']=='compare_both'
    assert not r['meaningful_product_ids']
    assert products.recommendation([p])['fx_backed_finds']==[]

def test_thresholds_are_configurable_and_validated(db,monkeypatch):
    observations(db);p=candidate(db,price=100)
    monkeypatch.setenv('STRATEGY_MINIMUM_DIFFERENCE_USD','0.01')
    assert decide(build(db,1),[p])['strategy']=='explore_overseas'
    monkeypatch.setenv('STRATEGY_MEANINGFUL_PERCENT','20')
    assert decide(build(db,1),[p])['strategy']=='compare_both'
    monkeypatch.setenv('STRATEGY_NEUTRAL_PERCENT','30')
    with pytest.raises(ValueError):thresholds()

def test_missing_fx_never_creates_market_advantage(db):
    r=decide(build(db,1),[candidate(db,currency='USD')])
    assert r['strategy']=='compare_both' and 'missing_fx_history' in r['reason_codes']

@pytest.mark.parametrize('stale_kind',['price','fx'])
def test_stale_evidence_cannot_drive_current_overseas(db,stale_kind):
    observations(db,age=10 if stale_kind=='fx' else 0)
    p=candidate(db)
    if stale_kind=='price':p['fx_opportunity']['listing_fresh']=False
    assert decide(build(db,1),[p])['strategy']!='explore_overseas'

def test_negative_fx_product_remains_personal_discovery(db):
    observations(db,current='1.2',reference='1.05')
    p=candidate(db);r=products.recommendation([p])
    assert r['best_discovery'] and not r['best_fx_backed']
    assert decide(build(db,1),[p])['strategy']=='us_stores_first'

def test_selected_currency_limits_strategy_evidence(db):
    observations(db);observations(db,'JPY','0.006','0.006')
    r=decide(build(db,1),[candidate(db)],{'listing_currency':'JPY'})
    assert r['strategy']=='us_stores_first' and r['meaningful_product_ids']==[]

def test_stale_storefront_proof_is_not_us_evidence(db):
    p=candidate(db,currency='USD',us=True)
    p['storefront_market_evidence']['observed_at']=(datetime.now(timezone.utc)-timedelta(days=35)).isoformat()
    assert observed_market(p) is None
    assert market_sections([p])['unverified_market']==[p]

def test_initial_strategy_and_per_persona_override_and_clear(client,db):
    d=client.get('/api/discovery?fx_mode=demo').json()
    assert d['strategy']['strategy']=='compare_both' and d['strategy']['recommended_sources']==[]
    db.add(ChatState(user_id=1,conditions_json=json.dumps({'search_query':'old overseas query','country':'JP'}),messages_json='[]'));db.commit()
    assert client.post('/api/strategy/preference',json={'priority':'domestic'}).status_code==200
    assert 'search_query' not in json.loads(db.get(ChatState,1).conditions_json)
    r=client.post('/api/products/automatic',json={}).json()
    assert r['mode']=='Demo Products' and r['strategy']['strategy']=='us_stores_first' and r['strategy']['user_override']
    client.post('/api/demo/session',json={'persona':'outdoor'})
    assert not client.get('/api/discovery?fx_mode=demo').json()['strategy']['user_override']
    client.post('/api/demo/session',json={'persona':'coffee'})
    assert client.get('/api/discovery?fx_mode=demo').json()['strategy']['shopping_priority']=='domestic'
    client.post('/api/concierge/clear',json={})
    assert client.get('/api/discovery?fx_mode=demo').json()['strategy']['shopping_priority']=='auto'

def test_domestic_and_explicit_overseas_queries_use_one_cached_search(client,db,monkeypatch):
    observations(db,current='1.2',reference='1.05');monkeypatch.setenv('CHANNEL3_API_KEY','unit-test-only-key')
    seen=[]
    def search(query,country):
        seen.append(query);return {'items':[listing(title='Coffee dripper',currency='USD')],'error':None,'source':'Mocked API'}
    monkeypatch.setattr(channel3.provider,'search',search)
    first=client.post('/api/products/automatic',json={}).json()
    assert 'US shopping sources' in seen[0] and first['strategy']['strategy']=='us_stores_first'
    client.post('/api/products/automatic',json={});assert len(seen)==1
    products._calls.clear()
    other=client.post('/api/products/automatic',json={'shopping_priority':'overseas','listing_currency':'EUR'}).json()
    assert 'priced in EUR' in seen[-1] and other['strategy']['user_override']
    assert other['strategy']['calculated_strategy']=='us_stores_first'

def test_explanation_is_scoped_versioned_and_offline_fallback(client,db):
    r=client.get('/api/discovery?fx_mode=demo').json()['strategy']
    answer=client.post('/api/strategy/explanation',json={'signature':r['signature']}).json()
    assert answer['explanation']==r['summary'] and 'no LLM' in answer['source']
    client.post('/api/demo/session',json={'persona':'outdoor'})
    assert client.post('/api/strategy/explanation',json={'signature':r['signature']}).status_code==409
    client.post('/api/demo/session',json={'persona':'coffee'})
    client.post('/api/history',json=purchase())
    assert client.post('/api/strategy/explanation',json={'signature':r['signature']}).status_code==409

def test_explanation_cache_fingerprint_ignores_link_cache_and_fx_retrieval_noise(db):
    observations(db);p=candidate(db);p['link_access']={'status':'reachable','cached':False}
    plan=build(db,1);a=decide(plan,[p])
    other=deepcopy(p);other['link_access']['cached']=True;other['fx_opportunity']['market']['retrieved_at']='changed retrieval timestamp'
    assert decide(plan,[other])['signature']==a['signature']

def test_structured_concierge_priority_persists_and_searches(client,db,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-only-key');conversation._calls.clear()
    from tests.test_recommendation_flow import intent
    parsed=intent();parsed.country=None;parsed.shopping_priority='domestic';parsed.search_query='coffee brewing equipment from US shopping sources'
    ai=MagicMock();ai.responses.parse.return_value=SimpleNamespace(output_parsed=parsed,usage=None)
    monkeypatch.setattr(conversation,'OpenAI',lambda **kwargs:ai)
    monkeypatch.setattr('backend.ai.explain',lambda db,scope,task,facts,fallback:{'explanation':fallback,'source':'Offline fixture'})
    seen=[]
    monkeypatch.setattr(products.provider,'search',lambda query,country:seen.append(query) or {'items':[listing(title='Coffee dripper',currency='USD')],'error':None,'source':'Mocked web'})
    result=client.post('/api/concierge',json={'message':'Find coffee products from US stores first'}).json()
    assert result['strategy']['shopping_priority']=='domestic' and 'US shopping sources' in seen[0]
    assert any(a['type']=='set_filters' and a['filters'].get('shopping_priority')=='domestic' for a in result['actions'])
    assert json.loads(db.get(ChatState,1).conditions_json)['shopping_priority']=='domestic'

def test_genuine_historical_examples_reproduce_all_three_without_network():
    from scripts.strategy_demo import scenarios
    cases=scenarios()
    assert set(cases)=={'explore_overseas','us_stores_first','compare_both'}
    for expected,result in cases.items():
        assert result['strategy']==expected and result['fx_mode']=='historical'
        assert 'Historical demonstration:' in result['limitations'][0]

def test_historical_budget_uses_saved_rates_without_live_retrieval(db,monkeypatch):
    monkeypatch.setattr('backend.fx.bundle',lambda *args:pytest.fail('Historical product amounts must not fetch live FX'))
    raw=listing(title='Coffee dripper',currency='EUR',price=5990)
    rows=products.enrich(db,1,[raw],'coffee',fx_mode='historical')
    amount=rows[0]['listing_usd_minor']
    assert amount==rows[0]['fx_opportunity']['current_usd_minor']
    assert products.enrich(db,1,[raw],'coffee',budget_minor=amount,fx_mode='historical')
    assert products.enrich(db,1,[raw],'coffee',budget_minor=amount-1,fx_mode='historical')==[]

@pytest.mark.parametrize('explicit',[False,True])
def test_ask_why_uses_viewed_strategy_sources_without_a_new_search(client,db,monkeypatch,explicit):
    observations(db);p=candidate(db)
    card=current(db,1,build(db,1),[p],{})
    monkeypatch.setattr(products.provider,'search',lambda *args:pytest.fail('Explaining a viewed card must not start a product search'))
    result=client.post('/api/concierge',json={'message':'Explain the current strategy and websites without searching or changing conditions.','strategy_signature':card['signature'],'explain_strategy':explicit}).json()
    assert result['strategy']['signature']==card['signature']
    assert result['strategy']['recommended_sources'][0]['url']==p['url']
    assert p['merchant'] in result['explanation']
    assert not any(a['type']=='search_products' for a in result['actions'])

def test_immediate_card_requires_no_external_fx_ai_or_product_calls(client,monkeypatch):
    monkeypatch.setattr('backend.fx.provider.fetch',lambda *args:pytest.fail('Immediate card must use cached observations only'))
    monkeypatch.setattr(products.provider,'search',lambda *args:pytest.fail('Immediate card must not search'))
    result=client.get('/api/strategy/initial').json()
    assert result['provisional'] and result['strategy']=='compare_both'
    assert result['primary_interest']=='Coffee' and not result['recommended_sources']
