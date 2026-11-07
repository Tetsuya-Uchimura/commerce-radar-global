from typing import Literal
from datetime import date
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from .db import get_db
from .models import Purchase
from .history import PurchaseInput,validated,editable
from . import analysis,fx,products
from .seed import seed

class Feedback(BaseModel):
    feedback:str=Field(max_length=500)
class ProductSearch(BaseModel):
    shopping_priority:Literal['auto','domestic','overseas','compare']|None=None
    fx_period:Literal['30D','90D','1Y']='90D'
    opportunity_mode:Literal['live','historical']='live'
    listing_currency:Literal['EUR','GBP','JPY','AUD','CAD','CHF','SEK','SGD','USD']|None=None
    query:str|None=Field(default=None,min_length=2,max_length=200)
    country:str|None=Field(default=None,max_length=2)
    goal:Literal['best','cheapest','unique','quality']='best'
    budget_minor:int|None=Field(default=None,gt=0,le=10000000)
    provider:Literal['auto','web','app_store','channel3','curated']='auto'
    excluded_countries:list[str]=Field(default_factory=list,max_length=30)
    kind:Literal['digital','physical','any']='any'

class AutomaticSearch(ProductSearch):
    category:analysis.Category|None=None
    expected_signature:str|None=Field(default=None,max_length=64)
    refresh:bool=False
    demo_only:bool=False

class StrategyPreference(BaseModel):
    priority:Literal['auto','domestic','overseas','compare']

class StrategyExplanation(BaseModel):
    signature:str=Field(min_length=24,max_length=24,pattern='^[a-f0-9]+$')

def install(app,principal):
    @app.post('/api/strategy/preference')
    def preference(body:StrategyPreference,user=Depends(principal),db=Depends(get_db)):
        from .shopping_strategy import set_preference
        set_preference(db,user.id,body.priority)
        return {'shopping_priority':body.priority}

    @app.post('/api/strategy/explanation')
    def strategy_explanation(body:StrategyExplanation,user=Depends(principal),db=Depends(get_db)):
        from .shopping_strategy import explanation
        value=explanation(db,user.id,body.signature)
        if value is None:raise HTTPException(409,'Strategy evidence changed or expired; refresh the strategy.')
        return value
    @app.get('/api/products/status')
    def provider_status(user=Depends(principal)):
        from .product_runtime import status
        return status()

    @app.post('/api/products/automatic')
    def automatic(body:AutomaticSearch,user=Depends(principal),db=Depends(get_db)):
        from .automatic_discovery import run
        return run(db,user.id,body.model_dump())
    @app.get('/api/products/plan')
    def plan(fx_period:Literal['30D','90D','1Y']='90D',opportunity_mode:Literal['live','historical']='live',user=Depends(principal),db=Depends(get_db)):
        from .search_plan import build
        return build(db,user.id,fx_period,opportunity_mode)

    @app.get('/api/fx/opportunities')
    def fx_opportunities(period:Literal['30D','90D','1Y']='90D',mode:Literal['live','historical']='live',user=Depends(principal),db=Depends(get_db)):
        from .fx_opportunities import intelligence
        return intelligence(db,period,mode)
    @app.get('/api/usage')
    def usage(user=Depends(principal),db=Depends(get_db)):
        from .usage import summary
        return summary(db,user.id)
    @app.post('/api/history')
    def add(body:PurchaseInput,user=Depends(principal),db=Depends(get_db)):
        row=Purchase(user_id=user.id,source='user_provided',**validated(body));db.add(row);db.commit()
        version=analysis.touch(db,user.id)
        return {'id':row.id,'version':version,'status':'pending'}

    @app.post('/api/history/{purchase_id}/edit')
    def edit(purchase_id:int,body:PurchaseInput,user=Depends(principal),db=Depends(get_db)):
        row=editable(db,user.id,purchase_id)
        for key,value in validated(body).items():setattr(row,key,value)
        db.commit();return {'id':row.id,'version':analysis.touch(db,user.id)}

    @app.post('/api/history/{purchase_id}/delete')
    def delete(purchase_id:int,user=Depends(principal),db=Depends(get_db)):
        row=editable(db,user.id,purchase_id);row.deleted=True;db.commit()
        return {'version':analysis.touch(db,user.id)}

    @app.post('/api/history/restore')
    def restore(user=Depends(principal),db=Depends(get_db)):
        seed(db,reset=True,user_id=user.id)
        return {'version':analysis.touch(db,user.id),'message':'Restored this persona only; user-provided data and all payments retained.'}

    @app.get('/api/analysis')
    def get_analysis(user=Depends(principal),db=Depends(get_db)):return analysis.public(db,user.id)

    @app.post('/api/analysis/reanalyze')
    def rerun(user=Depends(principal),db=Depends(get_db)):
        row=analysis.state(db,user.id);row.status='pending';db.commit();analysis.schedule(user.id)
        return analysis.public(db,user.id)

    @app.post('/api/analysis/feedback')
    def feedback(body:Feedback,user=Depends(principal),db=Depends(get_db)):
        row=analysis.state(db,user.id);row.feedback=body.feedback;db.commit();analysis.touch(db,user.id)
        return analysis.public(db,user.id)

    @app.get('/api/fx/chart')
    def chart(currency:Literal['EUR','GBP','JPY','CAD','AUD','CHF','SEK','SGD']='EUR',period:Literal['1M','3M','6M','1Y','5Y','MAX']='1Y',user=Depends(principal),db=Depends(get_db)):
        return fx.chart(db,currency,period)

    @app.post('/api/fx/refresh')
    def refresh(currency:Literal['EUR','GBP','JPY','CAD','AUD','CHF','SEK','SGD']='EUR',period:Literal['1M','3M','6M','1Y','5Y','MAX']='1Y',user=Depends(principal),db=Depends(get_db)):
        return fx.chart(db,currency,period,True)

    @app.get('/api/fx/compare')
    def compare(currencies:str='EUR,JPY',period:Literal['1M','3M','6M','1Y','5Y','MAX']='1Y',refresh:bool=False,user=Depends(principal),db=Depends(get_db)):
        codes=list(dict.fromkeys(currencies.split(',')))
        if not 2<=len(codes)<=5 or any(c not in fx.CURRENCIES for c in codes):raise HTTPException(422,'Select 2–5 supported foreign currencies.')
        series={c:fx.chart(db,c,period,refresh) for c in codes}
        return {'series':series,'indexed':fx.indexed(series),'explanation':'Common observed starting date = 100 foreign units per USD. Higher means stronger USD purchasing power; missing observations are not interpolated.'}

    @app.post('/api/products/search')
    def search(body:ProductSearch,user=Depends(principal),db=Depends(get_db)):
        return products.explore(db,user.id,body.query,body.country,body.provider,body.goal,body.budget_minor,body.excluded_countries,body.kind,False,body.fx_period,body.opportunity_mode,body.listing_currency,body.shopping_priority)

    @app.post('/api/concierge/clear')
    def clear_chat(user=Depends(principal),db=Depends(get_db)):
        from .models import ChatState
        row=db.get(ChatState,user.id)
        if row:row.conditions_json='{}';row.messages_json='[]';db.commit()
        return {'status':'cleared'}
