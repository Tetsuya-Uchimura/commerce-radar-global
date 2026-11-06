from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from .models import MigrationState, Offer, User, Country, Currency, Purchase, DemoScenario

def migrate_us(db):
    if db.get(MigrationState,'usd-v1'):return
    for offer in db.scalars(select(Offer)):
        if offer.checkout_usd is None and offer.checkout_jpy:
            offer.checkout_usd=int((Decimal(offer.checkout_jpy)/145*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        offer.available_in_us=offer.available_in_japan
        offer.refund_terms=offer.refund_terms.replace('Japan','United States')
    for user in db.scalars(select(User)):user.home_currency='USD'
    # Only synthetic stories change denomination; actual app payments are immutable.
    for purchase in db.scalars(select(Purchase).where(Purchase.source=='synthetic_global',Purchase.currency=='JPY')):
        purchase.amount=int((Decimal(purchase.amount)/145*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        purchase.currency='USD';purchase.country_code='US'
    for scenario in db.scalars(select(DemoScenario)):
        scenario.title=scenario.title.replace('yen','US dollar')
    for code,name,map_id,currency,lon,lat in [('JP','Japan','392','JPY',138,37),('DE','Germany','276','EUR',10,51)]:
        if not db.get(Country,code):db.add(Country(code=code,name=name,map_id=map_id,currency=currency,longitude=lon,latitude=lat))
    db.add(MigrationState(key='usd-v1',value='Additive USD quotes and US personas; historic payment amounts unchanged'))
    db.commit()
