"""Optional Channel3 REST adapter. Only observed offer fields become product facts."""
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import httpx

def normalize(data):
    from .products import safe_url
    if not isinstance(data,dict) or not isinstance(data.get('products'),list): raise ValueError('Invalid product response')
    items=[]; seen=set(); stamp=datetime.now(timezone.utc).isoformat()
    for product in data['products']:
        if not isinstance(product,dict) or not product.get('title'):continue
        for offer in product.get('offers') or []:
            if not isinstance(offer,dict):continue
            url=safe_url(offer.get('url'))
            if not url or url in seen:continue
            seen.add(url); price=offer.get('price') or {}; currency=price.get('currency') if isinstance(price,dict) else None
            minor=None
            try:
                # Official docs currently show both price.price and price.amount examples.
                amount=Decimal(str(price.get('price',price.get('amount'))))
                if currency in ('USD','EUR','GBP','JPY','AUD','CAD','CHF','SEK','SGD') and amount.is_finite() and 0<=amount<=100000000:
                    minor=int((amount*(1 if currency=='JPY' else 100)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            except (InvalidOperation,ValueError,TypeError,AttributeError):pass
            items.append({'id':'channel3:'+str(product.get('id'))+':'+str(len(items)),
                'name':str(product['title'])[:200],'merchant':offer.get('domain') or 'Unknown',
                'merchant_country':None,'target_country':None,'url':url,'price_minor':minor,'currency':currency,
                'price_verified_at':stamp if minor is not None else None,'verified_at':stamp,
                'description':str(product.get('description') or '')[:250],'image_url':None,
                'availability':offer.get('availability'),'shipping_available':None,'taxes':None,
                'estimated_total_usd':None,'quality_evidence':None,'merchant_reliability_evidence':None,
                'source':'Channel3 product API','verification':'Provider-reported listing price and availability, retrieved at the stated time. Merchant origin, US delivery, shipping and tax are unverified.',
                'paypal_checkout':False,'purchase_method':'Visit Store','kind':'external','query':None})
    return items[:20]

class Channel3Provider:
    def search(self,query,country=None):
        key=os.getenv('CHANNEL3_API_KEY')
        if not key:return {'items':[],'error':'CHANNEL3_API_KEY is required. Add a developer key to the server .env; Web and App Store search remain available.','source':'Unavailable'}
        try:
            # Query target is not an origin/US-delivery guarantee. Keep listing currency;
            # no guessed country locale (Japan is not currently a documented market).
            with httpx.Client(timeout=20,follow_redirects=False) as client:
                r=client.post('https://api.trychannel3.com/v1/search',headers={'x-api-key':key},json={'query':query[:200],'limit':8})
                r.raise_for_status();items=normalize(r.json())
            return {'items':items,'error':None,'source':'Channel3 product API'}
        except httpx.HTTPStatusError as error:
            code=error.response.status_code
            message='Channel3 authentication failed.' if code in (401,403) else 'Channel3 rate limit reached.' if code==429 else 'Channel3 provider returned an HTTP error.'
            return {'items':[],'error':message,'source':'Unavailable'}
        except httpx.TimeoutException:
            return {'items':[],'error':'Channel3 search timed out.','source':'Unavailable'}
        except (httpx.HTTPError,ValueError,TypeError):
            return {'items':[],'error':'Channel3 unavailable or key/credits rejected. No replacement prices were invented.','source':'Unavailable'}

provider=Channel3Provider()
