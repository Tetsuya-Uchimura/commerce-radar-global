"""Deterministic interest features, opportunity scores, and conservative country scores."""
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
import json
import os
import math
from sqlalchemy import select
from .models import Purchase, InterestProfile, Offer, Product, Country, SavedOpportunity
from .config import DEMO_DATE
from .costs import landed_cost

DEFAULT_WEIGHTS = {'interest': 30, 'cost': 25, 'fx': 15, 'novelty': 15, 'availability': 10, 'budget': 5}


def weights():
    result = json.loads(os.getenv('SCORING_WEIGHTS_JSON', json.dumps(DEFAULT_WEIGHTS)))
    if set(result) != set(DEFAULT_WEIGHTS) or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in result.values()) or sum(result.values()) <= 0:
        raise ValueError('Invalid scoring weights.')
    return result


def profile(db, user_id):
    from .search_plan import build
    plan = build(db, user_id)
    rows = list(db.scalars(select(Purchase).where(Purchase.user_id == user_id, Purchase.deleted == False)))
    setting = db.get(InterestProfile, user_id)
    counts = Counter(p.category for p in rows if p.category != 'Unknown')
    recent = Counter(p.category for p in rows if 0 <= (DEMO_DATE-p.purchased_at).days < 30)
    previous = Counter(p.category for p in rows if 30 <= (DEMO_DATE-p.purchased_at).days < 90)
    strength = {cat: round(100*(0.65*n/max(counts.values(), default=1)+0.35*recent[cat]/max(recent.values(), default=1))) for cat,n in counts.items()}
    statistical_strength = dict(strength)
    strength = plan['category_scores']
    if setting.overrides_json is not None:
        overrides = json.loads(setting.overrides_json)
        strength = {cat: strength.get(cat, 70) for cat in overrides}
    prices = sorted(p.amount for p in rows if p.currency == 'USD')
    def quantile(f):
        return prices[int((len(prices)-1)*f)] if prices else None
    emerging = [cat for cat, n in recent.items() if n >= 2 and n/max(sum(recent.values()),1) > previous[cat]/max(sum(previous.values()),1)*1.5]
    return {'search_plan':plan,'statistical_scores':statistical_strength,'user_id': user_id, 'home_country':'US', 'shipping_destination':'US', 'home_currency':'USD', 'interests': [{'category': c, 'score': s, 'purchases': counts[c]} for c,s in sorted(strength.items(), key=lambda x: -x[1])],
            'emerging_interests': emerging, 'preferred_price_range': {'currency': 'USD', 'min': quantile(.25), 'max': quantile(.75)},
            'purchase_count': len(rows), 'frequency_per_30_days': round(sum(0 <= (DEMO_DATE-p.purchased_at).days < 180 for p in rows)/6, 1),
            'product_preferences': [name for name,_ in Counter(p.product_name for p in rows if p.product_name != 'Unknown').most_common(5)],
            'international_countries': sorted({p.country_code for p in rows if p.country_code not in ('US', 'Unknown')}),
            'budget_usd': setting.budget_usd, 'customized': setting.overrides_json is not None,
            'sources': dict(Counter(p.source for p in rows)), 'reference_date': DEMO_DATE.isoformat()}


def score_factors(interest, cost, fx, novelty, availability, budget, weight=None):
    values = {'interest': interest, 'cost': cost, 'fx': fx, 'novelty': novelty, 'availability': availability, 'budget': budget}
    if any(v is None for v in values.values()):
        return None
    weight = weight or weights()
    return round(sum(max(0, min(100, values[k]))*weight[k] for k in weight)/sum(weight.values()), 1)


def country_score(items):
    complete = sorted((p['score'] for p in items if p['score'] is not None), reverse=True)
    if not complete:
        return None
    top = complete[:3]
    # Adequate candidate breadth and complete-cost coverage both matter.
    breadth = min(1, len(complete)/4)
    coverage = len(complete)/max(len(items), 1)
    return round(sum(top)/len(top)*breadth*coverage, 1)


