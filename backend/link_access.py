"""Bounded public-link checks. No cookies, credentials, browser spoofing or block bypass."""
from concurrent.futures import ThreadPoolExecutor,wait
from datetime import datetime,timezone,timedelta
import hashlib,ipaddress,json,re,socket,threading,time
from urllib.parse import urlparse,urljoin
import httpcore
from sqlalchemy.dialects.sqlite import insert
from .models import AICache

_pool=ThreadPoolExecutor(max_workers=6,thread_name_prefix='product-link')
_guard=threading.Lock();_pending={}
LIMIT=49152
NOTICE='Server-side observation only. Your region, browser, login and store rules can produce a different result. No purchase availability guarantee.'

class UnsafeLink(ValueError):pass

def public_ip(value):
    address=ipaddress.ip_address(value)
    return address.is_global and not address.is_multicast and not address.is_reserved

def public_url(url):
    try:
        p=urlparse(str(url));host=(p.hostname or '').lower()
        if p.scheme not in ('http','https') or p.username or p.password or not host or '.' not in host:raise UnsafeLink()
        if p.port not in (None,80 if p.scheme=='http' else 443):raise UnsafeLink()
        if host.endswith(('.local','.internal','.test','.example')) or host=='metadata.google.internal':raise UnsafeLink()
        try:
            if not public_ip(host):raise UnsafeLink()
        except ValueError as e:
            if isinstance(e,UnsafeLink):raise
        return str(url)
    except (ValueError,TypeError):raise UnsafeLink('Non-public or unsafe URL') from None

class PublicNetwork(httpcore.SyncBackend):
    def connect_tcp(self,host,port,timeout=None,local_address=None,socket_options=None):
        if port not in (80,443):raise UnsafeLink('Port blocked')
        addresses=list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)))
        if not addresses or any(not public_ip(a) for a in addresses):raise UnsafeLink('Non-public DNS result')
        addresses.sort(key=lambda address:ipaddress.ip_address(address).version)
        # Pin the actual TCP destination to a validated address. TLS SNI/certificate
        # verification and Host still use the original URL hostname in httpcore.
        return super().connect_tcp(addresses[0],port,timeout,local_address,socket_options)

def result(status,reason,**extra):
    return {'status':status,'reason':reason,'checked_at':datetime.now(timezone.utc).isoformat(),'scope':'server','limitation':NOTICE,**extra}

def classify(url,status,headers,body):
    text=body.decode('utf-8',errors='ignore').lower()
    path=urlparse(url).path.lower()
    if status==401:return ('login_required','The server requires authentication.')
    if status==403:return ('restricted','The store denied this server request (HTTP 403).')
    if status==429:return ('rate_limited','The store rate-limited this request (HTTP 429).')
    if status in (404,410):return ('unavailable','The destination page was not found or removed.')
    if status>=400:return ('unavailable','The destination returned an HTTP error.')
    if not 200<=status<300:return ('unconfirmed','No successful final page response.')
    if path.endswith('/disabled.html') or re.search(r'<(?:title|h1)[^>]*>\s*(?:disabled|page not found)\s*</',text):
        return ('unavailable','The redirect destination is a disabled/error page.')
    if re.search(r'<(?:title|h1)[^>]*>\s*(?:access denied|just a moment)[^<]*</',text):
        return ('restricted','An access-denied or browser-challenge page was returned.')
    if any(s in text for s in ('due to website restrictions we are unable to display','sorry, you have been blocked','verify you are human',"verify you're human",'verify you&#039;re human','checking your browser before accessing')) or ('quick security check' in text and 'cf-turnstile' in text):
        return ('restricted','A restriction or browser-verification page was returned.')
    if any(s in path for s in ('/login','/signin','/sign-in')):
        return ('login_required','The link redirected to a sign-in page.')
    host=urlparse(url).hostname or ''
    if host=='buy.trychannel3.com' or host=='affinity.net' or host.endswith('.affinity.net'):
        return ('unconfirmed','A tracking/interstitial page responded; the final store page was not confirmed.')
    if path in ('','/'):
        return ('unconfirmed','A homepage responded; the requested product page was not confirmed.')
    return ('reachable','A successful page response was observed from this server.')

