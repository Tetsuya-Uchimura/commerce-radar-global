"""Small, inspectable action resolver. The LLM never returns executable UI/payment tools."""
import re


def resolve_actions(message, offer_id=None):
    text = message.lower()
    actions = []
    filters = {}
    if any(word in text for word in ('digital', 'デジタル')):
        filters['digital_only'] = True
    if any(word in text for word in ('budget', 'under', '以内', '予算', '送料')):
        number = re.search(r'(\d[\d,]*)\s*(万)?', text)
        if number:
            budget = int(number[1].replace(',', '')) * (10000 if number[2] else 1)
            if 0 < budget <= 1000000:
                filters['max_budget'] = budget*100
    if any(word in text for word in ('coffee', 'コーヒー')):
        filters['category'] = 'Coffee'
    if any(word in text for word in ('outdoor', 'アウトドア')):
        filters['category'] = 'Outdoor'
    if any(word in text for word in ('photography', '写真')):
        filters['category'] = 'Photography'
    if any(word in text for word in ('purchasing power', 'currency', 'fx opportunity', '円で買いやす', '為替')):
        filters['sort'] = 'fx'
    if filters:
        actions.append({'type': 'set_filters', 'filters': filters})
    countries = {'japan':'JP','日本':'JP','germany':'DE','ドイツ':'DE','portugal': 'PT', 'ポルトガル': 'PT', 'united kingdom': 'GB', 'イギリス': 'GB',
                 'united states': 'US', 'アメリカ': 'US', 'australia': 'AU', 'オーストラリア': 'AU',
                 'canada': 'CA', 'カナダ': 'CA', 'singapore': 'SG', 'シンガポール': 'SG',
                 'switzerland': 'CH', 'スイス': 'CH', 'sweden': 'SE', 'スウェーデン': 'SE'}
    for name, code in countries.items():
        if name in text:
            actions.append({'type': 'select_country', 'country': code})
            break
    if offer_id and any(word in text for word in ('buy', 'detail', 'この商品', '購入', '買いたい')):
        actions.append({'type': 'open_offer', 'offer_id': offer_id})
    return actions
