"""Convert current AI hypotheses into auditable search proposals; never invent listings."""
import hashlib
import json
import re
from . import analysis
from .models import InterestProfile

TERMS = {
    'Coffee': 'coffee brewing equipment artisan beans workshops',
    'Photography': 'photography camera accessories creative photography courses',
    'Education': 'online courses learning workshops',
    'Outdoor': 'outdoor hiking camping gear',
    'Home & Living': 'handmade home decor kitchen accessories',
    'Digital Experiences': 'creative software apps online experiences',
    'Fashion': 'independent fashion accessories',
    'Electronics': 'electronics creative tools',
}

def build(db, uid, fx_period='90D', fx_mode='live',refresh_fx=True):
    facts = analysis.features(db, uid)
    state = analysis.state(db, uid)
    current = state.status == 'completed' and state.applied_version == state.version
    result = json.loads(state.result_json) if current and state.result_json else {}
    setting = db.get(InterestProfile, uid)
    chosen = facts['explicit_categories']
    ai_scores = {}; origins = {}
    def add(category, score, source):
        if category not in TERMS or chosen is not None and category not in chosen: return
        ai_scores[category] = max(ai_scores.get(category, 0), score)
        origins.setdefault(category, []).append(source)
    for interest in result.get('top_interests', []):
        add(interest['category'], {'Strong':100,'Moderate':65,'Emerging':45}[interest['level']], 'top_interests')
    for category in result.get('emerging_interests', []): add(category, 70, 'emerging_interests')
    for category in result.get('preferred_product_categories', []): add(category, 60, 'preferred_product_categories')
    categories = set(facts['scores']) | set(ai_scores)
    if chosen is not None: categories = set(chosen)
    scores = {c: round(.7*facts['scores'].get(c,0)+.3*ai_scores.get(c,0),1) if result else facts['scores'].get(c,70 if chosen is not None else 0) for c in categories}
    ranked = sorted(scores,key=lambda c:(-scores[c],c))
    queries = []
    def query(category, text, origin):
        text = re.sub(r'https?://\S+|[\x00-\x1f]', ' ', str(text))
        text = ' '.join(text.split())[:160]
        if text: queries.append({'category':category,'query':text,'origin':origin,'interest_score':scores.get(category,0)})
    # Emerging AI needs get an exploration slot even when historical coffee counts dominate.
    emerging = [c for c in result.get('emerging_interests',[]) if c in scores]
    for c in list(dict.fromkeys(emerging+ranked))[:5]: query(c,TERMS[c],'+'.join(origins.get(c,['category_statistics'])))
    primary = emerging[0] if emerging else ranked[0] if ranked else 'Digital Experiences'
    for field in ('potential_purchase_intentions','novel_product_opportunities'):
        for hypothesis in result.get(field,[])[:3]: query(primary,primary+' '+hypothesis,field)
    from .fx_opportunities import intelligence
    currency_context=intelligence(db,fx_period,fx_mode,refresh_fx)
    favorable=currency_context['favorable_currencies'][:3]
    fx_queries=[dict(q,query=(q['query']+'; listings priced in '+currency+'; confirm original listing currency')[:200],
        listing_currency_target=currency,origin=q['origin']+'+observed_fx_advantage') for q in queries[:3] for currency in favorable]
    signature = hashlib.sha256(json.dumps({'version':state.version,'applied':state.applied_version,'queries':queries,'scores':scores,'fx':currency_context['signature']},sort_keys=True).encode()).hexdigest()[:16]
    return {'version':state.version,'applied_version':state.applied_version,'current_ai':bool(result),
        'status':state.status,'signature':signature,'queries':queries,'fx_queries':fx_queries,'fx_intelligence':currency_context,'category_scores':scores,
        'statistical_scores':facts['scores'],'category_counts':facts['counts'],'ai_category_scores':ai_scores,
        'budget_minor':setting.budget_usd if setting else None,
        'scoring_rule':'70% frequency/recency score + 30% AI category rubric (Strong 100, Moderate 65, Emerging 45; emerging list 70; preferred list 60). Stale AI excluded. Explicit categories restrict scope.',
        'notice':'Search proposals are uncertain AI hypotheses. Products, prices and merchant origin require provider evidence.'}
