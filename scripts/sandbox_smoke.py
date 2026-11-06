"""Explicit online smoke test. Default: OAuth only. Never auto-captures."""
import argparse
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.paypal import paypal, PaymentError, money_value
from backend.db import init_db, Session
from backend.seed import seed
from backend import checkout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create-order', action='store_true', help='Create a fixed-USD Demo Merchant offer in Sandbox; buyer approval required.')
    parser.add_argument('--offer-id', type=int, default=2, help='Eligible synthetic offer ID (default: Lisbon Coffee Workshop).')
    args = parser.parse_args()
    paypal.token()
    print('Sandbox OAuth: OK (token not displayed or saved)')
    if args.create_order:
        init_db()
        with Session() as db, checkout.payment_lock:
            seed(db)
            order = checkout.create(db, 1, args.offer_id, 1, 'sandbox', str(uuid4()))
            print('App order:', order['id'])
            print('Amount:', money_value(order['amount'],order['currency']), order['currency'])
            print('PayPal order:', order['paypal_order_id'])
            print('Approval URL:', order['approval_url'])
            print('Return to the running app to explicitly capture after buyer approval.')


if __name__ == '__main__':
    try:
        main()
    except PaymentError as exc:
        print(exc.message, file=sys.stderr)
        sys.exit(1)
