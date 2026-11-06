from datetime import datetime,timedelta,timezone
import json,threading,time
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select,create_engine,func
from sqlalchemy.orm import Session as DBSession
from backend import products,analysis,product_runtime,channel3
from backend.automatic_discovery import country_groups
from backend.models import AICache,APIUsage,Base
from backend.seed import seed
from tests.test_recommendation_flow import listing
from tests.test_us_enhancements import purchase,fake_ai,intelligence
from types import SimpleNamespace

def enable(monkeypatch):
    monkeypatch.setenv('CHANNEL3_API_KEY','unit-test-only-key')
    calls=[]
    def search(query,country):
        calls.append(query)
        return {'items':[listing(title='Camera Coffee Dripper',currency='USD')],'error':None,'source':'Channel3 product API'}
    monkeypatch.setattr(channel3.provider,'search',search)
    return calls

def automatic(client,**changes):return client.post('/api/products/automatic',json=changes).json()

def test_scenario_a_automatic_initial_persona_and_cache(client,db,monkeypatch):
    calls=enable(monkeypatch)
    first=automatic(client)
    assert first['mode']=='Real Products' and first['items']
    assert first['items'][0]['data_source']=='Real Product'
    assert first['recommendation']['best_discovery'] and first['recommendation']['best_verified_value'] is None
    assert first['unknown_origin'] and first['countries']==[]
    second=automatic(client)
    assert second['mode']=='Cached Real Products' and len(calls)==1
    assert second['items'][0]['data_source']=='Cached Product'
    # Budget/FX ranking is local; the same upstream query does not need another call.
    assert automatic(client,budget_minor=10000)['items'] and len(calls)==1
    client.post('/api/demo/session',json={'persona':'outdoor'})
    other=automatic(client)
    assert other['user_id']==3 and len(calls)==2 and calls[-1]!=calls[0]

def test_scenario_b_edit_analysis_then_automatic_search(client,db,monkeypatch):
    calls=enable(monkeypatch);automatic(client)
    row=client.post('/api/history',json=purchase(category='Education')).json()
    ai=fake_ai(monkeypatch);analysis.run(db,1);products._calls.clear()
    photo=automatic(client)
    assert 'photography' in calls[-1].lower()
    assert photo['version']==row['version'] and photo['items'][0]['analysis_version']==row['version']
    client.post(f'/api/history/{row["id"]}/edit',json=purchase(category='Outdoor',product_name='Hiking Course'))
    output=intelligence();output.emerging_interests=['Outdoor']
    ai.responses.parse.return_value=SimpleNamespace(output_parsed=output,usage=None)
    analysis.run(db,1);products._calls.clear()
    hiking=automatic(client)
    assert 'outdoor' in calls[-1].lower() and hiking['version']>photo['version']
    client.post(f'/api/history/{row["id"]}/delete',json={});analysis.run(db,1)
    assert automatic(client)['version']>hiking['version']

