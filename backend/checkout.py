from datetime import datetime, timezone, timedelta
import threading
from urllib.parse import urlparse
from uuid import uuid4
from sqlalchemy import select
from .models import Product, Offer, PaymentOrder, PaymentEvent, Purchase
from .paypal import paypal, PaymentError, matches_amount
from .config import APP_URL, DEMO_DATE

# Local MVP runs one uvicorn worker. SQLite serializes writes; this lock also
# serializes external calls so a retried Capture cannot race with another request.
payment_lock = threading.RLock()


def view(order):
    return {key: getattr(order, key) for key in ('id', 'offer_id', 'product_name', 'country_code', 'quantity', 'amount',
            'currency', 'mode', 'status', 'paypal_order_id', 'paypal_capture_id', 'approval_url')}


def owned(db, order_id, user_id):
    order = db.get(PaymentOrder, order_id)
    if order is None or order.consumer_id != user_id:
        raise PaymentError('Order not found.', 404)
    return order


def create(db, user_id, offer_id, quantity, mode, key, currency='USD'):
    if currency not in ('USD','JPY'):raise PaymentError('Only USD and legacy JPY checkout are enabled.',422)
    existing = db.scalar(select(PaymentOrder).where(PaymentOrder.request_key == key))
    if existing:
        if (existing.consumer_id, existing.offer_id, existing.quantity, existing.mode) != (user_id, offer_id, quantity, mode):
            raise PaymentError('Idempotency key already belongs to a different purchase.', 409)
        if existing.currency!=currency:raise PaymentError('Idempotency key currency mismatch.',409)
        order = existing
        offer = db.get(Offer, order.offer_id)
        product = db.get(Product, offer.product_id)
    else:
        offer = db.get(Offer, offer_id)
        product = db.get(Product, offer.product_id) if offer else None
        if product is None:
            raise PaymentError('Product not found.', 404)
        if (not offer.paypal_eligible or not (offer.checkout_usd if currency=='USD' else offer.checkout_jpy) or offer.available_in_us is not True
                or offer.source != 'Synthetic Demo Catalog'
                or offer.merchant_name != 'Commerce Radar Demo Merchant' or offer.product_url):
            raise PaymentError('Only eligible fictional Demo Merchant offers can use app checkout.', 422)
        quote=offer.checkout_usd if currency=='USD' else offer.checkout_jpy
        if quote <= 0 or quantity < 1 or quantity > 10:
            raise PaymentError('Invalid quantity, price, or currency.', 422)
        if offer.stock < quantity:
            raise PaymentError('Not enough stock for this order.', 409)
        if mode == 'sandbox' and not paypal.configured():
            raise PaymentError('Configure server-side PayPal Sandbox credentials first, or choose simulation.', 503)
        order = PaymentOrder(id=str(uuid4()), consumer_id=user_id, offer_id=offer.id, product_name=product.name, category=product.category, country_code=offer.country_code,
                             quantity=quantity, amount=quote*quantity, currency=currency, mode=mode, request_key=key, capture_key=str(uuid4()))
        offer.stock -= quantity  # reserve once; retained on ambiguous network failures
        db.add(order)
        db.commit()
    if order.status == 'CREATING':
        if mode == 'simulation':
            order.status = 'AWAITING_CONFIRMATION'
        else:
            result = paypal.create(order, product, APP_URL)
            links = [link['href'] for link in result.get('links', []) if link.get('rel') in ('payer-action', 'approve')]
            if not links or not result.get('id'):
                raise PaymentError('PayPal did not return an approval URL. Retry the saved order.')
            url = urlparse(links[0])
            if url.scheme != 'https' or url.hostname not in ('www.sandbox.paypal.com', 'sandbox.paypal.com'):
                raise PaymentError('Unexpected approval URL; checkout stopped.')
            order.paypal_order_id = result['id']
            order.approval_url = links[0]
            order.status = result['status']
        db.add(PaymentEvent(order_id=order.id, event_type='CREATED', event_status=order.status,
                            external_event_id=f'create:{order.id}'))
        db.commit()
    return view(order)


