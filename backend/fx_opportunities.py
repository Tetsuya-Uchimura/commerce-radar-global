"""Auditable FX-first intelligence. USD per foreign unit, Decimal throughout."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib, json, os, math
from pathlib import Path
from sqlalchemy import select
from . import fx
from .models import ExchangeRate

D=Decimal
PERIODS={'30D':30,'90D':90,'1Y':365}
DEFAULT_WEIGHTS={'interest':45,'fx':35,'novelty':10,'evidence':10}
SNAPSHOT=Path(__file__).with_name('fixtures')/'fx_observed_snapshot.json'

def weights():
    values=json.loads(os.getenv('FX_RECOMMENDATION_WEIGHTS_JSON') or json.dumps(DEFAULT_WEIGHTS))
    if set(values)!=set(DEFAULT_WEIGHTS) or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in values.values()) or sum(values.values())<=0:
        raise ValueError('Invalid FX recommendation weights')
    return values

def comparison(current,reference):
    current=fx.safe_decimal(current);reference=fx.safe_decimal(reference)
    if current is None or reference is None:return None
    power=(reference/current-1)*100;cost=(current/reference-1)*100
    return {'purchasing_power_advantage':str(power),'constant_price_usd_cost_change':str(cost),
        'fx_score':float(min(D(100),max(D(0),power*10))),
        'classification':'favorable' if power>D('0.01') else 'unfavorable' if power<D('-0.01') else 'neutral'}

def summarize(currency,series,period='90D',today=None,fetched_at=None,mode='live'):
    today=today or date.today()
    points=sorted({day:fx.safe_decimal(rate) for day,rate in series if day<=today and fx.safe_decimal(rate)}.items())
    result={'currency':currency,'period':period,'mode':mode,'source':fx.provider.source,'current_rate':None,
        'rate_date':None,'retrieved_at':fetched_at,'stale':True,'comparisons':{},'selected':None,'eligible':False}
    if not points:return result|{'status':'insufficient_data'}
    latest,current=points[-1];stale=(today-latest).days>4
    for name,days in PERIODS.items():
        target=latest-timedelta(days=days)
        rows=[(day,rate) for day,rate in points if 0<=(target-day).days<=7]
        result['comparisons'][name]=comparison(current,rows[-1][1])|{'reference_rate':str(rows[-1][1]),'reference_date':rows[-1][0].isoformat(),'target_date':target.isoformat()} if rows else None
    selected=result['comparisons'][period]
    return result|{'current_rate':str(current),'rate_date':latest.isoformat(),'stale':stale,'selected':selected,
        'eligible':not stale and selected is not None,'status':'stale' if stale else selected['classification'] if selected else 'insufficient_data'}

def intelligence(db,period='90D',mode='live',refresh=True):
    if period not in PERIODS:raise ValueError('Unsupported FX opportunity period')
    if mode not in ('live','historical'):raise ValueError('Unsupported FX intelligence mode')
    snapshot=None
    if mode=='live':
        if refresh:fx.refresh_live(db,fx.CURRENCIES)
        rows=list(db.scalars(select(ExchangeRate).where(ExchangeRate.source=='frankfurter',ExchangeRate.quote=='USD',ExchangeRate.base.in_(fx.CURRENCIES))))
    else:
        snapshot=json.loads(SNAPSHOT.read_text(encoding='utf-8')) if SNAPSHOT.exists() else None
        rows=[]
    markets=[]
    for code in fx.CURRENCIES:
        if mode=='historical':
            series=[(date.fromisoformat(p['date']),p['rate']) for p in (snapshot or {}).get('currencies',{}).get(code,[])]
            today=date.fromisoformat(snapshot['as_of']) if snapshot else date.today()
            stamp=(snapshot or {}).get('retrieved_at')
        else:
            selected=[r for r in rows if r.base==code];series=[(r.rate_date,r.rate) for r in selected]
            today=date.today();stamp=max((r.fetched_at for r in selected),default=None);stamp=stamp.isoformat() if stamp else None
        markets.append(summarize(code,series,period,today,stamp,mode))
    markets.sort(key=lambda r:-(float((r['selected'] or {}).get('purchasing_power_advantage',-1000))))
    signature=hashlib.sha256(json.dumps({'period':period,'mode':mode,'rates':[(r['currency'],r['current_rate'],r['rate_date'],r['stale'],r['selected']) for r in markets]},sort_keys=True).encode()).hexdigest()[:16]
    return {'period':period,'mode':mode,'as_of':(snapshot or {}).get('as_of') if mode=='historical' else date.today().isoformat(),
        'label':'Historical Demonstration Scenario · saved Frankfurter observations' if mode=='historical' else 'Live Market FX · latest available daily references',
        'markets':markets,'favorable_currencies':[r['currency'] for r in markets if r['eligible'] and r['status']=='favorable'],
        'signature':signature,'notice':'Currency context only. Assumes unchanged local price; excludes unknown shipping, tax and payment conversion. Not a product discount, US price comparison or PayPal quote.'}

def cents(amount):return int(amount.quantize(D('1'),rounding=ROUND_HALF_UP))

def product_evidence(product,market,interest,novelty,mode='live'):
    """Listing currency, never search country, selects the applicable FX observation."""
    price=product.get('price_minor');currency=product.get('currency');observed=product.get('price_verified_at')
    fresh=False
    try:
        stamp=datetime.fromisoformat(observed.replace('Z','+00:00')).replace(tzinfo=timezone.utc)
        fresh=timedelta(minutes=-5)<=datetime.now(timezone.utc)-stamp<=timedelta(days=7)
        if mode=='historical' and market and market.get('retrieved_at'):
            saved=datetime.fromisoformat(market['retrieved_at'].replace('Z','+00:00')).replace(tzinfo=timezone.utc)
            fresh=abs(saved-stamp)<=timedelta(days=7)
    except (ValueError,TypeError,AttributeError):pass
    valid=type(price) is int and price>=0 and bool(currency) and bool(product.get('url')) and bool(product.get('source')) and fresh
    enough=bool(valid and market and market['eligible'] and market['currency']==currency)
    selected=(market or {}).get('selected') or {}
    favorable=bool(enough and selected.get('classification')=='favorable' and interest>=40)
    evidence=100 if valid else 45 if observed else 20
    factors={'interest':interest,'fx':selected.get('fx_score',0) if enough else None,'novelty':novelty,'evidence':evidence}
    w=weights();score=round(sum(D(str(factors[k]))*D(str(w[k])) for k in w)/D(str(sum(w.values()))),1) if enough else None
    result={'verified':enough,'favorable':favorable,'listing_fresh':fresh,'period':(market or {}).get('period'),
        'status':'FX-Backed Find' if favorable and mode=='live' else 'Historical FX-Backed Find' if favorable else 'Explore More — FX Benefit Not Verified',
        'score':float(score) if score is not None else None,'factors':factors,'weights':w,'current_usd_minor':None,'historical_usd_minor':None,'difference_usd_minor':None,
        'market':market,'price_observed_at':observed,'price_source':product.get('source'),
        'caveat':'Assumes the same foreign-currency listing price at both rates. Not observed past product prices. Shipping, tax, delivery and payment fees are unverified unless separately evidenced.'}
    if enough:
        unit=D(price)/(1 if currency=='JPY' else 100)
        now=unit*D(market['current_rate'])*100;then=unit*D(selected['reference_rate'])*100
        result.update(current_usd_minor=cents(now),historical_usd_minor=cents(then),difference_usd_minor=cents(then)-cents(now))
    if currency=='USD':result['status']='USD listing · no foreign FX benefit'
    if not fresh:result['status']='Stale or unverified price · FX ranking unavailable'
    return result
