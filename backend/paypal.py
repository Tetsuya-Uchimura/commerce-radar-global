"""Sandbox-only Orders v2 client, adapted from the verified test scripts."""
import os
import time
import threading
from decimal import Decimal
import httpx

SANDBOX = 'https://api-m.sandbox.paypal.com'
EXPONENTS = {'JPY': 0, 'USD': 2, 'EUR': 2, 'GBP': 2, 'AUD': 2, 'CAD': 2, 'SGD': 2, 'CHF': 2, 'SEK': 2}


class PaymentError(Exception):
    def __init__(self, message, code=502):
        self.message, self.code = message, code


def money_value(minor, currency):
    if currency not in EXPONENTS or not isinstance(minor, int) or minor <= 0:
        raise PaymentError('Unsupported currency or invalid amount.', 422)
    exponent = EXPONENTS[currency]
    return f'{Decimal(minor).scaleb(-exponent):.{exponent}f}'


def matches_amount(amount, minor, currency):
    try:
        return amount.get('currency_code') == currency and Decimal(amount['value']) == Decimal(money_value(minor, currency))
    except (ValueError, KeyError, ArithmeticError):
        return False


class PayPal:
    def __init__(self):
        self._token = None
        self._expires = 0
        self._lock = threading.Lock()

    def configured(self):
        return bool(os.getenv('CLIENT_ID') and os.getenv('CLIENT_SECRET'))

    def _request(self, method, path, **kwargs):
        try:
            with httpx.Client(timeout=25, follow_redirects=False) as client:
                response = client.request(method, SANDBOX+path, **kwargs)
            if not response.is_success:
                if response.status_code == 401:
                    self._expires = 0
                    raise PaymentError('PayPal Sandbox credentials were rejected. Check server configuration.', 502)
                raise PaymentError('PayPal could not process this request. Your order is saved; retry with the same order.', 502)
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (httpx.HTTPError, ValueError):
            raise PaymentError('PayPal Sandbox is temporarily unavailable. Your order is saved; retry safely.', 502) from None

    def token(self):
        if not self.configured():
            raise PaymentError('PayPal Sandbox credentials are not configured. Analytics and simulation remain available.', 503)
        with self._lock:
            if time.monotonic() >= self._expires:
                data = self._request('POST', '/v1/oauth2/token',
                                     auth=(os.environ['CLIENT_ID'], os.environ['CLIENT_SECRET']),
                                     data={'grant_type': 'client_credentials'})
                if not data.get('access_token'):
                    raise PaymentError('PayPal authentication response was incomplete.')
                self._token = data['access_token']
                self._expires = time.monotonic()+max(0, int(data.get('expires_in', 0))-60)
            return self._token

    def call(self, method, path, body=None, key=None):
        headers = {'Authorization': f'Bearer {self.token()}', 'Accept': 'application/json',
                   'Content-Type': 'application/json', 'Prefer': 'return=representation'}
        if key:
            headers['PayPal-Request-Id'] = key
        return self._request(method, path, headers=headers, **({'json': body} if body is not None else {}))

    def create(self, order, product, app_url):
        if order.currency not in ('USD','JPY'):
            raise PaymentError('Only USD and legacy JPY Sandbox quotes are enabled.', 422)
        return self.call('POST', '/v2/checkout/orders', {
            'intent': 'CAPTURE',
            'purchase_units': [{'reference_id': order.id, 'custom_id': order.id,
                                'description': product.name[:120],
                                'amount': {'currency_code': order.currency, 'value': money_value(order.amount, order.currency)}}],
            'payment_source': {'paypal': {'experience_context': {
                'shipping_preference': 'NO_SHIPPING', 'user_action': 'PAY_NOW',
                'return_url': f'{app_url}/payment/{order.id}?approved=1',
                'cancel_url': f'{app_url}/payment/{order.id}?cancelled=1',
            }}},
        }, order.request_key)

    def get(self, order_id):
        return self.call('GET', f'/v2/checkout/orders/{order_id}')

    def capture(self, order_id, key):
        return self.call('POST', f'/v2/checkout/orders/{order_id}/capture', {}, key)


paypal = PayPal()