def test_scenario_c_missing_key_never_uses_openai_product_search(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-only-key')
    monkeypatch.setattr(products.provider,'search',lambda *a:(_ for _ in ()).throw(AssertionError('Must not auto-spend on Web')))
    data=automatic(client)
    assert data['mode']=='Demo Products' and 'Live product search unavailable' in data['notice']
    assert data['items']==[] and client.get('/api/discovery?fx_mode=demo').json()['offers']

def test_scenario_d_failed_refresh_reuses_exact_cache_and_records_error(client,db,monkeypatch):
    calls=enable(monkeypatch);first=automatic(client)
    cached=db.scalar(select(AICache).where(AICache.key.like('products:%')))
    cached.created_at=datetime.now(timezone.utc)-timedelta(hours=5);db.commit()
    monkeypatch.setattr(channel3.provider,'search',lambda *a:{'items':[],'error':'Channel3 authentication failed.','source':'Unavailable'})
    products._calls.clear();second=automatic(client,refresh=True)
    assert second['mode']=='Cached Real Products' and second['items'] and second['error']
    assert second['stale_cache'] and second['items'][0]['id']==first['items'][0]['id']
    assert db.scalar(select(func.count()).select_from(APIUsage).where(APIUsage.status=='failed'))==1
    # A different query must not receive the old, unrelated products.
    third=automatic(client,query='unrelated hiking equipment')
    assert third['mode']=='Demo Products' and third['error'] and third['items']==[]

def test_successful_zero_results_are_not_mixed_with_demo(client,monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(channel3.provider,'search',lambda *a:{'items':[],'error':None,'source':'Channel3 product API'})
    result=automatic(client)
    assert result['mode']=='Real Products' and result['items']==[]
    assert 'No products match' in result['notice'] and not result['error']

def test_old_version_is_discarded_during_provider_call(client,db,monkeypatch):
    enable(monkeypatch)
    def delayed(*args):
        analysis.touch(db,1)
        return {'items':[listing(currency='USD')],'error':None,'source':'Channel3 product API'}
    monkeypatch.setattr(channel3.provider,'search',delayed)
    data=automatic(client)
    assert data['discarded'] and data['items']==[]
    assert automatic(client,expected_signature='obsolete')['discarded']

def test_analysis_pending_waits_without_search_then_failure_uses_statistics(client,db,monkeypatch):
    calls=enable(monkeypatch);monkeypatch.setenv('OPENAI_API_KEY','unit-test-only-key');monkeypatch.setenv('ANALYSIS_AUTORUN','true')
    assert automatic(client)['waiting_for_analysis'] and calls==[]
    state=analysis.state(db,1);state.status='failed';db.commit()
    assert automatic(client)['items'] and len(calls)==1

def test_origin_proof_required_and_complete_costs_select_verified_value(db):
    raw=listing(currency='USD');raw.update(merchant_country='JP',ship_from_country='US',delivery_countries=['US'])
    enriched=products.enrich(db,1,[raw],'coffee')
    assert not country_groups(enriched)['countries']
    raw['merchant_country_evidence']={'source':'https://observed-store.com/about','observed_at':datetime.now(timezone.utc).isoformat()}
    raw['verified_cost_components']={'product':3500,'shipping':300,'tax':250,'conversion':0}
    raw['cost_evidence']={k:{'source':'Observed seller quote','observed_at':datetime.now(timezone.utc).isoformat()} for k in raw['verified_cost_components']}
    enriched=products.enrich(db,1,[raw],'coffee')
    grouped=country_groups(enriched)
    assert grouped['countries'][0]['code']=='JP' and grouped['unknown_origin']==[]
    choice=products.recommendation(enriched,budget_minor=5000)
    assert choice['best_verified_value']['estimated_total_usd']==4050
    assert choice['best_discovery']

def test_daily_cap_and_failure_circuit_breaker(client,db,monkeypatch):
    calls=enable(monkeypatch);monkeypatch.setenv('PRODUCT_SEARCH_MAX_PER_DAY','1')
    automatic(client);products._calls.clear()
    limited=automatic(client,query='second query')
    assert len(calls)==1 and 'daily limit' in limited['error']
    assert automatic(client)['mode']=='Cached Real Products'

def test_single_flight_same_query_across_sessions(tmp_path,monkeypatch):
    product_runtime.reset_runtime();products._calls.clear();calls=enable(monkeypatch)
    engine=create_engine('sqlite:///'+str(tmp_path/'concurrent.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    with DBSession(engine) as db:seed(db)
    entered=threading.Event();release=threading.Event()
    def blocked(*args):
        calls.append('one upstream');entered.set();assert release.wait(5)
        return {'items':[listing(currency='USD')],'error':None,'source':'Channel3 product API'}
    monkeypatch.setattr(channel3.provider,'search',blocked)
    def call():
        with DBSession(engine) as db:return products.search(db,1,'identical coffee',provider_name='channel3')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(call);assert entered.wait(5);second=pool.submit(call);release.set()
        a=first.result();b=second.result()
    assert a['items'] and b['cached'] and calls==['one upstream']
    engine.dispose()

def test_startup_probes_actual_provider_once_and_warms_cache(db,monkeypatch):
    calls=enable(monkeypatch);health=product_runtime.check_startup(db)
    assert health['status']=='available' and len(calls)==1
    again=products.search(db,1,'coffee brewing equipment artisan beans workshops',provider_name='channel3')
    assert again['cached'] and len(calls)==1
