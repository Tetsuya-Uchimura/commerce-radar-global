""".env の資格情報で PayPal Sandbox の OAuth 接続を確認する。"""

import base64
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from dotenv import load_dotenv


class NoRedirect(HTTPRedirectHandler):
    """認証ヘッダーを別の接続先に転送しない。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main() -> int:
    load_dotenv(Path(__file__).resolve().with_name('.env'))
    client_id = os.getenv('CLIENT_ID', '').strip()
    client_secret = os.getenv('CLIENT_SECRET', '').strip()
    if not client_id or not client_secret:
        print('設定エラー: .env に CLIENT_ID と CLIENT_SECRET を設定してください。', file=sys.stderr)
        return 1

    # sandbox.paypal.com はログイン画面。API の接続先へ読み替える。
    configured_url = os.getenv('SANDBOX_URL', 'https://api-m.sandbox.paypal.com').strip().rstrip('/')
    allowed_urls = {
        'https://sandbox.paypal.com',
        'https://www.sandbox.paypal.com',
        'https://api.sandbox.paypal.com',
        'https://api-m.sandbox.paypal.com',
    }
    if configured_url not in allowed_urls:
        print('設定エラー: SANDBOX_URL に PayPal Sandbox の HTTPS URL を設定してください。', file=sys.stderr)
        return 1
    api_base = 'https://api-m.sandbox.paypal.com'
    credentials = base64.b64encode(f'{client_id}:{client_secret}'.encode('utf-8')).decode('ascii')
    request = Request(
        f'{api_base}/v1/oauth2/token',
        data=urlencode({'grant_type': 'client_credentials'}).encode('ascii'),
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            result = json.load(response)
        if not isinstance(result, dict) or not result.get('access_token'):
            print('接続失敗: レスポンスにアクセストークンがありません。', file=sys.stderr)
            return 1
    except HTTPError as exc:
        # 応答本文や認証情報はログに出さない。
        print(f'接続失敗: HTTP {exc.code}', file=sys.stderr)
        if exc.code == 401:
            print('Sandbox アプリの CLIENT_ID / CLIENT_SECRET を確認してください。', file=sys.stderr)
        return 1
    except (URLError, TimeoutError, OSError):
        print('接続失敗: ネットワーク、プロキシ、証明書またはタイムアウトを確認してください。', file=sys.stderr)
        return 1
    except (ValueError, UnicodeError):
        print('接続失敗: API の応答を JSON として読み取れませんでした。', file=sys.stderr)
        return 1

    print('PayPal Sandbox への接続・OAuth 認証に成功しました。')
    print(f'API: {api_base}')
    print(f'トークン有効期間: {result.get("expires_in", "不明")} 秒')
    print('アクセストークンおよび認証情報は表示・保存していません。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
