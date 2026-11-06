from uuid import uuid4
from sqlalchemy import select,func
from backend.models import Purchase,Offer,PaymentOrder
from backend.paypal import PaymentError,money_value,matches_amount


def payload(**changes):
    return {'offer_id':2,'quantity':1,'mode':'sandbox','idempotency_key':str(uuid4()),**changes}


def test_currency_and_minor_units():
    assert money_value(100,'JPY')=='100'
    assert money_value(1250,'USD')=='12.50'
    assert matches_amount({'currency_code':'JPY','value':'100.00'},100,'JPY')
    assert not matches_amount({'currency_code':'USD','value':'100'},100,'JPY')


def test_price_request_validation_and_create_dedup(client,db,mock_paypal):
    offer=db.get(Offer,2)
    before=offer.stock
    body=payload(quantity=2)
    result=client.post('/api/checkout/orders',json=body)
    assert result.status_code==200
    assert result.json()['amount']==offer.checkout_usd*2
    assert result.json()['currency']=='USD'
    assert db.get(Offer,2).stock==before-2
    assert client.post('/api/checkout/orders',json=body).json()['id']==result.json()['id']
    assert mock_paypal['creates']==1
    assert db.get(Offer,2).stock==before-2
    assert client.post('/api/checkout/orders',json={**body,'amount':1}).status_code==422
    assert client.post('/api/checkout/orders',json=payload(quantity=0)).status_code==422
    assert client.post('/api/checkout/orders',json=payload(offer_id=9999)).status_code==404
    assert client.post('/api/checkout/orders',json={**body,'quantity':3}).status_code==409


def test_capture_dedup_updates_history_and_intelligence(client,db,mock_paypal):
    profile=client.get('/api/profile').json()
    items=client.get('/api/discovery').json()['offers']
    offer=next(p for p in items if p['id']==2)
    before_novelty=offer['factors']['novelty']
    oid=client.post('/api/checkout/orders',json=payload()).json()['id']
    for _ in range(2):
        response=client.post(f'/api/checkout/orders/{oid}/capture',json={})
        assert response.status_code==200
        assert response.json()['status']=='COMPLETED'
    assert mock_paypal['captures']==1
    assert db.scalar(select(func.count()).select_from(Purchase).where(Purchase.source=='sandbox'))==1
    after=client.get('/api/profile').json()
    assert after['purchase_count']==profile['purchase_count']+1
    assert 'PT' in after['international_countries']
    history=client.get('/api/history').json()
    assert any(t['paypal_capture_id'] and t['source']=='sandbox' for t in history)
    updated=next(p for p in client.get('/api/discovery').json()['offers'] if p['id']==2)
    assert updated['factors']['novelty']<before_novelty


def test_lost_capture_response_reconciles(client,db,mock_paypal):
    oid=client.post('/api/checkout/orders',json=payload()).json()['id']
    mock_paypal['fail_capture_after_success']=True
    assert client.post(f'/api/checkout/orders/{oid}/capture',json={}).status_code==502
    assert client.post(f'/api/checkout/orders/{oid}/capture',json={}).json()['status']=='COMPLETED'
    assert mock_paypal['captures']==1
    assert db.scalar(select(func.count()).select_from(Purchase).where(Purchase.source=='sandbox'))==1


def test_unapproved_amount_and_currency_mismatch(client,db,mock_paypal):
    oid=client.post('/api/checkout/orders',json=payload()).json()['id']
    remote=mock_paypal['orders'][db.get(PaymentOrder,oid).paypal_order_id]
    remote['status']='PAYER_ACTION_REQUIRED'
    assert client.post(f'/api/checkout/orders/{oid}/capture',json={}).status_code==409
    remote['status']='APPROVED'
    remote['purchase_units'][0]['amount']['currency_code']='JPY'
    assert client.post(f'/api/checkout/orders/{oid}/capture',json={}).status_code==409
    remote['purchase_units'][0]['amount']['currency_code']='USD'
    remote['purchase_units'][0]['amount']['value']='1'
    assert client.post(f'/api/checkout/orders/{oid}/capture',json={}).status_code==409
    assert mock_paypal['captures']==0


def test_simulation_reset_preserves_all_app_payments(client,db):
    oid=client.post('/api/checkout/orders',json=payload(mode='simulation')).json()['id']
    assert client.post(f'/api/checkout/orders/{oid}/capture',json={}).json()['status']=='COMPLETED'
    assert client.post('/api/demo/reset',json={}).status_code==200
    assert db.get(PaymentOrder,oid).status=='COMPLETED'
    assert db.scalar(select(func.count()).select_from(Purchase).where(Purchase.source=='simulation'))==1
    assert db.scalar(select(func.count()).select_from(Purchase).where(Purchase.source=='synthetic_global'))==108


def test_api_failure_keeps_one_saved_reservation(client,db,mock_paypal,monkeypatch):
    from backend.paypal import paypal
    def fail(*args):raise PaymentError('Temporarily unavailable')
    monkeypatch.setattr(paypal,'create',fail)
    body=payload()
    before=db.get(Offer,2).stock
    for _ in range(2):assert client.post('/api/checkout/orders',json=body).status_code==502
    assert db.get(Offer,2).stock==before-1
    assert db.scalar(select(func.count()).select_from(PaymentOrder))==1


def test_ineligible_out_of_stock_and_seller_quote_is_fixed(client,db):
    assert client.post('/api/checkout/orders',json=payload(mode='simulation',offer_id=12)).status_code==422
    db.get(Offer,2).stock=0
    db.commit()
    assert client.post('/api/checkout/orders',json=payload(mode='simulation')).status_code==409


def test_external_seller_cannot_use_sandbox_even_if_flagged(client,db):
    offer=db.get(Offer,2)
    offer.source='External catalog'
    offer.merchant_name='Third-party seller'
    db.commit()
    assert client.post('/api/checkout/orders',json=payload(mode='simulation')).status_code==422


def test_oauth_mock_reuses_token(monkeypatch):
    from backend.paypal import PayPal
    monkeypatch.setenv('CLIENT_ID','test-client')
    monkeypatch.setenv('CLIENT_SECRET','test-secret')
    client=PayPal()
    calls=[]
    def fake(method,path,**kwargs):
        calls.append((method,path,kwargs))
        return {'access_token':'mock-token','expires_in':300}
    monkeypatch.setattr(client,'_request',fake)
    assert client.token()==client.token()=='mock-token'
    assert len(calls)==1
    assert calls[0][1]=='/v1/oauth2/token'
    assert calls[0][2]['data']=={'grant_type':'client_credentials'}


def test_pending_capture_is_not_a_completed_purchase(client,db,mock_paypal):
    oid=client.post('/api/checkout/orders',json=payload()).json()['id']
    order=db.get(PaymentOrder,oid)
    remote=mock_paypal['orders'][order.paypal_order_id]
    remote['status']='COMPLETED'
    remote['purchase_units'][0]['payments']={'captures':[{'id':'PENDING-CAP','status':'PENDING',
        'amount':remote['purchase_units'][0]['amount']}]}
    assert client.get(f'/api/checkout/orders/{oid}').json()['status']=='PENDING'
    assert db.scalar(select(func.count()).select_from(Purchase).where(Purchase.source=='sandbox'))==0
    remote['purchase_units'][0]['payments']['captures'][0]['status']='COMPLETED'
    assert client.get(f'/api/checkout/orders/{oid}').json()['status']=='COMPLETED'
    assert db.scalar(select(func.count()).select_from(Purchase).where(Purchase.source=='sandbox'))==1
