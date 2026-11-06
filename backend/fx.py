"""Frankfurter v2: USD per foreign unit; observations are never interpolated."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
import threading,time
import httpx
from sqlalchemy import select
from .models import ExchangeRate,DemoScenario
from .config import DEMO_DATE
D=Decimal
CURRENCIES=['EUR','GBP','JPY','CAD','AUD','CHF','SEK','SGD']
fx_lock=threading.Lock()
_range_requests={}
_failed_requests={}


def safe_decimal(value):
    try:
        x=D(str(value));return x if x.is_finite() and x>0 else None
    except (InvalidOperation,ValueError):return None


def purchasing_power(current,historical):
    if not safe_decimal(current) or not safe_decimal(historical):return None
    return (D(str(historical))/D(str(current))-1)*100


def summarize(currency,series,source,fetched_at=None,today=None):
    today=today or date.today()
    valid=sorted({day:safe_decimal(rate) for day,rate in series if safe_decimal(rate)}.items())
    if not valid:return {'currency':currency,'quote':'USD','rate':None,'source':source,'stale':True,'warning':'No valid daily observations.','fx_score':None,'history':[]}
    latest,current=valid[-1]
    def previous(days):
        target=latest-timedelta(days=days)
        rows=[r for day,r in valid if 0<=(target-day).days<=7]
        return rows[-1] if rows else None
    baseline=[r for day,r in valid if latest-timedelta(days=90)<=day<latest]
    mean=sum(baseline)/len(baseline) if len(baseline)>=30 and previous(90) else None
    advantage=purchasing_power(current,mean)
    stale=(today-latest).days>4 and source!='Synthetic Demo FX'
    result={'currency':currency,'quote':'USD','direction':f'1 {currency} in USD','rate':str(current),
        'inverse_rate':str(1/current),'rate_date':latest.isoformat(),'power_vs_90_average':str(advantage) if advantage is not None else None,
        'fx_score':round(float(max(D(0),min(D(100),50+advantage*D('2.5')))),1) if advantage is not None else None,
        'source':source,'last_updated':fetched_at,'stale':stale,
        'warning':'Synthetic scenario, not market FX.' if source=='Synthetic Demo FX' else 'Daily market observation is older than 4 days.' if stale else 'Latest available daily reference, not PayPal conversion rates.',
        'history':[{'date':day.isoformat(),'rate':str(rate)} for day,rate in valid]}
    for n in (30,90,365):result[f'change_{n}']=str(purchasing_power(current,previous(n))) if previous(n) else None
    return result


class FrankfurterProvider:
    source='Frankfurter v2 · Latest Available Daily FX Rate'
    def fetch(self,currencies,start=None):
        start=start or date.today()-timedelta(days=374)
        def one(currency):
            try:
                with httpx.Client(timeout=15,follow_redirects=False) as client:
                    response=client.get('https://api.frankfurter.dev/v2/rates',params={'base':'USD','quotes':currency,'from':start.isoformat(),'to':date.today().isoformat()})
                    response.raise_for_status();rows=response.json()
                if not isinstance(rows,list):return []
                parsed=[]
                for row in rows:
                    rate=safe_decimal(row.get('rate'));day=date.fromisoformat(row['date'])
                    if row.get('base','').upper()=='USD' and row.get('quote','').upper()==currency and rate and day<=date.today():
                        parsed.append((currency,day,1/rate))
                return parsed
            except (httpx.HTTPError,ValueError,TypeError,KeyError):return []
        with ThreadPoolExecutor(max_workers=4) as pool:return [row for rows in pool.map(one,currencies) for row in rows]


provider=FrankfurterProvider()


def refresh_live(db,currencies,force=False,start=None):
    with fx_lock:
        request_key=(tuple(sorted(currencies)),str(start))
        failure_key=(id(db.get_bind()),request_key)
        if not force and time.monotonic()-_failed_requests.get(failure_key,-1000)<60:return False
        if start is not None and not force and time.monotonic()-_range_requests.get(request_key,0)<21600:return False
        cached=list(db.scalars(select(ExchangeRate).where(ExchangeRate.source=='frankfurter',ExchangeRate.quote=='USD',ExchangeRate.base.in_(currencies))))
        now=datetime.now(timezone.utc)
        complete=all(any(r.base==c for r in cached) for c in currencies)
        covered=start is None or all(min((r.rate_date for r in cached if r.base==c),default=date.today())<=start+timedelta(days=7) for c in currencies)
        # Old long-range chart rows must not invalidate a freshly retrieved daily
        # window and force eight network requests on every profile read.
        latest_fetches=[max((r.fetched_at.replace(tzinfo=timezone.utc) for r in cached if r.base==code),default=datetime.min.replace(tzinfo=timezone.utc)) for code in currencies]
        if not force and complete and covered and min(latest_fetches)>now-timedelta(hours=6):return False
        rows=provider.fetch(currencies,start) if start else provider.fetch(currencies)
        for currency,day,rate in rows:
            item=db.scalar(select(ExchangeRate).where(ExchangeRate.base==currency,ExchangeRate.quote=='USD',ExchangeRate.rate_date==day,ExchangeRate.source=='frankfurter'))
            if item is None:item=ExchangeRate(base=currency,quote='USD',rate_date=day,source='frankfurter');db.add(item)
            item.rate=str(rate);item.fetched_at=now
        db.commit()
        if rows:_range_requests[request_key]=time.monotonic()
        else:_failed_requests[failure_key]=time.monotonic()
        return bool(rows)


def bundle(db,mode='live',scenario='balanced',adjustment=0):
    updated=refresh_live(db,CURRENCIES) if mode=='live' else False
    live=list(db.scalars(select(ExchangeRate).where(ExchangeRate.source=='frankfurter',ExchangeRate.quote=='USD'))) if mode=='live' else []
    demo=list(db.scalars(select(ExchangeRate).where(ExchangeRate.source=='synthetic')))
    aliases={'strong-usd':'strong-yen','weak-usd':'weak-yen'}
    scen=db.get(DemoScenario,scenario) or db.get(DemoScenario,aliases.get(scenario,scenario))
    multiplier=D(scen.current_multiplier if scen else '1')*(1+D(str(adjustment))/100)
    rates={};covered={r.base for r in live}
    for code in CURRENCIES:
        real=[r for r in live if r.base==code]
        rows=real or [r for r in demo if r.base==('USD' if code=='JPY' else code)]
        series=[]
        for r in rows:
            value=D(r.rate)
            if not real:
                value=1/value if code=='JPY' else value/D('145')
                value*=1+(multiplier-1)*max(D(0),1-D((DEMO_DATE-r.rate_date).days)/90)
            series.append((r.rate_date,value))
        fetched=max((r.fetched_at for r in rows),default=None)
        summary=summarize(code,series,provider.source if real else 'Synthetic Demo FX',fetched.isoformat() if fetched else None)
        summary['history']=summary['history'][-100:]
        rates[code]=summary
    rates['USD']={'currency':'USD','quote':'USD','direction':'1 USD = 1 USD','rate':'1','inverse_rate':'1','fx_score':50,'source':'USD identity','stale':False,'warning':'Base currency; no conversion.','rate_date':date.today().isoformat(),'last_updated':None,'change_30':'0','change_90':'0','change_365':'0','power_vs_90_average':'0','history':[]}
    effective=('live' if updated else 'cached') if len(covered)==len(CURRENCIES) else 'mixed' if covered else 'demo'
    warning=None
    if mode=='live' and len(covered)<len(CURRENCIES):warning='FX retrieval unavailable for some currencies. Labelled synthetic fallback is used; check each source.'
    elif mode=='live' and not updated:warning='Using cached daily market observations. Last successful retrieval is shown; use Refresh FX to retry.'
    return {'requested_mode':mode,'effective_mode':effective,'cache_used':bool(covered) and not updated,'scenario':scenario,'adjustment_percent':adjustment,'warning':warning,'rates':rates,'assumption':'Foreign sticker prices assumed fixed. Market FX is not a PayPal conversion quote.'}


def chart(db,currency,period='1Y',force=False):
    days={'1M':31,'3M':93,'6M':186,'1Y':374,'5Y':1835,'MAX':None}[period]
    start=date.today()-timedelta(days=days) if days else date(1948,1,1)
    updated=refresh_live(db,[currency],force,start)
    rows=list(db.scalars(select(ExchangeRate).where(ExchangeRate.base==currency,ExchangeRate.quote=='USD',ExchangeRate.source=='frankfurter',ExchangeRate.rate_date>=start).order_by(ExchangeRate.rate_date)))
    result=summarize(currency,[(r.rate_date,D(r.rate)) for r in rows],provider.source,max((r.fetched_at for r in rows),default=None).isoformat() if rows else None)
    fresh=bool(rows) and max(r.fetched_at.replace(tzinfo=timezone.utc) for r in rows)>datetime.now(timezone.utc)-timedelta(hours=6)
    history=result['history'];result.update({'period':period,'cache_used':not updated,'error':None if updated or fresh and not force else 'Provider retrieval unavailable; cached observations are shown.' if rows else 'FX provider unavailable. No market observations available.','period_start':history[0]['date'] if history else None,
        'high':str(max(D(p['rate']) for p in history)) if history else None,'low':str(min(D(p['rate']) for p in history)) if history else None,
        'period_change':str(purchasing_power(history[-1]['rate'],history[0]['rate'])) if history else None})
    return result


def indexed(series):
    """Common observed baseline; never interpolate or forward-fill missing dates."""
    nonempty={code:rows.get('history',[]) for code,rows in series.items() if rows.get('history')}
    if len(nonempty)<2:return []
    common=set.intersection(*({p['date'] for p in rows} for rows in nonempty.values()))
    if not common:return []
    first_day=min(common)
    result={}
    for code,points in nonempty.items():
        first=D(next(p['rate'] for p in points if p['date']==first_day))
        for point in points:
            if point['date']>=first_day:result.setdefault(point['date'],{'date':point['date']})[code]=str(first/D(point['rate'])*100)
    return [result[day] for day in sorted(result)]
