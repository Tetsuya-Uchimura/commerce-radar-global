from backend.discovery_markets import markets
from backend.automatic_discovery import country_groups
from backend.search_plan import build
from tests.test_us_enhancements import fake_ai,purchase

def test_markets_are_interest_led_routes_not_verified_country_scores(client,db):
    data=client.get('/api/discovery?fx_mode=demo&country=JP&category=Coffee&excluded_countries=DE').json()
    suggestions=data['discovery_markets']
    assert suggestions and not any(m['code']=='DE' for m in suggestions)
    japan=next(m for m in suggestions if m['code']=='JP')
    assert japan['selected'] and japan['interests']==['Coffee']
    assert 'coffee' in japan['query'] and 'JP' in japan['query']
    assert all(m['opportunity_score'] is None and m['seller_location_verified'] is False for m in suggestions)
    assert all('not confirmed seller location' in m['reason'] for m in suggestions)

def test_history_analysis_changes_exploration_query_without_assigning_product_origin(client,db,monkeypatch):
    from backend import analysis
    before=markets(db,1)
    client.post('/api/history',json=purchase(category='Education'))
    fake_ai(monkeypatch);analysis.run(db,1)
    after=markets(db,1)
    assert before[0]['query']!=after[0]['query']
    assert 'photography' in after[0]['query'] and after[0]['interests'][0]=='Photography'
    assert all(m['opportunity_score'] is None for m in after)

def test_verified_map_ignores_search_target_currency_domain_and_blocked_links():
    unknown={'id':'unknown','merchant_country':None,'target_country':'JP','currency':'JPY','merchant':'shop.jp','recommendation_score':99,'link_access':{'status':'reachable'}}
    verified={'id':'verified','merchant_country':'CA','merchant_country_evidence':{'source':'Observed provider seller location','observed_at':'2026-11-04T00:00:00Z'},'recommendation_score':75,'link_access':{'status':'reachable'}}
    blocked={**verified,'id':'blocked','merchant_country':'DE','link_access':{'status':'restricted'}}
    result=country_groups([unknown,verified,blocked])
    assert [m['code'] for m in result['countries']]==['CA']
    assert [p['id'] for p in result['unknown_origin']]==['unknown']
    assert result['countries'][0]['score']==75
