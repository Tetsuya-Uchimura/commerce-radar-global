"""Fictional international offers and three reproducible shopping personas."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import random
from sqlalchemy import select, delete
from .models import (User, Currency, Country, Product, Offer, Purchase, InterestProfile,
                     ExchangeRate, DemoScenario, SavedOpportunity, AICache)
from .config import DEMO_DATE

CURRENCIES = [('JPY','Japanese Yen',0),('USD','US Dollar',2),('EUR','Euro',2),
              ('GBP','Pound Sterling',2),('AUD','Australian Dollar',2),('CAD','Canadian Dollar',2),
              ('SGD','Singapore Dollar',2),('CHF','Swiss Franc',2),('SEK','Swedish Krona',2)]
COUNTRIES = [('PT','Portugal','620','EUR',-8,39),('GB','United Kingdom','826','GBP',-2,54),
             ('US','United States','840','USD',-100,39),('AU','Australia','036','AUD',134,-25),
             ('CA','Canada','124','CAD',-106,56),('SG','Singapore','702','SGD',103.8,1.35),
             ('CH','Switzerland','756','CHF',8.2,46.8),('SE','Sweden','752','SEK',15,62)]
RATES = {'EUR':Decimal('157'),'GBP':Decimal('184'),'USD':Decimal('145'),'AUD':Decimal('96'),
         'CAD':Decimal('106'),'SGD':Decimal('108'),'CHF':Decimal('164'),'SEK':Decimal('13.7')}
CATEGORIES = ['Coffee','Outdoor','Photography','Education','Home & Living','Digital Experiences','Fashion','Electronics']
CAT_IMAGES = {'Coffee':0,'Outdoor':3,'Photography':1,'Education':4,'Home & Living':6,'Digital Experiences':7,'Fashion':2,'Electronics':1}
PERSONAS = {1:('Alex Morgan','Coffee Enthusiast'),3:('Jamie Rivers','Outdoor Explorer'),4:('Sam Chen','Digital Creator')}
CATALOG = {
 'PT':[('Handcrafted Coffee Cup','Coffee','physical',2800),('Lisbon Coffee Workshop','Coffee','online_course',3200),('Ceramic Pour-over Set','Home & Living','physical',4600),('Coastal Photo Presets','Photography','digital',1800),('Portuguese Design Class','Education','online_course',2500),('Artisan Linen Pouch','Fashion','physical',2200)],
 'GB':[('Home Barista Masterclass','Coffee','online_course',2400),('Coffee Tasting Journal','Coffee','digital',1200),('Rain-ready Trail Pouch','Outdoor','physical',1800),('Documentary Photo Course','Photography','online_course',3900),('Creator Storyboard Kit','Digital Experiences','digital',1600),('Minimal Desk Organizer','Home & Living','physical',2700)],
 'US':[('Coffee Flavor Field Guide','Coffee','digital',1800),('Creator Editing Toolkit','Digital Experiences','digital',3200),('Wilderness Photo Lessons','Photography','online_course',3800),('Ultralight Trail Bottle','Outdoor','physical',2600),('Compact Travel Charger','Electronics','physical',3500),('Creative Coding Sessions','Education','online_course',2900)],
 'AU':[('Melbourne Brew Lab','Coffee','online_course',4200),('Coastal Trail Map Pack','Outdoor','digital',2300),('Camp Coffee Kit','Coffee','physical',4900),('Night Sky Photography','Photography','online_course',4600),('Surf-inspired Art Prints','Home & Living','physical',3300),('Mindful Travel Audio','Digital Experiences','digital',1900)],
 'CA':[('Backcountry Skills Course','Outdoor','online_course',3600),('Trail Navigation Planner','Outdoor','digital',2100),('Forest Lightroom Presets','Photography','digital',2500),('Maple Wood Coffee Scoop','Coffee','physical',1900),('Everyday Wool Beanie','Fashion','physical',3200),('Landscape Composition Lab','Education','online_course',4100)],
 'SG':[('Mobile Creator Workshop','Photography','online_course',3500),('Digital Portfolio Kit','Digital Experiences','digital',2200),('Coffee Recipe Atlas','Coffee','digital',1600),('Compact Tech Organizer','Electronics','physical',2900),('Urban Garden Course','Home & Living','online_course',2800),('Creative Business Class','Education','online_course',3800)],
 'CH':[('Alpine Photo Walk Guide','Photography','digital',1900),('Precision Coffee Scale','Coffee','physical',4200),('Mountain Safety Class','Outdoor','online_course',3100),('Swiss Design Resources','Digital Experiences','digital',2300),('Minimal Ceramic Cup','Home & Living','physical',2700),('Visual Storytelling Lab','Education','online_course',3600)],
 'SE':[('Nordic Coffee Rituals','Coffee','online_course',39000),('Forest Trail Journal','Outdoor','digital',22000),('Nordic Light Presets','Photography','digital',29000),('Scandinavian Design Course','Education','online_course',45000),('Wool Trail Socks','Outdoor','physical',27000),('Calm Workspace Objects','Home & Living','physical',34000)]}


def seed(db, reset=False, user_id=None):
    if not db.get(Currency,'JPY'):
        for code,name,exponent in CURRENCIES:db.add(Currency(code=code,name=name,exponent=exponent))
        db.flush()
        for code,name,map_id,currency,lon,lat in COUNTRIES:
            db.add(Country(code=code,name=name,map_id=map_id,currency=currency,longitude=lon,latitude=lat))
        for uid,(name,persona) in PERSONAS.items():
            db.add(User(id=uid,display_name=name,persona=persona))
        db.flush()
        for uid in PERSONAS:db.add(InterestProfile(user_id=uid,budget_jpy=15000))
        stamp=datetime.combine(DEMO_DATE,datetime.min.time(),tzinfo=timezone.utc)
        pid=0
        for country_index,(code,_,_,currency,_,_) in enumerate(COUNTRIES):
            for index,(name,category,kind,price) in enumerate(CATALOG[code]):
                pid+=1
                physical=kind=='physical'
                db.add(Product(id=pid,name=name,category=category,kind=kind,
                    description=f'A fictional {kind.replace("_"," ")} from the Commerce Radar Demo Merchant, inspired by {code}. No real seller or fulfillment.',
                    image_url=f'/images/product-{CAT_IMAGES[category]}.svg',
                    equivalence_group='demo-trail-bottle-v1' if name=='Ultralight Trail Bottle' else None))
                db.flush()
                shipping=(10000 if currency=='SEK' else 900) if physical else 0
                taxes=int((Decimal(price)*Decimal('.10')).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                total=int((Decimal(price+shipping+taxes)/100*RATES[currency]*Decimal('1.035')).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                unknown_shipping=code=='GB' and index==5
                unknown_tax=code=='AU' and index==4
                db.add(Offer(id=pid,product_id=pid,country_code=code,currency=currency,local_price=price,
                    shipping=None if unknown_shipping else shipping,taxes=None if unknown_tax else taxes,other_fees=0,
                    available_in_japan=False if code=='US' and index==4 else True,
                    available_in_us=False if code=='US' and index==4 else True,checkout_usd=int((Decimal(total)/Decimal('145')*100).quantize(Decimal('1'))),stock=25,paypal_eligible=not (unknown_shipping or unknown_tax) and not(code=='US' and index==4),
                    checkout_jpy=total if not(unknown_shipping or unknown_tax) else None,
                    comparison_reference_jpy=6500 if name=='Ultralight Trail Bottle' else None,
                    product_url=None,refund_terms='Fictional demo: no real delivery. Digital access limited to the United States; refund terms are illustrative, not a real sale contract.',
                    verified_at=stamp))
        for sid,title,mult in [('balanced','Balanced discovery','1'),('strong-yen','Stronger yen scenario','0.90'),('weak-yen','Weaker yen scenario','1.10')]:
            db.add(DemoScenario(id=sid,title=title,current_multiplier=mult,description='Synthetic FX scenario; not current market rates.'))
        for i,(currency,rate) in enumerate(RATES.items()):
            trend=Decimal(['0.08','0.04','0.06','-0.03','0.02','0.01','-0.02','0.10'][i])
            for age in range(91):
                value=rate*(1+trend*Decimal(age)/90)
                db.add(ExchangeRate(base=currency,quote='JPY',rate=str(value.quantize(Decimal('.000001'))),
                    rate_date=DEMO_DATE-timedelta(days=age),source='synthetic',fetched_at=stamp))
    if reset:
        db.execute(delete(Purchase).where(Purchase.source=='synthetic_global', *([Purchase.user_id==user_id] if user_id else [])))
        db.execute(delete(SavedOpportunity).where(*([SavedOpportunity.user_id==user_id] if user_id else [])))
        # Input-hashed AI caches are retained; other users are not reset.
        for profile in db.scalars(select(InterestProfile).where(*([InterestProfile.user_id==user_id] if user_id else []))):
            profile.overrides_json=None
            profile.budget_jpy=15000
            profile.budget_usd=15000
    if reset or not db.scalar(select(Purchase.id).where(Purchase.source=='synthetic_global').limit(1)):
        rng=random.Random(2026)
        histories={1:[('Coffee Beans','Coffee'),('Coffee Grinder','Coffee'),('Brewing Equipment','Coffee'),('Ceramic Mug','Home & Living')],
                   3:[('Hiking Shoes','Outdoor'),('Trail Jacket','Outdoor'),('Backpack','Outdoor'),('Travel Camera Strap','Photography')],
                   4:[('Camera Lens','Photography'),('Editing Software','Digital Experiences'),('Creative Course','Education'),('Creator Tools','Digital Experiences')]}
        for uid,items in histories.items():
            if user_id and uid!=user_id:
                for _ in range(36):rng.randint(20,150)
                continue
            for index in range(36):
                name,category=items[index%len(items)]
                db.add(Purchase(user_id=uid,product_name=name,category=category,merchant_name='Fictional Local Store',country_code='US',
                    amount=rng.randint(20,150)*100,currency='USD',purchased_at=DEMO_DATE-timedelta(days=index*5+1),source='synthetic_global'))
    db.commit()