def verify_remote(order, remote):
    units = remote.get('purchase_units', [])
    if (remote.get('id') != order.paypal_order_id or remote.get('intent') != 'CAPTURE'
            or len(units) != 1 or units[0].get('custom_id') != order.id
            or units[0].get('reference_id') != order.id
            or not matches_amount(units[0].get('amount', {}), order.amount, order.currency)):
        raise PaymentError('PayPal order does not match the saved product, reference, or amount.', 409)


def record_completed(db, order, capture_id):
    existing = db.scalar(select(Purchase).where(Purchase.paypal_capture_id == capture_id))
    if existing and existing.paypal_order_id != (order.paypal_order_id or f'SIM-{order.id}'):
        raise PaymentError('Capture already belongs to another order.', 409)
    if not existing:
        db.add(Purchase(user_id=order.consumer_id, offer_id=order.offer_id,
                           product_name=order.product_name, category=order.category, country_code=order.country_code,
                           merchant_name='Commerce Radar Demo Merchant', quantity=order.quantity, amount=order.amount,
                           currency=order.currency, purchased_at=DEMO_DATE if order.mode == 'simulation' else datetime.now(timezone(timedelta(hours=9))).date(),
                           paypal_order_id=order.paypal_order_id or f'SIM-{order.id}',
                           paypal_capture_id=capture_id, source=order.mode))
        db.add(PaymentEvent(order_id=order.id, event_type='CAPTURE', event_status='COMPLETED',
                            external_event_id=capture_id))
    order.status = 'COMPLETED'
    order.paypal_capture_id = capture_id
    db.commit()
    if not existing:
        from .analysis import touch
        touch(db,order.consumer_id)


def sync_remote(db, order, remote):
    verify_remote(order, remote)
    captures = remote['purchase_units'][0].get('payments', {}).get('captures', [])
    if len(captures) > 1:
        raise PaymentError('Unexpected multiple captures; manual reconciliation is required.', 409)
    if captures:
        capture = captures[0]
        if not matches_amount(capture.get('amount', {}), order.amount, order.currency):
            raise PaymentError('Capture amount mismatch.', 409)
        if remote.get('status') == 'COMPLETED' and capture.get('status') == 'COMPLETED':
            record_completed(db, order, capture['id'])
            return
        order.status = 'PENDING' if capture.get('status') == 'PENDING' else capture.get('status', 'UNKNOWN')
        order.paypal_capture_id = capture.get('id')
    else:
        order.status = remote.get('status', 'UNKNOWN')
    db.commit()


def status(db, order):
    if order.mode == 'sandbox' and order.paypal_order_id and order.status != 'COMPLETED':
        sync_remote(db, order, paypal.get(order.paypal_order_id))
    return view(order)


def capture(db, order):
    if order.status == 'COMPLETED':
        return view(order)
    if order.mode == 'simulation':
        if order.status != 'AWAITING_CONFIRMATION':
            raise PaymentError('Simulation is not awaiting confirmation.', 409)
        record_completed(db, order, f'SIM-CAP-{order.id}')
        return view(order)
    if not order.paypal_order_id:
        raise PaymentError('Order creation is incomplete. Retry create using the same key.', 409)
    remote = paypal.get(order.paypal_order_id)
    sync_remote(db, order, remote)
    if order.status in ('COMPLETED', 'PENDING'):
        return view(order)
    if order.status != 'APPROVED':
        raise PaymentError('Approve the purchase in PayPal Sandbox before capturing.', 409)
    # Retry always uses the persisted capture key. On ambiguous failures the next
    # request queries PayPal before trying Capture again.
    paypal.capture(order.paypal_order_id, order.capture_key)
    sync_remote(db, order, paypal.get(order.paypal_order_id))
    return view(order)