def opportunities(db, user_id, fx, country=None, category=None, digital_only=False,
                  max_budget=None, shipping_adjustment=0, sort='best', saved_only=False):
    person = profile(db, user_id)
    interests = {i['category']: i['score'] for i in person['interests']}
    bought = list(db.scalars(select(Purchase).where(Purchase.user_id == user_id, Purchase.deleted == False)))
    seen_countries = {p.country_code for p in bought}
    seen_products = {p.product_name for p in bought}
    saved = {s.offer_id for s in db.scalars(select(SavedOpportunity).where(SavedOpportunity.user_id == user_id))}
    budget = max_budget if max_budget is not None else person['budget_usd']
    items = []
    for offer, product, nation in db.execute(select(Offer, Product, Country).join(Product, Offer.product_id == Product.id).join(Country, Offer.country_code == Country.code)):
        if offer.stock <= 0 or offer.available_in_us is False:
            continue
        if country and offer.country_code != country or category and product.category != category:
            continue
        if digital_only and product.kind == 'physical' or saved_only and offer.id not in saved:
            continue
        rate = fx['rates'].get(offer.currency)
        estimate = landed_cost(offer, rate, shipping_adjustment if product.kind == 'physical' else 0)
        total = estimate['total_usd']
        if max_budget is not None and (total is None or total > max_budget):
            continue
        interest = interests.get(product.category, 15)
        novelty = (65 if offer.country_code not in seen_countries else 20)+(35 if product.name not in seen_products else 0)
        reference = None  # No verified USD equivalent reference was supplied.
        advantage = round(float((Decimal(reference)-Decimal(total))/Decimal(reference)*100), 1) if reference and total is not None else None
        cost_score = max(0, min(100, 50+(advantage or 0)*2)) if total is not None else None
        budget_score = 100 if total is not None and total <= budget else 0 if total is not None else None
        fx_score = rate.get('fx_score') if rate else None
        available = 100 if offer.available_in_us is True else None
        factors = {'interest': interest, 'cost': cost_score, 'fx': fx_score, 'novelty': novelty, 'availability': available, 'budget': budget_score}
        score = score_factors(**factors)
        if rate and rate.get('stale') and score is not None:
            score = min(score, 59)
        if budget_score == 0 and score is not None:
            score = min(score, 59)
        label = 'Comparable demo product' if reference else 'Global Discovery · no equivalent-price comparison'
        interest_reason = (f'{product.category} has a reproducible interest score of {interest}/100 (current AI category rubric blended with frequency/recency when available). '
                           if product.category in interests else f'No recorded {product.category} interest: included for exploration at 15/100. ')
        reason = (interest_reason +
                  f'{nation.name} is '+('new to your recorded shopping history. ' if offer.country_code not in seen_countries else 'already in your recorded shopping history. ')
                  + (f'Estimated total ${total/100:,.2f} USD includes shipping, estimated taxes, and assumed conversion costs.' if total is not None else 'Total cost is incomplete; missing charges are not treated as zero.'))
        items.append({'id': offer.id, 'product_id': product.id, 'name': product.name, 'description': product.description,
            'category': product.category, 'kind': product.kind, 'digital': product.kind != 'physical',
            'country_code': nation.code, 'country': nation.name, 'country_currency': nation.currency,
            'currency': offer.currency, 'local_price_minor': offer.local_price, 'image_url': product.image_url,
            'merchant': offer.merchant_name, 'product_url': offer.product_url, 'shipping_available': offer.available_in_us,
            'stock': offer.stock, 'checkout_available': offer.paypal_eligible and offer.checkout_usd is not None and offer.available_in_us is True,
            'checkout_quote_usd': offer.checkout_usd, 'source': offer.source, 'verified_at': offer.verified_at.isoformat(),
            'score': score, 'factors': factors, 'weights': weights(), 'cost': estimate, 'fx': rate,
            'comparison': {'label': label, 'reference_usd': reference, 'difference_usd': reference-total if reference and total is not None else None,
                           'advantage_percent': advantage, 'equivalence_group': product.equivalence_group},
            'explanation': reason, 'explanation_source': 'Deterministic explanation · no LLM', 'saved': offer.id in saved,
            'refund_terms': offer.refund_terms})
    key = {'best': lambda p: -(p['score'] if p['score'] is not None else -1),
           'fx': lambda p: -(p['factors']['fx'] if p['factors']['fx'] is not None else -1),
           'cost': lambda p: p['cost']['total_usd'] if p['cost']['total_usd'] is not None else float('inf'),
           'unique': lambda p: -p['factors']['novelty'], 'recent': lambda p: p['verified_at']}
    items.sort(key=key.get(sort, key['best']), reverse=sort == 'recent')
    return items


def countries(db, items, fx):
    grouped = defaultdict(list)
    for p in items:
        grouped[p['country_code']].append(p)
    result = []
    for country in db.scalars(select(Country)):
        candidates = grouped[country.code]
        score = country_score(candidates)
        complete = sum(p['score'] is not None for p in candidates)
        band = 'Insufficient Data' if score is None else 'Strong Opportunity' if score >= 80 else 'Good Opportunity' if score >= 60 else 'Explore'
        rate = fx['rates'].get(country.currency)
        top = sorted((p for p in candidates if p['score'] is not None), key=lambda p:-p['score'])[:1]
        match = f' The leading match is {top[0]["category"]} at {top[0]["factors"]["interest"]}/100 interest.' if top else ''
        power = (f' {country.currency} USD purchasing power is {float(rate["power_vs_90_average"]):+.1f}% vs its 90-day reference ({rate["source"]}); not a product discount.'
                 if rate and rate.get('power_vs_90_average') is not None else ' FX comparison history is insufficient.')
        result.append({'code': country.code, 'name': country.name, 'map_id': country.map_id, 'currency': country.currency,
            'longitude': country.longitude, 'latitude': country.latitude, 'score': score, 'band': band,
            'offer_count': len(candidates), 'complete_count': complete, 'fx': rate,
            'explanation': f'{len(candidates)} eligible demo offers, {complete} with complete cost and FX data.'+match+power+' Country scores discount narrow catalogs and incomplete estimates.'})
    return sorted(result, key=lambda c: -(c['score'] if c['score'] is not None else -1))
