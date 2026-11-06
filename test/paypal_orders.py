"""100 JPY の Sandbox 注文を作成し、購入者の承認後に Capture する。"""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from uuid import uuid4

from dotenv import load_dotenv
from test.paypal_sandbox_check import NoRedirect

BASE = 'https://api-m.sandbox.paypal.com'
STATE = Path(__file__).resolve().with_name('.paypal-order.json')


def request(method, path, token=None, body=None, request_id=None):
    headers = {'Accept': 'application/json'}
    if token is None:
        credentials = f'{os.environ["CLIENT_ID"]}:{os.environ["CLIENT_SECRET"]}'
        headers['Authorization'] = 'Basic ' + base64.b64encode(credentials.encode()).decode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        data = urlencode({'grant_type': 'client_credentials'}).encode()
    else:
        headers['Authorization'] = f'Bearer {token}'
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode() if body is not None else None
    if request_id:
        headers['PayPal-Request-Id'] = request_id
        headers['Prefer'] = 'return=representation'
    req = Request(BASE + path, data=data, headers=headers, method=method)
    with build_opener(NoRedirect()).open(req, timeout=30) as response:
        return json.load(response)


def save(state):
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
    temporary.replace(STATE)


def show(order):
    print(f'Order ID: {order["id"]}')
    print(f'Order status: {order["status"]}')
    captures = [c for unit in order.get('purchase_units', [])
                for c in unit.get('payments', {}).get('captures', [])]
    for capture in captures:
        amount = capture.get('amount', {})
        print(f'Capture ID: {capture["id"]} / {capture["status"]} / '
              f'{amount.get("value")} {amount.get("currency_code")}')
    completed = (order['status'] == 'COMPLETED' and bool(captures)
                 and all(c['status'] == 'COMPLETED' for c in captures))
    if completed:
        print('決済結果 COMPLETED を確認しました。')
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'status', 'capture'])
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().with_name('.env'))
    if not all(os.getenv(key, '').strip() for key in ('CLIENT_ID', 'CLIENT_SECRET')):
        raise ValueError('.env に CLIENT_ID / CLIENT_SECRET を設定してください。')
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    if args.action != 'create' and not state.get('order_id'):
        raise ValueError('先に create を実行してください。')
    token = request('POST', '/v1/oauth2/token')['access_token']
    if args.action == 'create':
        # 再実行でも同一キーを使い、通信失敗時の重複作成を防ぐ。
        if state.get('order_id'):
            order = request('GET', f'/v2/checkout/orders/{state["order_id"]}', token)
        else:
            if not state:
                state = {'create_request_id': str(uuid4()), 'capture_request_id': str(uuid4())}
                save(state)
            order = request('POST', '/v2/checkout/orders', token, {
                'intent': 'CAPTURE',
                'purchase_units': [{'description': 'PayPal AI Hackathon Sandbox test',
                                    'amount': {'currency_code': 'JPY', 'value': '100'}}],
                'payment_source': {'paypal': {'experience_context': {
                    'shipping_preference': 'NO_SHIPPING',
                    'user_action': 'PAY_NOW',
                    'return_url': 'http://localhost:8765/approved',
                    'cancel_url': 'http://localhost:8765/cancelled',
                }}},
            }, state['create_request_id'])
            state['order_id'] = order['id']
            save(state)
        show(order)
        for link in order.get('links', []):
            if link['rel'] in ('approve', 'payer-action'):
                print(f'購入者の Sandbox アカウントで承認してください:\n{link["href"]}')
        return 0
    order_id = state['order_id']
    if not re.fullmatch(r'[A-Z0-9]+', order_id):
        raise ValueError('保存された Order ID が不正です。')
    order = request('GET', f'/v2/checkout/orders/{order_id}', token)
    if args.action == 'capture':
        if order['status'] == 'COMPLETED':
            return 0 if show(order) else 1
        if order['status'] != 'APPROVED':
            show(order)
            print('購入者の承認後に capture を再実行してください。')
            return 1
        units = order.get('purchase_units', [])
        amount = units[0].get('amount', {}) if len(units) == 1 else {}
        if amount.get('currency_code') != 'JPY' or amount.get('value') != '100':
            raise ValueError('注文金額が 100 JPY と一致しません。')
        request('POST', f'/v2/checkout/orders/{order_id}/capture', token, {}, state['capture_request_id'])
        # Capture 応答だけでなく、注文照会でも確定結果を確認する。
        order = request('GET', f'/v2/checkout/orders/{order_id}', token)
        return 0 if show(order) else 1
    show(order)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except HTTPError as exc:
        print(f'PayPal API エラー: HTTP {exc.code}', file=sys.stderr)
        try:
            error = json.load(exc)
            print(f'種類: {error.get("name", "unknown")} / Debug ID: {error.get("debug_id", "unknown")}', file=sys.stderr)
            for detail in error.get('details', []):
                print(f'Issue: {detail.get("issue", "unknown")}', file=sys.stderr)
        except (ValueError, OSError):
            pass
        sys.exit(1)
    except (URLError, TimeoutError, OSError, ValueError, KeyError):
        print('実行失敗: 設定、保存した注文情報、ネットワークを確認してください。', file=sys.stderr)
        sys.exit(1)
