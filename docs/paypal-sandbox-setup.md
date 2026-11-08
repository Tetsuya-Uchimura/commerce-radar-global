# PayPal Sandbox setup for judges

Commerce Radar supports **Simulation** and **PayPal Sandbox**, never Live. Sandbox
uses test accounts and no real money. Only explicitly labelled fictional
**Commerce Radar Demo Merchant** products use this checkout. HARIO, KINTO and other
external product discoveries are not purchased through it. OpenAI and Channel3
are independently optional and are unnecessary for Sandbox checkout.

This guide's PayPal interface labels were checked against official documentation
on **2026-11-08**; no authenticated dashboard session or new payment was used to
write it. Dashboard layouts/localization can vary. Start with the
[Docker quick start](docker-quickstart.md); keep **http://localhost:5173** throughout.

## 1. Developer account and the two test roles

Open the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/).
Sign in with your developer/PayPal account, or register through that site. A Live
payment is not part of this setup. PayPal's [Sandbox overview](https://developer.paypal.com/sandbox-testing/overview/)
explains that test identities are separate from real customer accounts.

Go to **Testing Tools → Sandbox Accounts**. Existing default accounts can be
reused. Identify **Business** (seller) and **Personal** (buyer). For additional
roles, choose **Create account**, the account type and **Country/Region**, then
create it. Wait for successful creation. Current documentation describes default
accounts and their generated test credentials in
[Sandbox accounts](https://developer.paypal.com/sandbox-testing/accounts).

For each test account, use its **Settings** menu → **View/Edit account** →
**Login Info** to inspect the test login. If a password was changed, it may no
longer be displayed; use the documented **Change password** procedure for that
Sandbox account if necessary. Do not change your real PayPal account password
just to resolve a Sandbox login.

### Business seller

Keep track privately of the Business account that will own the REST application.
Sign into [PayPal Sandbox](https://www.sandbox.paypal.com/) with that account's test
email/password to inspect seller **Activity** / **Transactions** (localized names
may differ). A developer login, Business Sandbox login and REST Client Secret
are different credentials. The app's Business association determines where its
payments appear; see PayPal's
[associated Sandbox account instructions](https://securepayments.paypal.com/us/cshelp/article/how-do-i-access-the-sandbox-account-associated-with-my-rest-api-test-credentials-ts1497).

### Personal buyer

Use a different **Personal** Sandbox account for approval. Check that account's
details and test balance/funding information in the developer tools; an account
still being created or with unusable test funding cannot complete the demo.
Sign in only on PayPal's own Sandbox authentication/approval page. Do not enter
buyer credentials into Commerce Radar, source files, `.env` or `.env.docker.local`.
After payment, its Sandbox account activity provides the buyer-side record.

## 2. Select a Sandbox REST app for the intended Business account

In the Developer Dashboard, open **Apps & Credentials** and choose **Sandbox**.
Reuse the appropriate default REST app, or choose **Create App**. For a new app,
give it a name, choose the merchant app type when asked, and select the intended
Sandbox Business account. Open the app and verify its associated account before
copying the **Client ID** and **Client Secret**. These are an API credential pair,
not the Sandbox email/password. Use neither Live values nor older NVP/SOAP
username/signature credentials. These steps follow
[PayPal REST API setup](https://developer.paypal.com/api/get-started/) and
[REST app creation](https://securepayments.paypal.com/us/cshelp/article/how-do-i-create-paypal-rest-api-credentials-ts1949).

Keep the Secret private. Commerce Radar exchanges this pair for an OAuth token
on the backend only; no token, Secret or buyer password goes into the React bundle.
The backend's PayPal host is fixed to `https://api-m.sandbox.paypal.com`.

## 3. Configure Commerce Radar without touching the developer .env

Create a new ignored optional file safely.

PowerShell:

```powershell
if (-not (Test-Path -LiteralPath .env.docker.local)) {
    Copy-Item -LiteralPath docker/env.example -Destination .env.docker.local
}
notepad .env.docker.local
```

macOS/Linux:

```bash
if [ ! -e .env.docker.local ]; then
  (umask 077; cp docker/env.example .env.docker.local)
fi
${EDITOR:-vi} .env.docker.local
```

Fill only the required server-side API values. This template deliberately contains
no credentials; empty values keep the integration off.

```dotenv
CLIENT_ID=
CLIENT_SECRET=
OPENAI_API_KEY=
CHANNEL3_API_KEY=
```

Use plain `KEY=value`, without shell `export` or surrounding quotes: this Compose
file reads raw env values. Leave the unrelated integrations blank if not needed.
The local file is excluded from Git and Docker contexts. Container environments
are accessible to Docker administrators; do not share environment dumps or full
rendered configuration. See the
[secret-handling design](docker-quickstart.md#interpolation-injection-and-secrets).

```bash
docker compose config --quiet
docker compose up --build -d
# After changing a runtime key:
docker compose up -d --force-recreate --wait backend
docker compose ps
```

Reopen the app/reselect your persona after backend recreation. The **PayPal Sandbox ·
buyer approval required** radio becomes selectable when both API values are set.
For a status-only check without displaying keys:

```bash
docker compose exec -T backend python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/demo/status')); print('Sandbox credential pair present:', d['sandbox_configured'])"
```

**Configured means presence, not verified authentication.** No OAuth/order/capture
is sent by this status check. Incorrect nonempty values are rejected on the actual
manual checkout request. No keys is a supported Simulation-only setup.

## 4. Explicit manual Sandbox purchase

These steps send a Sandbox order/payment only when **you** initiate them.

1. Open `http://localhost:5173`, select **Coffee Enthusiast**, and find a fictional
   Demo Product. If real cards are active, switch to **Demo Products** first.
2. Open an eligible **Commerce Radar Demo Merchant** item. Read its fixed quote,
   **USD** currency, quantity and fictional-product disclaimer. Quotes vary by
   item; do not assume an old video's amount is the current quote.
3. Select **Review checkout conditions**. Change **Simulate · no PayPal API** to
   **PayPal Sandbox · buyer approval required**. Confirm the final USD amount.
4. Click **Continue to PayPal Sandbox**. The backend creates an Orders v2 order
   with a saved idempotency key; the browser opens the real PayPal Sandbox page.
5. Verify the HTTPS Sandbox host. Use the **Personal** test buyer's credentials
   on PayPal, check the amount and seller, then approve the test purchase. Prior
   PayPal login cookies may mean there is no new login prompt; approval is still
   required. Use a separate browser profile for another buyer if necessary.
6. PayPal returns to `/payment/{local_order_id}?approved=1` on localhost:5173.
   Nginx serves React at that direct URL. Keep the same browser/persona/session;
   after a backend restart reselect the purchasing persona.
7. Click **Refresh status** if needed. Only an actual approved order enables
   **Capture approved payment**. A success URL by itself does not authorize money.
8. Click **Capture approved payment** once. Wait for **PAYPAL SANDBOX · USD PAYMENT**
   and **COMPLETED**. A `PENDING` capture is not completion. On a network error,
   refresh/retry the same saved order, not an unrelated new checkout.
9. Record the receipt's PayPal **Order** and **Capture** identifiers privately.
   Select **View updated history** and confirm one `sandbox` purchase. Repeated
   capture/reconciliation must not duplicate the history entry.
10. In a separate browser profile, sign into the associated **Business** Sandbox
    account. Open its activity/transaction details and inspect the completed
    merchant-side transaction, filters, amount/currency and identifiers.
11. Sign into the **Personal** Sandbox account and inspect its payment activity
    and detail/receipt. Preserve the distinct buyer-side identifier when shown.

The app implements its own server-side Orders v2 flow; judges do not need to
install PayPal's sample JavaScript integration. Official context:
[Standard Checkout](https://developer.paypal.com/studio/checkout/standard/getstarted),
[Orders v2](https://developer.paypal.com/api/orders/v2),
[idempotent API requests](https://developer.paypal.com/api/rest/reference/idempotency/).

## 5. Correlating the records accurately

Start with the app's local receipt route (a local UUID, **not** the PayPal Order ID).
The receipt/API saved record contains the PayPal Order ID, Capture ID, mode,
amount, currency and verified status. The backend verifies the remote order's
purchase unit/reference, currency/amount and completed capture before recording
history. At the Orders API level, the order response links its own `id` to
`purchase_units[].payments.captures[].id`; those identifiers serve different roles.

Compare the merchant transaction's identifier to the recorded Capture ID wherever
the dashboard exposes it, then confirm amount **and currency**, status, date/time
(including timezone), seller and buyer. Check the app's associated Business account,
not just a similarly named test store. Equal USD amounts do not establish a match.
Opening a previously completed local receipt does not create a new order.

Buyer and seller can have different transaction identifiers, as PayPal explains in
[its transaction-ID guidance](https://history.paypal.com/us/cshelp/article/why-are-there-different-buyer-and-seller-transaction-ids-for-the-same-transaction-ts2265).
When the account details provide a related transaction/receipt reference, follow
that explicit relationship and record both IDs privately. **This application does
not implement a buyer-to-seller ID crosswalk.** If the available dashboard records
do not expose an identifier-backed relation, keep buyer activity labelled
independently observed/unmatched; do not claim identity from amount/date alone.
An authorized PayPal transaction report/support lookup may be needed to resolve
that relationship. No reporting permission expansion or new payment is necessary
merely to write a demonstration caption.

## 6. Safe recovery and evidence

- **Cannot sign in:** confirm Personal Sandbox role and Login Info, not developer
  or Business credentials. Test accounts are not real PayPal customer logins.
- **Credentials rejected/wrong merchant:** choose the correct app under Sandbox,
  correct the API pair in the local file, recreate the backend and reload. Do not
  repoint existing payment rows or change their amount/status.
- **Return 404:** rebuild the frontend Nginx image; an API ownership error instead
  requires the original persona/DB. See the Docker troubleshooting table.
- **Approved but not completed:** refresh the saved order; capture only when
  approved. Do not manufacture a COMPLETED screenshot or reset a payment row.
- **Seller record missing:** approval alone is insufficient; verify a completed
  capture, associated Business account and transaction filters.
- **After restart:** reload/reselect the persona. The named volume preserves saved
  orders and payments; deleting the volume is not a session fix.

Mask emails, account/card/phone details, credentials and transaction metadata in
public screenshots. Keep the Sandbox label, amount/currency and status readable.
Simulation receipts explicitly say no PayPal transaction. A screenshot from an
earlier native checkout is historical evidence, not proof of a new Docker payment.
See [the verification report](docker-verification.md) for the exact tests performed.
