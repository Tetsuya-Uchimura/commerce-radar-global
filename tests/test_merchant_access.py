import hashlib,json
from datetime import datetime,timezone
from backend import products,link_access
from backend.merchant_access import decision,POLICY_PATH
from backend.models import AICache
from tests.test_recommendation_flow import listing

def test_user_table_is_recorded_and_domains_are_boundary_matched():
    policy=json.loads(POLICY_PATH.read_text())
    assert len(policy['allow'])==35 and set(policy['exclude'])=={'academy.com','belk.com','jcpenney.com'}
    assert decision('www.belk.com')['decision']=='exclude'
    assert decision('offers.abt.com')['decision']=='allow'
    assert decision('www.hario-usa.com')['decision']=='allow'
    assert decision('notbelk.com') is None and decision('buy.trychannel3.com') is None

def test_exclusions_filter_cached_product_data_before_display(db):
    rows=[dict(listing(currency='USD'),merchant=m,id=m) for m in ['academy.com','belk.com','jcpenney.com','abt.com','new.store.com']]
    result=products.enrich(db,1,rows)
    assert {p['merchant'] for p in result}=={'abt.com','new.store.com'}

def test_manual_confirmation_overrides_server_challenge_without_automated_request(db,monkeypatch):
    p=dict(listing(currency='USD'),merchant='abt.com')
    prior=link_access.result('restricted','Server browser verification required')
    key='link-v1:'+hashlib.sha256(p['url'].encode()).hexdigest()
    db.add(AICache(key=key,content=json.dumps(prior),created_at=datetime.now(timezone.utc)));db.commit()
    monkeypatch.setattr(link_access,'probe',lambda url:(_ for _ in ()).throw(AssertionError('Manual review must not trigger probe')))
    result=link_access.attach(db,[p])[0]
    assert result['link_access']['status']=='user_confirmed' and result['link_access']['scope']=='user'
    assert result['link_access']['server_observation']['status']=='restricted'
    assert products.recommendation([result])['best_discovery']
    assert result['merchant_country'] is None and result['estimated_total_usd'] is None

def test_manual_allow_does_not_override_known_broken_or_unsafe_url(db):
    p=dict(listing(currency='USD'),merchant='abt.com')
    key='link-v1:'+hashlib.sha256(p['url'].encode()).hexdigest()
    db.add(AICache(key=key,content=json.dumps(link_access.result('unavailable','Disabled destination')),created_at=datetime.now(timezone.utc)));db.commit()
    assert link_access.attach(db,[p])[0]['link_access']['status']=='unavailable'
    assert link_access.attach(db,[dict(p,url='http://127.0.0.1/private')])[0]['link_access']['status']=='unsafe'

def test_new_merchant_waits_for_user_review_without_network(db,monkeypatch):
    from backend import merchant_access
    monkeypatch.setattr(merchant_access,'manual_mode',lambda:True)
    monkeypatch.setattr(link_access,'probe',lambda url:(_ for _ in ()).throw(AssertionError('No automatic probe in manual mode')))
    item=link_access.attach(db,[listing(currency='USD')])[0]
    assert item['link_access']['status']=='user_pending'
