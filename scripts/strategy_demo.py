"""Offline, genuine-observation demonstration of all three search priorities.

The Coffee interest profile is synthetic. FX and listing prices are saved public
observations. No credentials, network, payment operations or developer DB writes.
"""
import sys,json,hashlib
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.fx_opportunities import summarize,product_evidence
from backend.shopping_strategy import decide

def scenarios():
    root=Path(__file__).resolve().parents[1]/'backend/fixtures'
    snapshot=json.loads((root/'fx_observed_snapshot.json').read_text(encoding='utf-8'))
    prices=json.loads((root/'strategy_historical_prices.json').read_text(encoding='utf-8'))
    markets=[summarize(c,[(date.fromisoformat(p['date']),p['rate']) for p in rows],today=date.fromisoformat(snapshot['as_of']),fetched_at=snapshot['retrieved_at'],mode='historical') for c,rows in snapshot['currencies'].items()]
    intel={'markets':markets,'period':'90D','mode':'historical','as_of':snapshot['as_of'],'signature':hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()[:16]}
    plan={'fx_intelligence':intel,'category_scores':{'Coffee':100},'version':1,'signature':'synthetic-coffee-profile-saved-observations'}
    items=[]
    for raw in prices['items']:
        p=dict(raw,score_factors={'interest':100},matched_categories=['Coffee'])
        market=next((m for m in markets if m['currency']==p['currency']),None)
        p['fx_opportunity']=product_evidence(p,market,100,100,'historical');p['fx_recommendation_score']=p['fx_opportunity']['score']
        p['listing_usd_minor']=p['price_minor'] if p['currency']=='USD' else p['fx_opportunity']['current_usd_minor']
        items.append(p)
    return {
        'explore_overseas':decide(plan,items,{'listing_currency':'EUR'}),
        'us_stores_first':decide(plan,items,{'listing_currency':'JPY'}),
        # An actual USD 10 listing cap leaves no observed relevant EUR item.
        'compare_both':decide(plan,[p for p in items if p['listing_usd_minor'] is not None and p['listing_usd_minor']<=1000],{'listing_currency':'EUR','budget_minor':1000})}

if __name__=='__main__':
    cases=scenarios()
    for expected,result in cases.items():
        assert result['strategy']==expected,(expected,result['strategy'])
    print(json.dumps({'notice':'Historical demonstration using saved genuine FX/prices and a synthetic Coffee profile. Search priority only; not current market advice.','cases':cases},ensure_ascii=True,indent=2))
