from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
import json
import pytest
from backend import fx,products,channel3,product_runtime,analysis
from backend.fx_opportunities import comparison,summarize,intelligence,product_evidence,weights
from backend.models import ExchangeRate
from backend.search_plan import build
from tests.test_recommendation_flow import listing as base_listing

def listing(*args,**kwargs):
    return base_listing(*args,**kwargs)|{'price_verified_at':datetime.now(timezone.utc).isoformat()}

def observations(db,currency='EUR',current='1.05',reference='1.12',age=0):
    today=date.today()-timedelta(days=age)
    for n in (0,30,90,365):
        db.add(ExchangeRate(base=currency,quote='USD',source='frankfurter',rate_date=today-timedelta(days=n),rate=current if n==0 else reference,fetched_at=datetime.now(timezone.utc)))
    db.commit()

def test_power_and_constant_price_change_have_different_denominators():
    r=comparison('1.05','1.12')
    assert Decimal(r['purchasing_power_advantage'])==pytest.approx(Decimal('6.6666666666666666666666667'))
    assert Decimal(r['constant_price_usd_cost_change'])==Decimal('-6.2500')
    assert r['classification']=='favorable' and r['fx_score']>0
    assert comparison(1,1)['classification']=='neutral'
    assert comparison(1.12,1.05)['classification']=='unfavorable'
    assert comparison(0,1) is None and comparison('NaN',1) is None

@pytest.mark.parametrize('period',['30D','90D','1Y'])
def test_actual_reference_dates_periods_and_pair_direction(db,period):
    observations(db)
    market=intelligence(db,period)['markets'][0]
    assert market['currency']=='EUR' and market['eligible']
    assert market['current_rate']=='1.05' and market['selected']['reference_rate']=='1.12'
    assert all(market['comparisons'][p] is not None for p in ('30D','90D','1Y'))
    p=listing(currency='EUR',price=10000)
    r=product_evidence(p,market,100,100)
    assert r['current_usd_minor']==10500 and r['historical_usd_minor']==11200 and r['difference_usd_minor']==700
    assert r['favorable'] and r['factors']['interest']==100

def test_missing_stale_and_weekend_reference_are_explicit(db):
    assert intelligence(db)['favorable_currencies']==[]
    observations(db,age=8)
    m=next(m for m in intelligence(db)['markets'] if m['currency']=='EUR')
    assert m['stale'] and not m['eligible']
    today=date.today();r=summarize('GBP',[(today,'1'),(today-timedelta(days=92),'1.1')])
    assert r['selected']['reference_date']==(today-timedelta(days=92)).isoformat()
    assert r['comparisons']['1Y'] is None

def test_listing_currency_not_search_country_controls_benefit(db):
    observations(db,'JPY','0.006','0.007')
    market=next(m for m in intelligence(db)['markets'] if m['currency']=='JPY')
    jpy=product_evidence(listing(currency='JPY',price=10000),market,100,100)
    assert jpy['current_usd_minor']==6000 and jpy['favorable']
    usd=product_evidence(listing(currency='USD',price=10000),market,100,100)
    assert not usd['verified'] and not usd['favorable'] and usd['difference_usd_minor'] is None
    assert 'no foreign FX benefit' in usd['status']

@pytest.mark.parametrize('patch',[{'currency':None},{'price_minor':None},{'price_verified_at':None},{'price_verified_at':'2000-01-01T00:00:00Z'}])
def test_incomplete_or_old_listing_is_not_fx_ranked(db,patch):
    observations(db);market=intelligence(db)['markets'][0]
    raw=listing(currency='EUR');raw.update(patch)
    r=product_evidence(raw,market,100,100)
    assert not r['verified'] and not r['favorable'] and r['score'] is None

def test_fx_backed_ranking_personal_fit_and_no_invented_origin(db):
    observations(db)
    good=listing(title='Coffee Brewing Dripper',currency='EUR');good['id']='coffee'
    weak=listing(title='Outdoor Hiking Gear',currency='EUR');weak['id']='outdoor'
    result=products.enrich(db,1,[weak,good],'coffee')
    selected=products.recommendation(result)
    assert selected['best_fx_backed']['id']=='coffee'
    assert selected['best_verified_value'] is None
    assert all(p['merchant_country'] is None and p['estimated_total_usd'] is None for p in result)
    assert not next(p for p in result if p['id']=='outdoor')['fx_opportunity']['favorable']
    assert selected['best_fx_backed']['fx_opportunity']['current_usd_minor']==3675

