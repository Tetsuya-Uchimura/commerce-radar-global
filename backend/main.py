"""Consumer-only Global Opportunity Discovery API."""
from contextlib import asynccontextmanager
import secrets
import time
from typing import Literal
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session as DBSession
from .config import APP_URL, DEMO_MODE, DEMO_DATE
from .db import init_db, get_db, Session
from .models import User, Purchase, Offer, Product, Country, InterestProfile, SavedOpportunity, DemoScenario, AnalysisState, PaymentOrder
from .seed import seed, CATEGORIES, PERSONAS
from .migration import import_legacy
from . import fx, discovery, checkout
from .ai import explain
from .paypal import paypal, PaymentError
from .concierge import resolve_actions
from . import analysis
from .history import PurchaseInput,validated,editable
from .us_migration import migrate_us


@asynccontextmanager
async def lifespan(app):
    init_db()
    with Session() as db:
        seed(db)
        import_legacy(db)
        migrate_us(db)
        for job in db.scalars(select(AnalysisState).where(AnalysisState.status=='analyzing')):
            job.status='pending'
        db.commit()
        from .product_runtime import check_startup
        check_startup(db)
    yield


app=FastAPI(title='Commerce Radar — AI Shopping Strategy Engine',version='3.1.0',lifespan=lifespan,
    dependencies=[Depends(APIKeyHeader(name='X-Commerce-Radar',auto_error=False))],
    description='Local synthetic shopping discovery demo. Set X-Commerce-Radar to 1 via Authorize for writes; create a demo session first.')
app.add_middleware(CORSMiddleware,allow_origins=[APP_URL],allow_credentials=True,
    allow_methods=['GET','POST'],allow_headers=['Content-Type','X-Commerce-Radar'])
sessions={}


