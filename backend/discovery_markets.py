"""Exploration routes, never evidence of seller origin, stock or price advantage."""
from sqlalchemy import select
from .models import Country
from .search_plan import build,TERMS

def markets(db,uid,selected=None,category=None,excluded=None,plan=None):
    plan=plan or build(db,uid)
    interests=[category] if category in TERMS else list(dict.fromkeys(q['category'] for q in plan['queries']))[:3]
    topic=TERMS.get(category) or (plan['queries'][0]['query'] if plan['queries'] else 'international products')
    excluded=set(excluded or [])
    rows=[]
    for country in db.scalars(select(Country).order_by(Country.name)):
        if country.code in excluded:continue
        rows.append({'code':country.code,'name':country.name,'interests':interests,
            'selected':country.code==selected,'query':(topic+' '+country.code+' products')[:200],
            'basis':'Explicit search target' if country.code==selected else 'Supported exploration route using your current interest query',
            'reason':f'Explore {country.name} using '+(', '.join(interests) if interests else 'an explicit shopping query')+'. This is a search destination, not confirmed seller location, inventory or better pricing.',
            'seller_location_verified':False,'opportunity_score':None,'source':'Interest-led search plan · exploration suggestion'})
    return rows
