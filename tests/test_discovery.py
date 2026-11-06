from sqlalchemy import select,func
from backend import discovery as d
from backend.fx import bundle
from backend.models import Purchase,Offer,SavedOpportunity,InterestProfile
from backend.seed import seed


def test_profile_scoring_and_catalog(db):
    assert d.profile(db,1)['interests'][0]['category']=='Coffee'
    assert d.profile(db,3)['interests'][0]['category']=='Outdoor'
    assert d.score_factors(100,100,100,100,100,100)==100
    assert d.score_factors(100,None,100,100,100,100) is None
    items=d.opportunities(db,1,bundle(db))
    assert items[0]['category']=='Coffee'
    assert not any(p['id']==17 for p in items) # unavailable in Japan
    assert any(p['score'] is None for p in items)
    assert all(p['comparison']['advantage_percent'] is None for p in items if p['comparison']['equivalence_group'] is None)


def test_country_breadth_and_incomplete_penalties(db):
    assert d.country_score([{'score':100}])==25
    assert d.country_score([{'score':100}]*4)==100
    assert d.country_score([{'score':100}]*4+[{'score':None}]*4)==50
    assert d.country_score([{'score':None}]) is None
    ranks=d.countries(db,d.opportunities(db,1,bundle(db)),bundle(db))
    assert len(ranks)==10
    assert all(r['band']=='Insufficient Data' for r in d.countries(db,[],bundle(db)))


def test_budget_gate_unknowns_shipping_and_recalculation(db):
    balanced=bundle(db)
    baseline=d.opportunities(db,1,balanced)
    stronger=d.opportunities(db,1,bundle(db,scenario='strong-yen'))
    item=next(p for p in baseline if p['id']==1)
    changed=next(p for p in stronger if p['id']==1)
    assert changed['cost']['total_usd']<item['cost']['total_usd']
    assert changed['explanation']!=item['explanation']
    assert changed['factors']['fx']>item['factors']['fx']
    limited=d.opportunities(db,1,balanced,max_budget=5000)
    assert all(p['cost']['complete'] and p['cost']['total_usd']<=5000 for p in limited)
    altered=d.opportunities(db,1,balanced,shipping_adjustment=1000)
    assert next(p for p in altered if p['id']==1)['cost']['total_usd']>item['cost']['total_usd']
    assert next(p for p in altered if p['id']==2)['cost']==next(p for p in baseline if p['id']==2)['cost']


def test_seed_reset_is_reproducible(db):
    def snapshot():
        return [(p.user_id,p.product_name,p.amount,p.purchased_at) for p in db.scalars(select(Purchase).where(Purchase.source=='synthetic_global').order_by(Purchase.id))]
    before=snapshot()
    seed(db,reset=True)
    assert snapshot()==before
    assert len(before)==108
