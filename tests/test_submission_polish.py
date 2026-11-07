"""Final label/evidence contracts; provider calls are isolated by conftest."""
import hashlib,json
from pathlib import Path
import pytest
from backend import products,link_access,merchant_access
from backend.fx_opportunities import display_label
from backend.models import AICache
from backend.search_plan import build
from backend.shopping_strategy import decide
from tests.test_fx_opportunities import observations,listing


@pytest.mark.parametrize('reference,price,classification,label,strategy',[
    ('1.0002',10000,'favorable','Slight FX Improvement','us_stores_first'),
    ('1.0001',10000,'neutral','Neutral FX Trend','us_stores_first'),
    ('1',10000,'neutral','Neutral FX Trend','us_stores_first'),
    ('0.9998',10000,'unfavorable','Unfavorable FX Trend','us_stores_first'),
    ('1.01',10000,'favorable','Slight FX Improvement','compare_both'),
    ('1.02',10000,'favorable','Meaningful Shopping Opportunity','explore_overseas'),
    ('1.02',100,'favorable','Favorable Currency Trend — Product Advantage Unverified','compare_both'),
])
def test_labels_and_strategy_share_evidence_without_changing_math(db,reference,price,classification,label,strategy):
    observations(db,current='1',reference=reference)
    p=products.enrich(db,1,[listing(title='Coffee brewing dripper',currency='EUR',price=price)],'coffee')[0]
    plan=build(db,1);decision=decide(plan,[p]);f=p['fx_opportunity']
    assert f['market']['selected']['classification']==classification
    assert f['display_label']==label
    assert decision['strategy']==strategy
    assert next(m for m in decision['fx_evidence'] if m['currency']=='EUR')['display_label']==label
    assert bool(products.recommendation([p])['fx_backed_finds'])==(strategy=='explore_overseas')
    # The currency layer has no product evidence, including when products qualify.
    if strategy=='explore_overseas':
        assert f['market']['display_label']=='Favorable Currency Trend — Product Advantage Unverified'


def test_missing_price_and_configured_threshold_do_not_create_opportunity(db,monkeypatch):
    observations(db,current='1',reference='1.02')
    raw=listing(title='Coffee dripper',currency='EUR');raw['price_minor']=None
    p=products.enrich(db,1,[raw],'coffee')[0]
    assert not p['fx_opportunity']['verified']
    assert p['fx_opportunity']['display_label']=='Favorable Currency Trend — Product Advantage Unverified'
    assert decide(build(db,1),[p])['strategy']=='compare_both'
    monkeypatch.setenv('STRATEGY_MEANINGFUL_PERCENT','3')
    assert display_label(p['fx_opportunity']['market'])=='Slight FX Improvement'
    assert decide(build(db,1),[p])['strategy']=='compare_both'


def test_reachable_observation_does_not_approve_hario_but_existing_kinto_policy_applies(db,monkeypatch):
    monkeypatch.setattr(merchant_access,'manual_mode',lambda:True)
    monkeypatch.setattr(link_access,'probe',lambda _:pytest.fail('Manual policy must not perform network checks'))
    items=[]
    for merchant,url in [
        ('www.hario-europe.com','https://www.hario-europe.com/products/v60-ceramic-immersion-colour-dripper-switch-02-size'),
        ('kinto-usa.com','https://kinto-usa.com/products/27574'),
    ]:
        key='link-v1:'+hashlib.sha256(url.encode()).hexdigest()
        db.add(AICache(key=key,content=json.dumps(link_access.result('reachable','Read-only observation, not user approval'))))
        items.append(dict(listing(currency='USD'),merchant=merchant,url=url))
    db.commit()
    hario,kinto=link_access.attach(db,items)
    assert hario['link_access']['status']=='user_pending'
    assert merchant_access.decision('hario-europe.com') is None
    assert kinto['link_access']['status']=='user_confirmed'
    assert kinto['link_access']['server_observation']['status']=='reachable'


def test_current_documentation_distinguishes_merged_baseline_from_historical_work():
    root=Path(__file__).resolve().parents[1]
    for name in ('shopping-strategy.md','fx-driven-discovery.md','implementation-status.md'):
        text=(root/'docs'/name).read_text(encoding='utf-8')
        assert 'Current repository status' in text
        assert 'a7fb8a0' in text and 'main' in text
        assert 'Historical' in text
    readme=(root/'README.md').read_text(encoding='utf-8')
    assert 'Know What to Buy. Know Where to Buy.' in readme
    assert 'Private' in readme and 'final-submission-check.md' in readme
