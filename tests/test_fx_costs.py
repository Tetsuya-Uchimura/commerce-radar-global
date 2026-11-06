from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from sqlalchemy import select
from backend.fx import purchasing_power,summarize,bundle,refresh_live
from backend.costs import landed_cost,major
from backend.models import Offer,ExchangeRate,Country


def test_fx_direction_and_zero_decimal_currency():
    assert purchasing_power(100,110)==Decimal('10.0')
    assert purchasing_power(110,100)<0
    assert purchasing_power(0,100) is None
    assert major(100,'JPY')==Decimal('100')
    assert major(100,'USD')==Decimal('1.00')


def test_30_90_reference_missing_and_staleness():
    today=date(2026,11,3)
    series=[(today-timedelta(days=d),Decimal(100)+Decimal(d)/10) for d in range(91)]
    result=summarize('USD',series,'Live test',today=today)
    assert Decimal(result['change_30'])==Decimal('3.00')
    assert Decimal(result['change_90'])==Decimal('9.00')
    assert result['fx_score']>50
    assert not result['stale']
    assert summarize('USD',series,'Live test',today=today+timedelta(days=5))['stale']
    sparse=summarize('USD',series[:3],'Live test',today=today)
    assert sparse['fx_score'] is None
    assert sparse['change_30'] is None
    assert summarize('USD',[(today,'0'),(today,'NaN')],'Live test')['rate'] is None


def test_live_cache_updates_and_missing_fallback(db,monkeypatch):
    import backend.fx as fx
    today=date.today()
    calls=[]
    def fetch(currencies):
        calls.append(currencies)
        return [('EUR',today,Decimal('1.4425'))]
    monkeypatch.setattr(fx.provider,'fetch',fetch)
    assert refresh_live(db,['EUR'])
    assert not refresh_live(db,['EUR'])
    assert len(calls)==1
    cached=db.scalar(select(ExchangeRate).where(ExchangeRate.source=='frankfurter'))
    assert cached.rate=='1.4425'
    cached.fetched_at=datetime.now(timezone.utc)-timedelta(hours=7)
    db.commit()
    monkeypatch.setattr(fx.provider,'fetch',lambda currencies:[('EUR',today,Decimal('1.43'))])
    refresh_live(db,['EUR'])
    assert cached.rate=='1.43'
    data=bundle(db,'live')
    assert data['effective_mode']=='mixed'
    assert data['rates']['EUR']['source']==fx.provider.source
    assert data['rates']['GBP']['source']=='Synthetic Demo FX'
    assert data['warning']


def test_landed_cost_unknown_costs_and_assumptions(db):
    offer=db.get(Offer,1)
    rate={'rate':'1.5'}
    result=landed_cost(offer,rate)
    assert result['components']['product']==4200
    assert result['total_usd']==sum(result['components'].values())
    assert result['estimate_only']
    offer.shipping=None
    incomplete=landed_cost(offer,rate)
    assert incomplete['total_usd'] is None
    assert 'shipping' in incomplete['unknown']
    offer.shipping=0
    offer.taxes=None
    assert landed_cost(offer,rate)['total_usd'] is None
    assert landed_cost(offer,None)['total_usd'] is None


def test_offer_selling_currency_separate_from_country(db):
    from backend.discovery import opportunities
    offer=db.get(Offer,1)
    offer.currency='USD'
    db.commit()
    rates=bundle(db)
    item=next(p for p in opportunities(db,1,rates) if p['id']==1)
    assert db.get(Country,'PT').currency=='EUR'
    assert item['currency']=='USD'
    assert Decimal(item['cost']['fx_rate'])==Decimal(rates['rates']['USD']['rate'])
