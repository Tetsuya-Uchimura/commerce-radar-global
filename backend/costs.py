"""Transparent landed-cost estimates. Unknown charges never become zero."""
from decimal import Decimal, ROUND_HALF_UP
import os

EXPONENTS = {'JPY': 0, 'USD': 2, 'EUR': 2, 'GBP': 2, 'AUD': 2, 'CAD': 2, 'SGD': 2, 'CHF': 2, 'SEK': 2}
D = Decimal


def major(minor, currency):
    return D(minor).scaleb(-EXPONENTS[currency])


def jpy(value):
    return int(value.quantize(D('1'), rounding=ROUND_HALF_UP))


def landed_cost(offer, fx, shipping_adjustment=0, conversion_percent=None):
    """All components use the offer's selling currency, not the country's currency."""
    conversion_percent = D(str(conversion_percent if conversion_percent is not None else os.getenv('ASSUMED_CONVERSION_PERCENT', '3.5')))
    if not conversion_percent.is_finite() or not 0 <= conversion_percent <= 20:
        raise ValueError('ASSUMED_CONVERSION_PERCENT must be a finite percentage from 0 to 20.')
    rate = D(fx['rate']) if fx and fx.get('rate') else None
    if rate is not None and (not rate.is_finite() or rate <= 0):
        rate = None
    unknown = []
    if rate is None:
        unknown.append('FX rate')
    components = {}
    raw = {}
    for label, value in [('product', offer.local_price), ('shipping', offer.shipping), ('taxes', offer.taxes), ('other_fees', offer.other_fees)]:
        if value is None:
            unknown.append(label)
            raw[label] = None
            components[label] = None
        else:
            converted = major(value, offer.currency)*rate if rate else None
            if label == 'shipping' and converted is not None:
                converted += D(str(shipping_adjustment))/100
            raw[label] = converted
            components[label] = int((converted*100).quantize(D('1'),rounding=ROUND_HALF_UP)) if converted is not None else None
    complete = not unknown
    subtotal = sum(raw.values()) if complete else None
    conversion = subtotal*D(str(conversion_percent))/100 if complete else None
    components['conversion_estimate'] = int((conversion*100).quantize(D('1'),rounding=ROUND_HALF_UP)) if conversion is not None else None
    # Sum displayed minor-unit components, so the visible receipt adds up exactly.
    total = sum(components.values()) if complete else None
    return {'currency': 'USD', 'components': components, 'total_usd': total,
            'known_subtotal_usd': sum(v for v in components.values() if v is not None),
            'unknown': unknown, 'complete': complete, 'conversion_percent': str(conversion_percent),
            'conversion_source': 'Assumed estimate, not PayPal fees or exchange rate',
            'fx_currency': offer.currency, 'fx_rate': str(rate) if rate else None,
            'shipping_adjustment_usd': shipping_adjustment, 'price_verified_at': offer.verified_at.isoformat(),
            'estimate_only': True, 'tax_note': 'Synthetic estimated taxes; not customs or tax advice.',
            'checkout_quote_usd': offer.checkout_usd}
