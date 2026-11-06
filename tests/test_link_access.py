from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from unittest.mock import MagicMock
import socket
import threading
import pytest
from backend import link_access,products
from backend.models import AICache
from tests.test_recommendation_flow import listing

actual_probe=link_access.probe

@pytest.mark.parametrize('url,status,body,expected',[
    ('https://store.com/products/item',200,b'<h1>Product</h1>','reachable'),
    ('https://store.com/products/item',403,b'','restricted'),
    ('https://store.com/products/item',429,b'','rate_limited'),
    ('https://store.com/products/item',404,b'','unavailable'),
    ('https://store.com/products/item',200,b'Sorry, due to website restrictions we are unable to display the requested page.','restricted'),
    ('http://cpsrd.affinity.net/disabled.html',200,b'<h1>Disabled</h1>','unavailable'),
    ('https://store.com/products/item',200,b'<title>Access denied</title>','restricted'),
    ('https://buy.trychannel3.com/product',200,b"<h1>Quick security check</h1><p>Please verify you're human to continue</p><div class='cf-turnstile'></div>",'restricted'),
    ('https://buy.trychannel3.com/product',200,b'<h1>Product metadata</h1>','unconfirmed'),
    ('https://store.com/login',200,b'Please sign in','login_required'),
    ('https://store.com/',200,b'Homepage','unconfirmed'),
])
def test_http_and_soft_error_classification(url,status,body,expected):
    assert link_access.classify(url,status,{},body)[0]==expected

@pytest.mark.parametrize('url',['http://127.0.0.1/secret','https://169.254.169.254/latest','https://user:password@store.com/p','https://store.com:8080/p','file:///etc/passwd','https://metadata.google.internal/','https://localhost.local/p'])
def test_unsafe_urls_rejected(url):
    with pytest.raises(link_access.UnsafeLink):link_access.public_url(url)

def test_dns_private_or_mixed_answer_never_connects(monkeypatch):
    connect=MagicMock();monkeypatch.setattr(link_access.httpcore.SyncBackend,'connect_tcp',connect)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443)),(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(link_access.UnsafeLink):link_access.PublicNetwork().connect_tcp('rebind.store.com',443)
    connect.assert_not_called()

def test_public_dns_is_pinned_at_tcp_connection(monkeypatch):
    connect=MagicMock(return_value='network-stream');monkeypatch.setattr(link_access.httpcore.SyncBackend,'connect_tcp',connect)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    assert link_access.PublicNetwork().connect_tcp('store.com',443,2)=='network-stream'
    assert connect.call_args.args[:2]==('93.184.216.34',443)

class FakePool:
    def __init__(self,responses):self.responses=iter(responses);self.urls=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    @contextmanager
    def stream(self,method,url,**kwargs):
        self.urls.append(url);yield next(self.responses)

def response(status,headers=None,body=b''):
    return type('Response',(),{'status':status,'headers':headers or [],'iter_stream':lambda self:iter([body])})()

def test_redirect_chain_detects_disabled_page(monkeypatch):
    pool=FakePool([response(302,[(b'location',b'http://cpsrd.affinity.net/disabled.html')]),response(200,body=b'<h1>Disabled</h1>')])
    monkeypatch.setattr(link_access.httpcore,'ConnectionPool',lambda **k:pool)
    result=actual_probe('https://buy.trychannel3.com/example')
    assert result['status']=='unavailable' and result['final_host']=='cpsrd.affinity.net' and result['redirects']==1

def test_redirect_to_private_destination_is_blocked(monkeypatch):
    pool=FakePool([response(302,[(b'location',b'http://127.0.0.1/secret')])])
    monkeypatch.setattr(link_access.httpcore,'ConnectionPool',lambda **k:pool)
    assert actual_probe('https://store.com/products/item')['status']=='unsafe'
    assert len(pool.urls)==1

def test_result_cache_avoids_repeat_probe_and_refresh_has_cooldown(db,monkeypatch):
    calls=[]
    monkeypatch.setattr(link_access,'probe',lambda url:(calls.append(url) or link_access.result('reachable','Observed success')))
    first=link_access.attach(db,[listing(currency='USD')]);second=link_access.attach(db,[listing(currency='USD')])
    third=link_access.attach(db,[listing(currency='USD')],force=True)
    assert len(calls)==1 and second[0]['link_access']['cached'] and third[0]['link_access']['cached']
    assert first[0]['link_access']['checked_at'] and 'browser' in first[0]['link_access']['limitation']

def test_broken_and_unconfirmed_links_cannot_win_recommendations():
    good=listing(currency='USD');good.update(id='good',recommendation_score=30,link_access=link_access.result('reachable','Success'))
    broken=listing(currency='USD');broken.update(id='bad',recommendation_score=100,link_access=link_access.result('unavailable','Disabled page'))
    pending=listing(currency='USD');pending.update(id='pending',recommendation_score=99,link_access=link_access.result('unconfirmed','Timeout'))
    assert products.recommendation([broken,pending,good])['best_discovery']['id']=='good'
    assert products.recommendation([broken,pending])['best_discovery'] is None

def test_pending_check_is_harvested_without_duplicate_request(db,monkeypatch):
    release=threading.Event();calls=[]
    def blocked(url):
        calls.append(url);release.wait(3);return link_access.result('reachable','Finished check')
    monkeypatch.setattr(link_access,'probe',blocked)
    monkeypatch.setattr(link_access,'wait',lambda futures,timeout:None)
    try:
        data=link_access.attach(db,[listing(currency='USD')])
        assert data[0]['link_access']['pending']
        release.set()
        for future in list(link_access._pending.values()):future.result(timeout=3)
        next_result=link_access.attach(db,[listing(currency='USD')])
        assert next_result[0]['link_access']['status']=='reachable' and len(calls)==1
    finally:release.set()