def probe(url):
    current=url;started=time.monotonic();redirects=0
    try:
        with httpcore.ConnectionPool(network_backend=PublicNetwork(),max_connections=1,retries=0) as pool:
            while redirects<=4:
                current=public_url(current)
                remaining=8-(time.monotonic()-started)
                if remaining<=0:return result('unconfirmed','Link-check time limit reached.')
                timeout=min(2,remaining)
                with pool.stream('GET',current,headers=[(b'User-Agent',b'CommerceRadar-LinkCheck/1.0'),(b'Accept',b'text/html,application/xhtml+xml')],extensions={'timeout':dict(connect=timeout,read=timeout,write=timeout,pool=timeout)}) as response:
                    headers={k.decode('ascii',errors='ignore').lower():v.decode('latin-1') for k,v in response.headers}
                    if response.status in (301,302,303,307,308):
                        location=headers.get('location')
                        if not location:return result('unconfirmed','Redirect had no destination.',http_status=response.status)
                        current=public_url(urljoin(current,location));redirects+=1;continue
                    # Read a small prefix only, to recognize HTTP-200 error pages.
                    content=b''
                    if 'gzip' not in headers.get('content-encoding',''):
                        for chunk in response.iter_stream():
                            content+=chunk[:LIMIT-len(content)]
                            if len(content)>=LIMIT or time.monotonic()-started>=8:break
                    status,reason=classify(current,response.status,headers,content)
                    if headers.get('content-encoding') and status=='reachable':status,reason='unconfirmed','Encoded page responded; content could not be checked.'
                    return result(status,reason,http_status=response.status,final_host=urlparse(current).hostname,redirects=redirects)
            return result('unconfirmed','Redirect limit reached; destination was not confirmed.')
    except UnsafeLink:return result('unsafe','Unsafe URL or non-public redirect was blocked.')
    except (httpcore.TimeoutException,TimeoutError):return result('unconfirmed','The destination timed out.')
    except (httpcore.NetworkError,httpcore.ProtocolError,OSError,ValueError):return result('unconfirmed','The destination could not be verified from this server.')

def attach(db,items,force=False):
    """Global URL cache; worker threads do not touch SQLAlchemy sessions."""
    now=datetime.now(timezone.utc);ready={};futures={};keys={}
    def save(url,data):
        key='link-v1:'+hashlib.sha256(url.encode()).hexdigest()
        stmt=insert(AICache).values(key=key,content=json.dumps(data),created_at=datetime.now(timezone.utc))
        db.execute(stmt.on_conflict_do_update(index_elements=['key'],set_={'content':stmt.excluded.content,'created_at':stmt.excluded.created_at}))
    # Harvest late completions, including URLs not requested again, so the bounded
    # in-flight registry cannot fill up with completed work.
    with _guard:
        finished=[(url,f) for url,f in _pending.items() if f.done()]
    for url,future in finished:
        try:save(url,future.result())
        except Exception:pass
        with _guard:
            if _pending.get(url) is future:_pending.pop(url,None)
    if finished:db.commit();db.expire_all()
    for item in items[:20]:
        url=item.get('url','');key='link-v1:'+hashlib.sha256(url.encode()).hexdigest();keys[url]=key
        try:public_url(url)
        except UnsafeLink:
            ready[url]=result('unsafe','Unsafe destination URL was blocked.');continue
        cached=db.get(AICache,key)
        from .merchant_access import decision,manual_mode
        policy=decision(item.get('merchant'))
        if policy and policy['decision']=='allow':
            previous=json.loads(cached.content) if cached else None
            if previous and previous['status'] in ('unsafe','unavailable'):
                ready[url]=previous|{'cached':True};continue
            ready[url]={'status':'user_confirmed','reason':'User confirmed a representative merchant product link in their browser. Other products and future access are not guaranteed.',
                'checked_at':policy['reviewed_on'],'scope':'user','limitation':policy['scope'],
                'source':policy['source'],'merchant_domain':policy['matched_domain'],'server_observation':previous}
            continue
        if manual_mode():
            previous=json.loads(cached.content) if cached else None
            ready[url]=previous|{'cached':True} if previous and previous['status'] in ('unsafe','unavailable') else {
                'status':'user_pending','reason':'This merchant has not been reviewed by the user. No automated link request was made.',
                'checked_at':'','scope':'pending_user_review','limitation':'Awaiting user browser review.'}
            continue
        if cached:
            data=json.loads(cached.content);age=now-cached.created_at.replace(tzinfo=timezone.utc)
            ttl=timedelta(hours=6 if data['status']=='reachable' else 1 if data['status'] in ('restricted','unavailable','login_required') else .08)
            if age<ttl and (not force or age<timedelta(seconds=30)):
                ready[url]=data|{'cached':True};continue
        with _guard:
            future=_pending.get(url)
            if future is None and len(_pending)<60:
                future=_pool.submit(probe,url);_pending[url]=future
            if future:futures[url]=future
    if futures:wait(set(futures.values()),timeout=10)
    for url,future in futures.items():
        if future.done():
            try:data=future.result()
            except Exception:data=result('unconfirmed','Link check could not be completed.')
            ready[url]=data|{'cached':False}
            save(url,data)
            with _guard:
                if _pending.get(url) is future:_pending.pop(url,None)
        else:ready[url]=result('unconfirmed','Link check is still pending; the result will update automatically.',pending=True)
    db.commit();db.expire_all()
    return [dict(p,link_access=ready.get(p.get('url'),result('unconfirmed','Link-check capacity limit; destination not verified.'))) for p in items]
