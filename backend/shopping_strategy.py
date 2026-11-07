"""Deterministic shopping-search priorities. Never a cheapest-market verdict."""
from datetime import datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
import hashlib,json,os
from .models import AICache,ChatState

PRIORITIES=('auto','domestic','overseas','compare')
LABELS={'explore_overseas':'Explore Overseas','us_stores_first':'US Stores First','compare_both':'Compare Both'}

def thresholds():
    defaults={'neutral_percent':'0.5','meaningful_percent':'1','minimum_difference_usd':'1','minimum_interest':'40'}
    values={}
    for key,default in defaults.items():
        try:
            v=Decimal(os.getenv('STRATEGY_'+key.upper(),default))
            if not v.is_finite() or v<0:raise ValueError('Invalid strategy threshold')
        except InvalidOperation:raise ValueError('Invalid strategy threshold')
        values[key]=v
    if values['neutral_percent']>values['meaningful_percent'] or values['minimum_interest']>100:raise ValueError('Invalid strategy threshold ordering')
    return values

def preferences(db,uid,body=None):
    row=db.get(ChatState,uid)
    saved=json.loads(row.conditions_json) if row else {}
    explicit=(body or {}).get('shopping_priority')
    return explicit if explicit in PRIORITIES else saved.get('shopping_priority','auto') if saved.get('shopping_priority','auto') in PRIORITIES else 'auto'

def set_preference(db,uid,priority):
    if priority not in PRIORITIES:raise ValueError('Unsupported shopping priority')
    row=db.get(ChatState,uid)
    if not row:row=ChatState(user_id=uid,conditions_json='{}',messages_json='[]');db.add(row)
    conditions=json.loads(row.conditions_json)
    if priority=='auto':conditions.pop('shopping_priority',None)
    else:conditions['shopping_priority']=priority
    # These are search targets, not merchant-country facts. Clear incompatible
    # previous targets when the user deliberately changes shopping priority.
    for key in ('country','listing_currency','search_query','last_results'):conditions.pop(key,None)
    row.conditions_json=json.dumps(conditions);db.commit()

def observed_market(p,as_of=None):
    proof=p.get('storefront_market_evidence') or {}
    if p.get('storefront_market')!='US' or not isinstance(proof,dict):return None
    from .products import safe_url
    try:
        stamp=datetime.fromisoformat(proof.get('observed_at','').replace('Z','+00:00'))
        stamp=stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
        reference=datetime.fromisoformat(as_of).replace(tzinfo=timezone.utc)+timedelta(days=1,microseconds=-1) if as_of else datetime.now(timezone.utc)
        fresh=timedelta(minutes=-5)<=reference-stamp<=timedelta(days=30)
    except (ValueError,TypeError,AttributeError):return None
    return 'US' if safe_url(proof.get('source')) and fresh and proof.get('basis') else None

