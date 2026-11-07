"""Explicitly refresh a tiny public-price evidence set from allowlisted official pages.
Not a background crawler or destination-access approval. No location inference.
"""
import sys,json,re,hashlib,html as html_module
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.products import safe_url
ROOT=Path(__file__).resolve().parents[1]
def nodes(value):
    if isinstance(value,dict):
        yield value
        for v in value.values():yield from nodes(v)
    elif isinstance(value,list):
        for v in value:yield from nodes(v)
def extract(html,url,stamp):
    items=[]
    for text in re.findall(r'<script[^>]*type=[\"\x27]application/ld\+json[\"\x27][^>]*>(.*?)</script>',html,re.S|re.I):
        try:root=json.loads(text)
        except ValueError:continue
        for node in nodes(root):
            if node.get('@type')!='Product' or not node.get('name'):continue
            offers=node.get('offers',[]);offers=offers if isinstance(offers,list) else [offers]
            for offer in offers[:1]:
                currency=offer.get('priceCurrency');amount=offer.get('price');link=safe_url(offer.get('url') or url)
                if currency not in ('EUR','GBP','JPY','USD') or amount is None or not link:continue
                try:
                    value=Decimal(str(amount))
                    if not value.is_finite() or value<0:continue
                    minor=int((value*(1 if currency=='JPY' else 100)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                except Exception:continue
                items.append({'id':'curated:'+hashlib.sha256(link.encode()).hexdigest()[:12],
                    'name':node['name'],'merchant':(offer.get('seller') or {}).get('name') or httpx.URL(url).host,
                    'category':'Coffee','description':'Coffee brewing equipment. Specific variant observed in publisher Product/Offer JSON-LD.',
                    'price_minor':minor,'currency':currency,'url':link,'merchant_country':None,'shipping_available':None,
                    'price_verified_at':stamp,'verified_at':stamp,'price_source_url':url,'source':'Curated official listing · Product/Offer JSON-LD',
                    'verification':'Exact published variant/offer observed. Country, US delivery, tax and shipping remain unknown. Reconfirm price with seller.',
                    'kind':'external','paypal_checkout':False,'purchase_method':'Visit Store'})
    if not items:
        meta={k:html_module.unescape(v) for k,v in re.findall(r'<meta\s+property="([^"]+)"\s+content="([^"]*)"',html,re.I)}
        price=meta.get('og:price:amount');currency=meta.get('og:price:currency');name=meta.get('og:title')
        if price and currency in ('EUR','GBP','JPY','USD') and name:
            try:
                amount=Decimal(price.replace(',','.'))
                if amount.is_finite() and amount>=0:
                    items.append({'id':'curated:'+hashlib.sha256(url.encode()).hexdigest()[:12],'name':name,'merchant':httpx.URL(url).host,
                        'category':'Coffee','description':'Coffee brewing dripper. Published Open Graph product price; confirm variant with seller.',
                        'price_minor':int((amount*(1 if currency=='JPY' else 100)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)),
                        'currency':currency,'url':url,'merchant_country':None,'shipping_available':None,'price_verified_at':stamp,'verified_at':stamp,
                        'price_source_url':url,'source':'Curated official listing · Open Graph price metadata',
                        'verification':'Published page price/currency metadata observed. Variant, country, US delivery and final costs require seller confirmation.',
                        'kind':'external','paypal_checkout':False,'purchase_method':'Visit Store'})
            except Exception:pass
    return items
def main():
    urls=['https://www.hario.co.uk/products/hario-v60-coffee-dripper-plastic-size-02-white','https://jp.kurasu.kyoto/products/hario-v60-dripper','https://kinto-usa.com/products/27574']
    observations=[];stamp=datetime.now(timezone.utc).isoformat()
    with httpx.Client(timeout=15,follow_redirects=False) as client:
        us_faq=client.get('https://kinto-usa.com/pages/faq')
        us_market_confirmed=us_faq.status_code==200 and 'Western USA' in us_faq.text and 'Eastern USA' in us_faq.text
        collection=client.get('https://www.hario-europe.com/collections/v60-dripper/ceramic')
        if collection.status_code==200:
            links=list(dict.fromkeys(re.findall(r'href="(?:/collections/[^" ]+)?(/products/[^"?# ]+)',collection.text)))
            urls+=['https://www.hario-europe.com'+p for p in links[:1]]
        for url in urls:
            try:
                r=client.get(url);items=extract(r.text,url,stamp) if r.status_code==200 else []
                if url.startswith('https://kinto-usa.com/') and us_market_confirmed:
                    for p in items:
                        p['storefront_market']='US'
                        p['storefront_market_evidence']={'source':'https://kinto-usa.com/pages/faq','observed_at':stamp,'basis':'Publisher FAQ explicitly describes US delivery regions; market evidence only, no legal-country or per-item shipping-cost assertion.'}
                observations.extend(items[:2]);print(json.dumps({'url':url,'status':r.status_code,'offers':[(i['name'],i['currency'],i['price_minor']) for i in items[:2]]},ensure_ascii=True))
            except httpx.HTTPError as e:print(type(e).__name__,url)
    target=ROOT/'backend/fixtures/curated_products.json';target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps({'observed_at':stamp,'notice':'Saved public facts only; not continuously live prices. No merchant location or delivery inference.','items':observations},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