def test_unfavorable_product_keeps_personal_discovery_without_badge(db):
    observations(db,current='1.2',reference='1.1')
    rows=products.enrich(db,1,[listing(currency='EUR')],'coffee')
    r=products.recommendation(rows)
    assert r['best_fx_backed'] is None and r['best_discovery']
    assert not rows[0]['fx_opportunity']['favorable']

def test_fx_first_query_signature_and_cache_survive_period_change(client,db,monkeypatch):
    observations(db);monkeypatch.setenv('CHANNEL3_API_KEY','unit-test-only-key')
    seen=[]
    def search(query,country):
        seen.append(query);return {'items':[listing(title='Coffee Dripper',currency='EUR')],'error':None,'source':'Observed fixture'}
    monkeypatch.setattr(channel3.provider,'search',search)
    plan=build(db,1)
    assert plan['fx_queries'][0]['listing_currency_target']=='EUR'
    first=client.post('/api/products/automatic',json={}).json()
    assert 'priced in EUR' in seen[0] and first['recommendation']['best_fx_backed']
    second=client.post('/api/products/automatic',json={'fx_period':'1Y'}).json()
    assert len(seen)==1 and second['mode']=='Cached Real Products'
    assert first['analysis_signature']!=second['analysis_signature']
    assert second['items'][0]['fx_opportunity']['period']=='1Y'
    assert first['unknown_origin'] and first['countries']==[]
    # Chart viewing never triggers the paid product adapter or OpenAI.
    client.get('/api/fx/chart?currency=EUR&period=3M')
    assert len(seen)==1

def test_frozen_observations_are_labelled_and_no_synthetic_fallback(client,db):
    snapshot=client.get('/api/fx/opportunities?mode=historical').json()
    assert snapshot['mode']=='historical' and 'saved Frankfurter' in snapshot['label']
    assert snapshot['as_of'] and len(snapshot['markets'])==8
    live=client.get('/api/fx/opportunities').json()
    assert all(m['status']=='insufficient_data' for m in live['markets'])

def test_weights_configurable_and_reject_invalid(monkeypatch):
    monkeypatch.setenv('FX_RECOMMENDATION_WEIGHTS_JSON','{"interest":50,"fx":30,"novelty":10,"evidence":10}')
    assert weights()['interest']==50
    monkeypatch.setenv('FX_RECOMMENDATION_WEIGHTS_JSON','{"interest":100}')
    with pytest.raises(ValueError):weights()

def test_curated_parser_requires_observed_price_currency_and_keeps_unknowns():
    from scripts.refresh_curated import extract
    html='<script type="application/ld+json">'+json.dumps({'@type':'Product','name':'Observed coffee dripper','offers':{'price':'9','priceCurrency':'GBP','url':'https://official-store.com/products/dripper'}})+'</script>'
    data=extract(html,'https://official-store.com/products/dripper',datetime.now(timezone.utc).isoformat())
    assert data[0]['price_minor']==900 and data[0]['currency']=='GBP'
    assert data[0]['merchant_country'] is None and data[0]['shipping_available'] is None
    assert not extract(html.replace('priceCurrency','unknown'),'https://official-store.com/products/dripper','now')

def test_old_long_range_rows_do_not_refetch_fresh_daily_window(db,monkeypatch):
    observations(db)
    db.add(ExchangeRate(base='EUR',quote='USD',source='frankfurter',rate_date=date(1950,1,1),rate='1',fetched_at=datetime.now(timezone.utc)-timedelta(days=10)));db.commit()
    monkeypatch.setattr(fx.provider,'fetch',lambda *args:pytest.fail('Fresh per-currency data must be reused despite old MAX chart rows'))
    assert not fx.refresh_live(db,['EUR'])

def test_curated_query_match_ignores_generic_fx_instructions(monkeypatch,tmp_path):
    from backend import curated
    f=tmp_path/'observed.json';f.write_text(json.dumps({'items':[{'name':'Coffee dripper','category':'Coffee','currency':'EUR','description':'Confirm original listing currency'}]}))
    monkeypatch.setattr(curated,'FILE',f)
    assert not curated.candidates('photography creative courses confirm original listing currency')
    assert curated.candidates('coffee brewing equipment','EUR')
    assert not curated.candidates('coffee brewing equipment','JPY')