def decide(plan,items,conditions=None):
    """Pure decision: provided numerical FX/product evidence is the only input."""
    from .fx_opportunities import display_label
    conditions=conditions or {};limits=thresholds();intel=plan['fx_intelligence']
    historical_day=intel['as_of'] if intel['mode']=='historical' else None
    us_market=lambda p:observed_market(p,historical_day)
    scores=plan.get('category_scores',{})
    primary=conditions.get('category') or max(scores,key=lambda c:(scores[c],c),default='Your interests')
    selected_currency=conditions.get('listing_currency')
    markets=[m for m in intel['markets'] if m.get('eligible') and m.get('selected') and (not selected_currency or selected_currency=='USD' or m['currency']==selected_currency)]
    meaningful=[m for m in markets if Decimal(m['selected']['purchasing_power_advantage'])>limits['meaningful_percent']]
    relevant=[]
    for p in items:
        if (p.get('link_access') or {}).get('status') in ('unsafe','unavailable'):continue
        interest=(p.get('score_factors') or {}).get('interest',0)
        if primary in scores and primary not in p.get('matched_categories',[]):continue
        if Decimal(str(interest))<limits['minimum_interest']:continue
        relevant.append(p)
    strong=[]
    for p in relevant:
        f=p.get('fx_opportunity') or {};market=f.get('market') or {};comparison=market.get('selected') or {}
        applicable=next((m for m in markets if m['currency']==p.get('currency')),None)
        same_reference=applicable and market.get('current_rate')==applicable.get('current_rate') and comparison.get('reference_rate')==applicable['selected'].get('reference_rate')
        if same_reference and f.get('verified') and f.get('listing_fresh') and f.get('difference_usd_minor') is not None and market.get('eligible') and not market.get('stale'):
            if Decimal(comparison.get('purchasing_power_advantage','0'))>limits['meaningful_percent'] and Decimal(f['difference_usd_minor'])>=limits['minimum_difference_usd']*100:
                strong.append(p)
    us=[p for p in relevant if us_market(p)=='US']
    marginal=any(Decimal(m['selected']['purchasing_power_advantage'])>limits['neutral_percent'] for m in markets)
    if strong:
        computed='explore_overseas';codes=['strong_personal_interest','meaningful_fx_advantage','observed_foreign_currency_listing','meaningful_absolute_difference']
        summary=f'Your {primary.lower()} interests align with observed foreign-currency listings and a meaningful FX movement. Explore these sources while checking final purchase conditions.'
    elif markets and not marginal:
        computed='us_stores_first';codes=['no_compelling_foreign_fx_advantage','verified_us_storefront' if us else 'domestic_search_suggestion_only']
        summary=f'Start with US shopping sources for {primary.lower()}. The selected FX evidence does not provide a strong reason to prioritize foreign-currency listings; this does not establish that US prices are lower.'
    else:
        computed='compare_both';codes=['missing_fx_history' if not markets else 'insufficient_relevant_price_evidence' if meaningful else 'marginal_or_mixed_fx']
        summary=f'Compare US and international sources for {primary.lower()}. Currency or product-price evidence does not support a stronger shopping priority yet.'
    priority=conditions.get('shopping_priority','auto')
    chosen={'domestic':'us_stores_first','overseas':'explore_overseas','compare':'compare_both'}.get(priority,computed)
    override=priority!='auto'
    if override:
        codes=['user_selected_priority',*codes]
        summary=f'You chose {LABELS[chosen].lower()} for {primary.lower()}. The automatic assessment is {LABELS[computed]}; your preference changes search priority without creating an FX or price advantage.'
    ranked=sorted(strong,key=lambda p:-(p.get('fx_recommendation_score') or 0))
    currencies=list(dict.fromkeys(p['currency'] for p in ranked))
    if chosen=='us_stores_first':currencies=['USD']
    elif not currencies:currencies=[m['currency'] for m in meaningful[:2]] if chosen=='explore_overseas' else list(dict.fromkeys(['USD',*([selected_currency] if selected_currency and selected_currency!='USD' else [m['currency'] for m in meaningful[:2]])]))
    title=(f'Explore {", ".join(currencies) or "foreign-currency"}-priced {primary.lower()}' if chosen=='explore_overseas' else f'Start with US shopping sources for {primary.lower()}' if chosen=='us_stores_first' else f'Compare US and international {primary.lower()} sources')
    candidates=us if chosen=='us_stores_first' else ranked if chosen=='explore_overseas' and ranked else relevant
    sources=[];seen=set()
    from .products import safe_url
    for p in candidates:
        url=safe_url(p.get('url'))
        if not url or p.get('merchant') in seen:continue
        # A domestic site recommendation needs affirmative US-market evidence.
        if chosen=='us_stores_first' and us_market(p)!='US':continue
        seen.add(p.get('merchant'))
        f=p.get('fx_opportunity') or {}
        sources.append({'merchant':p.get('merchant') or 'Unknown merchant','product':p['name'],'product_id':p['id'],
            'currency':p.get('currency'),'price_minor':p.get('price_minor'),'price_observed_at':p.get('price_verified_at'),
            'url':url,'source':p.get('source'),'storefront_market':us_market(p),'storefront_market_evidence':p.get('storefront_market_evidence'),
            'seller_country':p.get('seller_country'),'link_access':p.get('link_access'),
            'basis':['personal_interest_match',*(['observed_price_and_currency'] if p.get('price_minor') is not None and p.get('currency') else []),*(['meaningful_currency_context'] if p in strong else []),*(['verified_us_storefront'] if us_market(p)=='US' else [])],
            'evidence_status':'observed_listing' if f.get('listing_fresh') else 'incomplete_or_stale',
            'fx_evidence':f if f.get('verified') else None})
        if len(sources)==3:break
    limitations=['Search priority, not proof of the cheapest market.','Shipping, tax, seller origin and payment costs remain unknown unless separately evidenced.']
    if not sources:limitations.insert(0,'No suitable shopping site is verified yet; use the suggested search, not an invented merchant.')
    if intel['mode']=='historical':limitations.insert(0,f'Historical demonstration: saved observations as of {intel["as_of"]}, not current market conditions.')
    result={'strategy':chosen,'calculated_strategy':computed,'display_name':LABELS[chosen],'title':title,'summary':summary,
        'home_country':'US','home_currency':'USD','fx_period':intel['period'],'fx_mode':intel['mode'],'as_of':intel['as_of'],
        'primary_interest':primary,'recommended_currencies':currencies,'reason_codes':codes,
        'recommended_sources':sources,'evidence_status':'partial' if sources else 'search_suggestion',
        'limitations':limitations,'shopping_priority':priority,'user_override':override,
        'next_action':'explore_products' if chosen=='explore_overseas' else 'search_us_sources' if chosen=='us_stores_first' else 'compare_markets',
        'thresholds':{k:str(v) for k,v in limits.items()},'fx_signature':intel['signature'],'analysis_version':plan['version'],
        'context':context(conditions),
        'analysis_signature':plan['signature'],'evidence_count':len(relevant),'meaningful_product_ids':[p['id'] for p in ranked],
        'fx_evidence':[{'currency':m['currency'],'rate_date':m['rate_date'],'reference_date':m['selected']['reference_date'],'purchasing_power_advantage':m['selected']['purchasing_power_advantage'],
            'display_label':display_label(m,any(p['currency']==m['currency'] for p in strong))} for m in markets]}
    fingerprint=json.loads(json.dumps(result))
    for source in fingerprint['recommended_sources']:
        if source.get('link_access'):source['link_access'].pop('cached',None)
        if source.get('fx_evidence') and source['fx_evidence'].get('market'):source['fx_evidence']['market'].pop('retrieved_at',None)
    result['signature']=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()[:24]
    return result

