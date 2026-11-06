"""One versioned result envelope for automatic cards, recommendations and map evidence."""
import hashlib,json,os
from collections import defaultdict
from . import products,analysis,product_runtime
from .search_plan import build,TERMS

def country_groups(items):
    groups=defaultdict(list);unknown=[]
    for p in items:
        # Only a source-attributed seller-country observation can enter this map.
        code=p.get('merchant_country');evidence=p.get('merchant_country_evidence')
        if code and isinstance(evidence,dict) and evidence.get('source') and evidence.get('observed_at'):
            if not p.get('link_access') or p['link_access']['status'] in ('reachable','user_confirmed'):groups[code].append(p)
        else:unknown.append(p)
    return {'countries':[{'code':code,'score':round(sum(p['recommendation_score'] for p in rows)/len(rows),1),
        'offer_count':len(rows),'complete_count':sum(p.get('estimated_total_usd') is not None for p in rows),
        'basis':'Verified seller-country evidence; average discovery-match score, not delivered value.'} for code,rows in groups.items()],
        'unknown_origin':unknown}

def run(db,uid,body):
    plan=build(db,uid)
    conditions={k:body.get(k) for k in ('query','country','category','budget_minor','kind','excluded_countries','provider','goal')}
    signature=hashlib.sha256(json.dumps({'uid':uid,'plan':plan['signature'],'conditions':conditions},sort_keys=True).encode()).hexdigest()[:20]
    base={'user_id':uid,'version':plan['version'],'analysis_signature':plan['signature'],'signature':signature,
        'search_plan':plan,'items':[],'countries':[],'unknown_origin':[],'provider_status':product_runtime.status(),
        'error':None,'waiting_for_analysis':False,'discarded':False,'cached':False,'recommendation':products.recommendation([])}
    if body.get('expected_signature') and body['expected_signature']!=plan['signature']:
        return base|{'mode':'Discovering','discarded':True}
    if body.get('demo_only'):
        return base|{'mode':'Demo Products','notice':'Sample product data · fictional Demo Catalog.'}
    chosen=body.get('provider') or 'auto'
    if chosen=='auto' and not os.getenv('CHANNEL3_API_KEY'):
        return base|{'mode':'Demo Products','notice':'Sample product data · Live product search unavailable. Configure CHANNEL3_API_KEY for automatic real discovery.'}
    # Let the existing analysis debounce settle before spending on transient queries.
    # A missing key or failed analysis uses the latest statistical features instead.
    if plan['status'] in ('pending','analyzing') and os.getenv('OPENAI_API_KEY') and os.getenv('ANALYSIS_AUTORUN','true').lower()=='true' and product_runtime.status()['status']!='unavailable':
        return base|{'mode':'Discovering','waiting_for_analysis':True,'notice':'Discovering global shopping opportunities...'}
    query=body.get('query') or TERMS.get(body.get('category')) or None
    result=products.explore(db,uid,query,body.get('country'),chosen,body.get('goal') or 'best',body.get('budget_minor'),body.get('excluded_countries'),body.get('kind') or 'any',bool(body.get('refresh')))
    # DB state may have changed during a provider call; never label old work current.
    db.expire_all();latest=build(db,uid)
    if latest['signature']!=plan['signature']:
        return base|{'mode':'Discovering','discarded':True,'version':latest['version'],'analysis_signature':latest['signature']}
    error=result.get('error')
    cached=bool(result.get('cached'))
    if cached and not error:error=product_runtime.status().get('error') if chosen in ('auto','channel3') else None
    if error and not result['items']:
        return base|{'mode':'Demo Products','error':error,'retry_after':result.get('retry_after'),
            'notice':'Live product search unavailable. Sample product data is displayed separately as Demo Products.'}
    mode='Cached Real Products' if cached else 'Real Products'
    def observed(p,field):
        evidence=p.get(field+'_evidence') or {}
        return p.get(field) if isinstance(evidence,dict) and evidence.get('source') and evidence.get('observed_at') else None
    items=[dict(p,data_source='Cached Product' if cached else 'Real Product',
        seller_country=observed(p,'merchant_country'),ship_from_country=observed(p,'ship_from_country'),
        delivery_countries=observed(p,'delivery_countries')) for p in result['items']]
    grouped=country_groups(items)
    return base|{'mode':mode,'items':items,**grouped,'cached':cached,'error':error,
        'retry_after':result.get('retry_after') or (3 if any(p.get('link_access',{}).get('pending') for p in items) else None),'stale_cache':result.get('stale_cache',False),
        'query':result.get('query'),'source':result.get('source'),'provider_status':product_runtime.status(),
        'recommendation':result['recommendation'],
        'notice':('No products match these search conditions. You can switch to Demo Products.' if not items else
            'Seller location, shipping origin, currency and delivery countries are separate facts. Origin Unknown items do not contribute to map scores.')}
