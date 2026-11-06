# PayPal Sandbox 接続サンプル

Python 3.10 以降で、次のコマンドを実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe paypal_sandbox_check.py
```

スクリプトと同じフォルダの `.env` に `CLIENT_ID` と `CLIENT_SECRET` を設定してください。
設定例は `.env.example` にあります。既存の環境変数がある場合はそちらを優先します。

OAuth API (`POST /v1/oauth2/token`) でアクセストークンを取得し、成功と有効期間を表示します。
認証情報とトークンは表示・保存しません。決済や注文の作成は行いません。
成功時の終了コードは 0、設定・通信・認証の失敗時は 1 です。

`SANDBOX_URL=https://sandbox.paypal.com` は API 用の
`https://api-m.sandbox.paypal.com` に読み替えます。本番環境には接続しません。
`EMAIL`、`PASSWORD`、`SANDBOX_REGION` はこの API 認証には不要です。

公式資料: https://developer.paypal.com/api/get-started/

## 100円の注文作成と Capture

```powershell
.\.venv\Scripts\python.exe paypal_orders.py create
```

表示された承認URLをブラウザで開き、販売者とは別の購入者用 Sandbox
アカウントでログインして100円の支払いを承認してください。
承認後は localhost:8765 に戻ります。このサンプルは Web サーバーを起動しないため
接続エラーになりますが、PayPal 側で承認が済んでいれば次に進めます。
キャンセルした場合は Capture できません。

```powershell
.\.venv\Scripts\python.exe paypal_orders.py status
.\.venv\Scripts\python.exe paypal_orders.py capture
```

Capture は APPROVED の注文に対してのみ実行し、注文と Capture の両方が
COMPLETED であることを照会で確認します。PENDING の場合は後で status を実行してください。
API 接続先は Sandbox に固定しています。トークンや購入者情報は保存しません。
注文IDと重複実行防止キーのみ `.paypal-order.json` に保存します。
create の再実行は同じ注文を表示します。別のテストを始める場合は、既存注文の
結果を確認してからこのファイルを別名に移してください。
通信失敗時は同じコマンドを再実行してください。PayPal の重複実行防止キーには
保存期限があるため、長時間経過後の再作成は先に Sandbox の履歴を確認してください。

公式資料: https://developer.paypal.com/whats-an-order/