@app.middleware('http')
async def write_guard(request:Request,call_next):
    if request.method=='POST':
        if request.headers.get('X-Commerce-Radar')!='1':
            return JSONResponse({'detail':'Missing same-origin request marker.'},status_code=403)
        if request.headers.get('origin') not in (None,APP_URL,'http://127.0.0.1:8000','http://localhost:8000'):
            return JSONResponse({'detail':'Origin not allowed.'},status_code=403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response


@app.exception_handler(PaymentError)
async def payment_error(request,exc):
    return JSONResponse({'detail':exc.message},status_code=exc.code)


def principal(request:Request,db:DBSession=Depends(get_db)):
    session=sessions.get(request.cookies.get('radar_session',''))
    if not session or session[1]<time.monotonic():raise HTTPException(401,'Choose a demo persona to start.')
    user=db.get(User,session[0])
    if not user:raise HTTPException(401,'Session expired.')
    return user


class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid')


class Persona(StrictModel):
    persona:Literal['coffee','outdoor','creator']


class DiscoveryQuery(BaseModel):
    shopping_priority:Literal['auto','domestic','overseas','compare']|None=None
    fx_period:Literal['30D','90D','1Y']='90D'
    opportunity_mode:Literal['live','historical']='live'
    listing_currency:Literal['EUR','GBP','JPY','AUD','CAD','CHF','SEK','SGD','USD']|None=None
    fx_mode:Literal['demo','live']='live'
    scenario:Literal['balanced','strong-yen','weak-yen','strong-usd','weak-usd']='balanced'
    adjustment:float=Field(default=0,ge=-30,le=30,allow_inf_nan=False)
    shipping_adjustment:int=Field(default=0,ge=0,le=10000)
    country:str|None=Field(default=None,max_length=2)
    category:str|None=Field(default=None,max_length=40)
    digital_only:bool=False
    physical_only:bool=False
    excluded_countries:str=Field(default='',max_length=100)
    max_budget:int|None=Field(default=None,gt=0,le=1000000)
    sort:Literal['best','fx','cost','unique','recent']='best'
    saved_only:bool=False


class ProfileInput(StrictModel):
    interests:list[str]|None=Field(default=None,max_length=12)
    budget_usd:int=Field(ge=100,le=1000000)


class SaveInput(StrictModel):
    saved:bool


class Question(StrictModel):
    explain_strategy:bool=False
    strategy_signature:str|None=Field(default=None,min_length=24,max_length=24,pattern='^[a-f0-9]+$')
    message:str=Field(min_length=1,max_length=800)
    offer_id:int|None=Field(default=None,gt=0)


class CheckoutInput(StrictModel):
    currency:Literal['USD','JPY']='USD'
    offer_id:int=Field(gt=0)
    quantity:int=Field(default=1,ge=1,le=10)
    mode:Literal['sandbox','simulation']
    idempotency_key:UUID


def data_context(db,user_id,q):
    rates=fx.bundle(db,q.fx_mode,q.scenario,q.adjustment)
    items=discovery.opportunities(db,user_id,rates,category=q.category,digital_only=q.digital_only,
        max_budget=q.max_budget,shipping_adjustment=q.shipping_adjustment,sort=q.sort,saved_only=q.saved_only)
    if q.physical_only:items=[p for p in items if not p['digital']]
    if q.excluded_countries:items=[p for p in items if p['country_code'] not in q.excluded_countries.split(',')]
    nations=discovery.countries(db,items,rates)
    return rates,items,nations


def find_item(db,user_id,offer_id,q):
    # Detail queries ignore browse filters; retain the same FX/cost scenario.
    rates=fx.bundle(db,q.fx_mode,q.scenario,q.adjustment)
    items=discovery.opportunities(db,user_id,rates,shipping_adjustment=q.shipping_adjustment)
    item=next((p for p in items if p['id']==offer_id),None)
    if not item:raise HTTPException(404,'Offer not available for discovery.')
    return item


def compact(item):
    return {k:item[k] for k in ('id','name','country','currency','local_price_minor','category','score','factors','cost','comparison','explanation','refund_terms')}|{
        'fx':{k:item['fx'].get(k) for k in ('rate','rate_date','source','power_vs_90_average','stale')} if item['fx'] else None}


@app.get('/api/health')
def health():return {'status':'ok','product':'Global Opportunity Discovery'}


@app.get('/api/demo/status')
def demo_status(db:DBSession=Depends(get_db)):
    return {'default_country':'US','default_currency':'USD','default_language':'English','demo_mode':DEMO_MODE,'source':'Synthetic Demo Catalog / Purchase History','demo_date':DEMO_DATE.isoformat(),
        'sandbox_configured':paypal.configured(),'checkout_currency':'USD',
        'currencies_sandbox_verified':list(db.scalars(select(PaymentOrder.currency).where(PaymentOrder.mode=='sandbox',PaymentOrder.status=='COMPLETED',PaymentOrder.paypal_capture_id.is_not(None)).distinct())),
        'personas':[{'id':key,'user_id':uid,'name':PERSONAS[uid][0],'title':PERSONAS[uid][1]}
            for key,uid in [('coffee',1),('outdoor',3),('creator',4)]],
        'categories':CATEGORIES,'countries':db.scalar(select(func.count()).select_from(Country)),
        'offers':db.scalar(select(func.count()).select_from(Offer)),
        'scenarios':[{'id':s.id,'title':s.title,'description':s.description} for s in db.scalars(select(DemoScenario))]}


@app.post('/api/demo/session')
def demo_session(body:Persona,response:Response,db:DBSession=Depends(get_db)):
    if not DEMO_MODE:raise HTTPException(403,'Demo disabled. Production identity is not implemented.')
    for token,session in list(sessions.items()):
        if session[1]<time.monotonic():sessions.pop(token,None)
    uid={'coffee':1,'outdoor':3,'creator':4}[body.persona]
    token=secrets.token_urlsafe(32)
    sessions[token]=(uid,time.monotonic()+43200)
    response.set_cookie('radar_session',token,httponly=True,samesite='lax',max_age=43200,path='/')
    row=analysis.state(db,uid)
    if row.status=='pending':analysis.schedule(uid)
    return {'persona':body.persona,'name':PERSONAS[uid][0],'demo_only':True}


@app.get('/api/discovery')
def discover(q:DiscoveryQuery=Depends(),user=Depends(principal),db:DBSession=Depends(get_db)):
    rates,items,nations=data_context(db,user.id,q)
    person=discovery.profile(db,user.id,q.fx_period,q.opportunity_mode)
    from .discovery_markets import markets
    from .shopping_strategy import current
    return {'profile':person,'countries':nations,'fx_intelligence':person['search_plan']['fx_intelligence'],
        'strategy':current(db,user.id,person['search_plan'],[],q.model_dump()),
        'discovery_markets':markets(db,user.id,q.country,q.category,q.excluded_countries.split(',') if q.excluded_countries else [],person['search_plan']),
        'offers':[p for p in items if not q.country or p['country_code']==q.country],
        'fx':rates,'catalog_source':'Synthetic Demo Catalog','weights':discovery.weights(),
        'filters':q.model_dump(),'all_offer_count':len(items)}


@app.get('/api/profile')
def profile(user=Depends(principal),db:DBSession=Depends(get_db)):
    return discovery.profile(db,user.id)|{'name':user.display_name,'persona':user.persona}


@app.get('/api/strategy/initial')
def initial_strategy(q:DiscoveryQuery=Depends(),user=Depends(principal),db:DBSession=Depends(get_db)):
    from .search_plan import build
    from .shopping_strategy import current
    # Show an honest immediate assessment even on a cold/offline FX startup.
    # Live discovery proceeds independently; this path never calls providers.
    plan=build(db,user.id,q.fx_period,q.opportunity_mode,refresh_fx=False)
    return current(db,user.id,plan,[],q.model_dump())|{'provisional':True}


@app.post('/api/profile')
def update_profile(body:ProfileInput,user=Depends(principal),db:DBSession=Depends(get_db)):
    import json
    if body.interests is not None and any(c not in CATEGORIES for c in body.interests):
        raise HTTPException(422,'Choose interests from the catalog categories.')
    row=db.get(InterestProfile,user.id)
    row.overrides_json=json.dumps(list(dict.fromkeys(body.interests))) if body.interests is not None else None
    row.budget_usd=body.budget_usd
    db.commit()
    analysis.touch(db,user.id)
    return discovery.profile(db,user.id)


@app.get('/api/history')
def history(user=Depends(principal),db:DBSession=Depends(get_db)):
    rows=list(db.scalars(select(Purchase).where(Purchase.user_id==user.id,Purchase.deleted==False).order_by(Purchase.purchased_at.desc(),Purchase.id.desc()).limit(200)))
    return [{k:getattr(p,k) for k in ('id','offer_id','product_name','category','merchant_name','country_code','quantity','amount','currency','purchased_at','source','paypal_order_id','paypal_capture_id','notes')}|{'editable':p.source in ('synthetic_global','user_provided')} for p in rows]


@app.get('/api/offers/{offer_id}')
def offer(offer_id:int,q:DiscoveryQuery=Depends(),user=Depends(principal),db:DBSession=Depends(get_db)):
    return find_item(db,user.id,offer_id,q)


@app.post('/api/saved/{offer_id}')
def save_offer(offer_id:int,body:SaveInput,user=Depends(principal),db:DBSession=Depends(get_db)):
    if not db.get(Offer,offer_id):raise HTTPException(404,'Offer not found.')
    row=db.scalar(select(SavedOpportunity).where(SavedOpportunity.user_id==user.id,SavedOpportunity.offer_id==offer_id))
    if body.saved and row is None:db.add(SavedOpportunity(user_id=user.id,offer_id=offer_id))
    if not body.saved and row is not None:db.delete(row)
    db.commit()
    return {'offer_id':offer_id,'saved':body.saved}


@app.post('/api/offers/{offer_id}/explanation')
def explain_offer(offer_id:int,q:DiscoveryQuery=Depends(),user=Depends(principal),db:DBSession=Depends(get_db)):
    item=find_item(db,user.id,offer_id,q)
    return explain(db,f'user:{user.id}','Explain this global discovery using only these facts; distinguish market estimates from fixed Sandbox quotes.',compact(item),item['explanation'])


@app.post('/api/countries/{country_code}/explanation')
def explain_country(country_code:str,q:DiscoveryQuery=Depends(),user=Depends(principal),db:DBSession=Depends(get_db)):
    rates,items,nations=data_context(db,user.id,q)
    nation=next((n for n in nations if n['code']==country_code),None)
    if nation is None:raise HTTPException(404,'Country not covered by the demo catalog.')
    facts={'country':{k:v for k,v in nation.items() if k!='fx'},'fx':{k:v for k,v in (nation['fx'] or {}).items() if k!='history'},
           'top_offers':[compact(p) for p in items if p['country_code']==country_code][:3]}
    return explain(db,f'user:{user.id}','Explain why to explore this country. Do not equate FX changes with discounts.',facts,nation['explanation'])


@app.post('/api/concierge')
def concierge(body:Question,q:DiscoveryQuery=Depends(),user=Depends(principal),db:DBSession=Depends(get_db)):
    message=body.message.strip()
    if not message or any(ord(c)<32 and c not in '\n\t' for c in message):raise HTTPException(422,'Enter a readable shopping question.')
    from .conversation import respond
    return respond(db,user.id,message,q,body.offer_id,body.strategy_signature,body.explain_strategy)


@app.post('/api/demo/reset')
def reset(user=Depends(principal),db:DBSession=Depends(get_db)):
    if not DEMO_MODE:raise HTTPException(403,'Demo reset disabled.')
    with checkout.payment_lock:seed(db,reset=True,user_id=user.id);analysis.touch(db,user.id)
    return {'status':'Reset synthetic persona histories, interests, and saves. Completed app payments, orders, FX cache, and legacy data preserved.'}


@app.post('/api/checkout/orders')
def create_order(body:CheckoutInput,user=Depends(principal),db:DBSession=Depends(get_db)):
    with checkout.payment_lock:
        return checkout.create(db,user.id,body.offer_id,body.quantity,body.mode,str(body.idempotency_key),body.currency)


@app.get('/api/checkout/orders/{order_id}')
def get_order(order_id:str,user=Depends(principal),db:DBSession=Depends(get_db)):
    with checkout.payment_lock:return checkout.status(db,checkout.owned(db,order_id,user.id))


@app.post('/api/checkout/orders/{order_id}/capture')
def capture_order(order_id:str,user=Depends(principal),db:DBSession=Depends(get_db)):
    with checkout.payment_lock:return checkout.capture(db,checkout.owned(db,order_id,user.id))

from .enhancements import install
install(app,principal)
