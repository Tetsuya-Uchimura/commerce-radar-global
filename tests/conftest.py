import os
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from backend.db import get_db
from backend.main import app, sessions
from backend.models import Base
from backend.seed import seed


@pytest.fixture
def db(monkeypatch):
    from backend import curated
    monkeypatch.setattr(curated,'candidates',lambda *args:[])
    monkeypatch.setenv('ANALYSIS_AUTORUN','false')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('CHANNEL3_API_KEY',raising=False)
    from backend import product_runtime,products
    product_runtime.reset_runtime();products._calls.clear()
    from backend import link_access
    from backend import merchant_access
    monkeypatch.setattr(merchant_access,'manual_mode',lambda:False)
    monkeypatch.setattr(link_access,'probe',lambda url:link_access.result('reachable','Offline fixture: observed successful page response.'))
    from backend.fx import provider,_range_requests
    _range_requests.clear()
    monkeypatch.setattr(provider,'fetch',lambda currencies,*args:[])
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    @event.listens_for(engine, 'connect')
    def pragmas(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    maker = sessionmaker(engine, expire_on_commit=False)
    with maker() as session:
        seed(session)
        from backend.us_migration import migrate_us
        migrate_us(session)
        yield session
    engine.dispose()


@pytest.fixture
def client(db, monkeypatch):
    # Every normal test is offline, even when the developer's .env has keys.
    import backend.main as main
    monkeypatch.setenv('ANALYSIS_AUTORUN','false')
    import backend.fx as fx
    fx._range_requests.clear()
    monkeypatch.setattr(main, 'DEMO_MODE', True)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    from backend.paypal import paypal
    from backend.fx import provider
    monkeypatch.setattr(provider, 'fetch', lambda currencies,*args: [])
    def no_network(*args, **kwargs):
        pytest.fail('Unexpected external API call in an offline test')
    monkeypatch.setattr(paypal, '_request', no_network)
    app.dependency_overrides[get_db] = lambda: db
    sessions.clear()
    # No lifespan: isolated database is already initialized by the db fixture.
    c = TestClient(app)
    c.headers['X-Commerce-Radar'] = '1'
    assert c.post('/api/demo/session', json={'persona':'coffee'}).status_code == 200
    yield c
    app.dependency_overrides.clear()
    sessions.clear()


@pytest.fixture
def mock_paypal(monkeypatch):
    from backend.paypal import paypal
    from backend.paypal import money_value
    state = {'orders': {}, 'creates': 0, 'captures': 0, 'fail_capture_after_success': False}
    monkeypatch.setattr(paypal, 'configured', lambda: True)
    def create(order, product, url):
        state['creates'] += 1
        remote_id = 'TEST'+order.id.replace('-','').upper()
        remote = {'id': remote_id, 'intent': 'CAPTURE', 'status': 'APPROVED', 'purchase_units': [
            {'reference_id':order.id, 'custom_id':order.id,
             'amount':{'currency_code':order.currency,'value':money_value(order.amount,order.currency)}}],
            'links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token='+remote_id}]}
        state['orders'][remote_id] = remote
        return remote
    def get(order_id):
        return state['orders'][order_id]
    def capture(order_id, key):
        state['captures'] += 1
        remote = state['orders'][order_id]
        remote['status'] = 'COMPLETED'
        unit = remote['purchase_units'][0]
        unit['payments'] = {'captures':[{'id':'CAP'+order_id,'status':'COMPLETED','amount':unit['amount']}]}
        if state['fail_capture_after_success']:
            from backend.paypal import PaymentError
            raise PaymentError('Simulated lost response')
        return remote
    monkeypatch.setattr(paypal, 'create', create)
    monkeypatch.setattr(paypal, 'get', get)
    monkeypatch.setattr(paypal, 'capture', capture)
    return state
