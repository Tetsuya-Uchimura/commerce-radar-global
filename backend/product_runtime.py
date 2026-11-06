"""Bounded, single-flight provider calls with persistent, query-scoped evidence cache."""
from collections import defaultdict
from datetime import datetime,timezone,timedelta
import hashlib,json,logging,os,threading,time
from sqlalchemy import select,func
from .models import AICache,APIUsage

_guard=threading.Lock();_locks=defaultdict(threading.Lock);_failures={};_quota_lock=threading.Lock()
_health={'status':'unchecked','checked_at':None,'error':None};_credential=None
logger=logging.getLogger(__name__)

def status():
    configured=bool(os.getenv('CHANNEL3_API_KEY'))
    return {'provider':'channel3','configured':configured,**(_health if configured else {'status':'unconfigured','checked_at':None,'error':'Live product search unavailable: CHANNEL3_API_KEY is not configured.'})}

def _mark(result):
    global _health
    _health={'status':'unavailable' if result.get('error') else 'available','checked_at':datetime.now(timezone.utc).isoformat(),'error':result.get('error')}

def check_startup(db):
    """One actual generic search, also warming the first statistical coffee query."""
    if not os.getenv('CHANNEL3_API_KEY'):return status()
    result=search(db,1,'coffee brewing equipment artisan beans workshops',None,'channel3',force=True)
    _mark(result)
    return status()

def _limit(name,default):
    try:return max(1,min(10000,int(os.getenv(name,str(default)))))
    except ValueError:return default

def search(db,uid,query,country,provider_name,force=False):
    from . import products
    from .channel3 import provider as channel3
    from .usage import record
    if provider_name=='auto':provider_name='channel3' if os.getenv('CHANNEL3_API_KEY') else 'web'
    query=' '.join(query.strip().split())[:200]
    key='products:'+hashlib.sha256((str(uid)+provider_name+query+str(country)).encode()).hexdigest()
    # Lock includes quota accounting and the upstream call. Waiting callers re-read
    # the committed cache rather than issuing another request (including refresh).
    requested=time.monotonic()
    with _guard:lock=_locks[key]
    with lock:
        db.expire_all();cached=db.get(AICache,key)
        now=datetime.now(timezone.utc)
        age=now-cached.created_at.replace(tzinfo=timezone.utc) if cached else timedelta.max
        def reuse(error=None,stale=False,retry_after=None):
            result=json.loads(cached.content)
            return result|{'cached':True,'stale_cache':stale,'error':error,'retry_after':retry_after,'cache_created_at':cached.created_at.isoformat()}
        if cached and (age<timedelta(hours=4) and not force or cached.created_at.replace(tzinfo=timezone.utc).timestamp()>now.timestamp()-(time.monotonic()-requested)):
            return reuse()
        def failure(error,retry_after=None):
            if cached and age<timedelta(days=7):return reuse(error,age>=timedelta(hours=4),retry_after)
            return {'items':[],'error':error,'source':'Unavailable','cached':False,'retry_after':retry_after}
        if provider_name=='channel3' and not force and _health['status']=='unavailable' and _health['checked_at']:
            if now-datetime.fromisoformat(_health['checked_at'])<timedelta(seconds=60):
                return failure(_health['error'])
        previous=_failures.get(key)
        if previous and not force and time.monotonic()<previous[0]:return failure(previous[1])
        with _quota_lock:
            # Persisted successful AND failed provider attempts count toward limits.
            minute=db.scalar(select(func.count()).select_from(APIUsage).where(APIUsage.user_id==uid,APIUsage.feature=='product_search',APIUsage.created_at>=now-timedelta(minutes=1)))
            day=db.scalar(select(func.count()).select_from(APIUsage).where(APIUsage.user_id==uid,APIUsage.feature=='product_search',APIUsage.created_at>=now-timedelta(days=1)))
            if minute>=_limit('PRODUCT_SEARCH_MAX_PER_MINUTE',6):return failure('Product search minute limit reached. Cached results are preferred.',60)
            if day>=_limit('PRODUCT_SEARCH_MAX_PER_DAY',60):return failure('Product search daily limit reached. Cached results are preferred.')
            wait=2-(time.monotonic()-products._calls.get(uid,0))
            if wait>0:return failure('Product searches are debounced; retry shortly.',max(1,int(wait)+1))
            products._calls[uid]=time.monotonic()
            # Reserve before leaving the lock, so concurrent different queries also
            # respect the cap. Update its status/tokens after the bounded call.
            entry=APIUsage(user_id=uid,feature='product_search',model=provider_name,status='pending',input_tokens=0,output_tokens=0)
            db.add(entry);db.commit()
        adapter={'channel3':channel3,'app_store':products.app_store_provider}.get(provider_name,products.provider)
        try:result=adapter.search(query,country)
        except Exception:
            result={'items':[],'error':'Product provider failed unexpectedly. No product facts were invented.','source':'Unavailable'}
        usage=result.get('usage') or {}
        entry.status='failed' if result.get('error') else 'success'
        entry.input_tokens=int(usage.get('input_tokens',0));entry.output_tokens=int(usage.get('output_tokens',0));db.commit()
        if provider_name=='channel3':_mark(result)
        if result.get('error'):
            _failures[key]=(time.monotonic()+60,result['error'])
            logger.warning('Product provider %s unavailable: %s',provider_name,result['error'])
            return failure(result['error'])
        stored_at=datetime.now(timezone.utc)
        db.merge(AICache(key=key,content=json.dumps(result),created_at=stored_at));db.commit()
        return result|{'cached':False,'cache_created_at':stored_at.isoformat()}

def reset_runtime():
    """Isolated test helper; does not touch persistent data or credentials."""
    global _health
    _failures.clear();_locks.clear();_health={'status':'unchecked','checked_at':None,'error':None}
