from datetime import date,timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from sqlalchemy import select
from backend.models import Purchase,AnalysisState
from backend.history import PurchaseInput
from backend import analysis,fx,products
from tests.test_checkout import payload

def purchase(**changes):
    return {'purchased_at':date.today().isoformat(),'merchant_name':'Example Demo Camera Store','country_code':'US',
            'product_name':'Photography Course','category':'Photography','quantity':1,'price':'35.50','currency':'USD','notes':'User-provided demo',**changes}

def intelligence():
    return analysis.Intelligence(top_interests=[analysis.Interest(category='Photography',level='Emerging',reason='New observed purchases.')],
        emerging_interests=['Photography'],preferred_product_categories=['Photography'],potential_purchase_intentions=['May explore a related course.'],
        preferred_price_range='Observed USD range only.',novel_product_opportunities=['Explore related public product pages.'],
        explanation='Photography is an uncertain emerging interest.',uncertainty=['Purchase purpose is not known.'])

def fake_ai(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-only-key')
    monkeypatch.setenv('OPENAI_MODEL','gpt-6-luna')
    analysis._calls.clear()
    client=MagicMock()
    client.responses.parse.return_value=SimpleNamespace(output_parsed=intelligence(),usage=SimpleNamespace(input_tokens=100,output_tokens=50))
    monkeypatch.setattr(analysis,'OpenAI',lambda **kwargs:client)
    return client

def test_editable_history_crud_and_currency_validation(client):
    initial=len(client.get('/api/history').json())
    row=client.post('/api/history',json=purchase()).json()
    assert row['version']>1
    rows=client.get('/api/history').json()
    assert len(rows)==initial+1
    assert next(p for p in rows if p['id']==row['id'])['amount']==3550
    assert client.post(f'/api/history/{row["id"]}/edit',json=purchase(price='42.00')).status_code==200
    assert client.post(f'/api/history/{row["id"]}/delete',json={}).status_code==200
    assert len(client.get('/api/history').json())==initial
    for invalid in [purchase(price='-1'),purchase(price='NaN'),purchase(price='1.234',currency='JPY'),purchase(quantity=0),purchase(purchased_at=(date.today()+timedelta(days=1)).isoformat())]:
        assert client.post('/api/history',json=invalid).status_code==422

def test_payment_history_immutable_and_reset_scoped(client,db):
    other_before=len(list(db.scalars(select(Purchase).where(Purchase.user_id==3))))
    order=client.post('/api/checkout/orders',json=payload(mode='simulation')).json()
    client.post(f'/api/checkout/orders/{order["id"]}/capture',json={})
    paid=next(p for p in client.get('/api/history').json() if p['source']=='simulation')
    assert not paid['editable']
    assert client.post(f'/api/history/{paid["id"]}/delete',json={}).status_code==403
    assert client.post(f'/api/history/{paid["id"]}/edit',json=purchase()).status_code==403
    client.post('/api/demo/reset',json={})
    assert len(list(db.scalars(select(Purchase).where(Purchase.user_id==3))))==other_before
    assert any(p['id']==paid['id'] for p in client.get('/api/history').json())

def test_analysis_cache_and_history_invalidation(client,db,monkeypatch):
    fake=fake_ai(monkeypatch)
    first=analysis.run(db,1)
    assert first['status']=='completed'
    assert first['result']['model']=='gpt-6-luna'
    assert first['usage']['calls']==1
    assert analysis.run(db,1)['cached']
    assert fake.responses.parse.call_count==1
    client.post('/api/history',json=purchase())
    updated=analysis.run(db,1)
    assert updated['applied_version']==updated['version']
    assert fake.responses.parse.call_count==2
    assert updated['current_features']['scores']['Photography']>0
    assert updated['previous'] is not None

def test_stale_analysis_cannot_overwrite_newer_edit(db,monkeypatch):
    fake=fake_ai(monkeypatch)
    row=analysis.state(db,1)
    def delayed(**kwargs):
        row.version+=1;row.status='pending';db.commit()
        return SimpleNamespace(output_parsed=intelligence(),usage=SimpleNamespace(input_tokens=100,output_tokens=50))
    fake.responses.parse.side_effect=delayed
    result=analysis.run(db,1)
    assert result['applied_version']==0
    assert result['result'] is None
    assert result['status']=='pending'

def test_analysis_failure_preserves_previous(db,monkeypatch):
    from openai import OpenAIError
    fake=fake_ai(monkeypatch)
    analysis.run(db,1)
    row=analysis.state(db,1);row.feedback='Different shopping preference';row.version+=1;db.commit()
    fake.responses.parse.side_effect=OpenAIError('Mock unavailable')
    result=analysis.run(db,1)
    assert result['status']=='failed'
    assert result['result']['source']=='OpenAI analysis'
    assert 'preserved' in result['error'] or 'no alternate' in result['error']

def test_common_index_start_and_missing_dates():
    series={'EUR':{'history':[{'date':'2026-01-01','rate':'1.2'},{'date':'2026-01-02','rate':'1.0'},{'date':'2026-01-03','rate':'0.8'}]},
            'JPY':{'history':[{'date':'2026-01-02','rate':'0.01'},{'date':'2026-01-04','rate':'0.009'}]}}
    data=fx.indexed(series)
    assert data[0]['date']=='2026-01-02'
    assert Decimal(data[0]['EUR'])==Decimal(data[0]['JPY'])==100
    assert 'JPY' not in data[1]
    assert Decimal(data[1]['EUR'])==125

def test_frankfurter_v2_array_inversion(monkeypatch):
    mock=MagicMock();mock.__enter__.return_value=mock
    mock.get.return_value.json.return_value=[{'base':'USD','quote':'EUR','date':date.today().isoformat(),'rate':0.8},
        {'base':'USD','quote':'EUR','date':date.today().isoformat(),'rate':0}]
    monkeypatch.setattr(fx.httpx,'Client',lambda **kwargs:mock)
    result=fx.FrankfurterProvider().fetch(['EUR'])
    assert len(result)==1 and result[0][2]==Decimal('1.25')
    assert mock.get.call_args.kwargs['params']['base']=='USD'

def test_real_source_normalization_and_url_validation():
    entries=[{'url':'https://example-store.com/products/coffee','title':'Observed Coffee Product'},
             {'url':'https://example-store.com/products/coffee','title':'Duplicate'},
             {'url':'http://127.0.0.1/products/secret','title':'Blocked'},
             {'url':'javascript:alert(1)','title':'Blocked'}]
    result=products.normalize_sources(entries,'coffee','JP')
    assert len(result)==1
    assert result[0]['price_minor'] is None and result[0]['shipping_available'] is None
    assert result[0]['merchant_country'] is None
    assert not result[0]['paypal_checkout']
    assert products.recommendation(result,'cheapest')['winner'] is None
    assert products.recommendation(result,budget_minor=10000)['candidates']==[]

def test_real_search_failure_not_replaced_with_fake_products(client,monkeypatch):
    monkeypatch.setattr(products.provider,'search',lambda *args:{'items':[],'error':'Provider unavailable','source':'Unavailable'})
    products._calls.clear()
    result=client.post('/api/products/search',json={'query':'coffee equipment'}).json()
    assert result['items']==[] and result['error']

def test_legacy_jpy_quote_still_capturable(client,db,mock_paypal):
    from backend.models import Offer
    body=payload(currency='JPY')
    result=client.post('/api/checkout/orders',json=body).json()
    assert result['amount']==db.get(Offer,2).checkout_jpy
    assert result['currency']=='JPY'
    captured=client.post(f'/api/checkout/orders/{result["id"]}/capture',json={}).json()
    assert captured['status']=='COMPLETED'


def test_scoped_demo_restore_reproduces_the_same_story(client,db):
    def snapshot(uid):
        return [(p.product_name,p.amount,p.currency,p.purchased_at) for p in db.scalars(select(Purchase).where(Purchase.user_id==uid,Purchase.source=='synthetic_global').order_by(Purchase.id))]
    before=snapshot(3);other=snapshot(1)
    client.post('/api/demo/session',json={'persona':'outdoor'})
    client.post('/api/history/restore',json={})
    assert snapshot(3)==before
    assert snapshot(1)==other


def test_sensitive_interpretation_is_not_applied(db,monkeypatch):
    fake=fake_ai(monkeypatch)
    output=intelligence();output.explanation='A health condition can be inferred.'
    fake.responses.parse.return_value=SimpleNamespace(output_parsed=output,usage=SimpleNamespace(input_tokens=100,output_tokens=50))
    result=analysis.run(db,1)
    assert result['status']=='failed'
    assert result['result'] is None


def test_official_store_prices_are_observed_and_totals_remain_unknown():
    rows=[{'trackId':1,'trackName':'Photo Tool','trackViewUrl':'https://apps.apple.com/us/app/photo/id1','price':3.99,'currency':'USD','averageUserRating':4.5,'userRatingCount':100},
          {'trackId':2,'trackViewUrl':'https://apps.apple.com/us/app/free/id2','price':0,'currency':'USD','userRatingCount':None}]
    items=products.normalize_store(rows)
    assert [p['price_minor'] for p in items]==[399,0]
    assert all(p['estimated_total_usd'] is None and p['merchant_country'] is None and not p['paypal_checkout'] for p in items)
    assert products.recommendation(items,'quality')['winner']['id']=='apple:1'
    assert products.recommendation(items,'cheapest')['winner'] is None
    assert products.recommendation(items,'quality',1000)['winner'] is None


def test_official_store_failure_has_no_fabricated_results(monkeypatch):
    mock=MagicMock();mock.__enter__.return_value=mock
    mock.get.return_value.json.return_value=[]
    monkeypatch.setattr(products.httpx,'Client',lambda **kwargs:mock)
    result=products.OfficialAppStoreProvider().search('photo')
    assert result['items']==[] and result['error']