def store(db,uid,strategy):
    strategy=dict(strategy,user_id=uid)
    strategy['signature']=hashlib.sha256((str(uid)+strategy['signature']).encode()).hexdigest()[:24]
    key=f'strategy:{uid}:{strategy["signature"]}'
    if db.get(AICache,key) is None:
        from sqlalchemy.dialects.sqlite import insert
        db.execute(insert(AICache).values(key=key,content=json.dumps(strategy)).on_conflict_do_nothing(index_elements=['key']));db.commit()
    return strategy

def current(db,uid,plan,items,conditions=None):
    conditions=dict(conditions or {});conditions['shopping_priority']=preferences(db,uid,conditions)
    return store(db,uid,decide(plan,items,conditions))

def context(values):
    excluded=values.get('excluded_countries') or []
    if isinstance(excluded,str):excluded=excluded.split(',')
    return {'category':values.get('category') or None,'country':values.get('country') or None,
        'listing_currency':values.get('listing_currency') or None,
        'budget_minor':values.get('budget_minor') if values.get('budget_minor') is not None else values.get('max_budget'),
        'kind':values.get('kind') or ('digital' if values.get('digital_only') else 'physical' if values.get('physical_only') else 'any'),
        'excluded_countries':sorted(c for c in excluded if c),
        'shopping_priority':values.get('shopping_priority') or 'auto'}

def market_sections(items,as_of=None):
    items=[p for p in items if (p.get('link_access') or {}).get('status') not in ('unsafe','unavailable')]
    return {'us_storefronts':[p for p in items if observed_market(p,as_of)=='US'],
        'foreign_currency_listings':[p for p in items if p.get('currency') not in (None,'USD') and observed_market(p,as_of)!='US'],
        'unverified_market':[p for p in items if observed_market(p,as_of)!='US' and p.get('currency') in (None,'USD')]}

def cached_strategy(db,uid,signature):
    from . import analysis
    row=db.get(AICache,f'strategy:{uid}:{signature}')
    if not row or datetime.now(timezone.utc)-row.created_at.replace(tzinfo=timezone.utc)>timedelta(hours=6):return None
    value=json.loads(row.content)
    if analysis.state(db,uid).version!=value['analysis_version']:return None
    from .search_plan import build
    if build(db,uid,value['fx_period'],value['fx_mode'])['signature']!=value['analysis_signature']:return None
    return value

def explanation(db,uid,signature):
    value=cached_strategy(db,uid,signature)
    if value is None:return None
    from .ai import explain
    fallback=value['summary']+(' Suggested sources: '+', '.join(s['merchant'] for s in value['recommended_sources'][:2])+'.' if value['recommended_sources'] else '')
    answer=explain(db,f'user:{uid}','Explain this deterministic shopping strategy in two or three short sentences, at most 65 words. Do not change the strategy, compute new numbers, invent stores, infer seller location from currency, or claim cheapest/delivered savings. Distinguish user override and historical observations. Use only supplied source evidence and state relevant unknowns.',{'strategy':value},fallback)
    if len(answer['explanation'].split())>75:
        answer={'explanation':value['summary'],'source':'Deterministic strategy · concise fallback','limitation':'Search priority only; final purchase costs unverified.'}
    return answer|{'strategy_signature':signature}
