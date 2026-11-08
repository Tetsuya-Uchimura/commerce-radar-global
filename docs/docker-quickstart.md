# Docker quick start

Commerce Radar runs as two Linux containers: a Node-built React frontend served
by Nginx on **127.0.0.1:5173**, and a single-worker Python/FastAPI backend on the
Compose network. SQLite lives in the project's named `radar-data` volume at
`/app/data/global_radar.db`, with writable WAL/sidecar storage. No host development
database is mounted. The backend has no published port.

## Requirements and default mode

Windows 11: Docker Desktop running with Linux containers. macOS: Docker Desktop.
Linux: Docker Engine and the Compose plugin. Use Compose **2.30 or newer** for the
optional raw-format environment file. Both amd64 and arm64 are supported by the
selected official image families; this change is actually tested on Windows
Docker Desktop / Linux amd64. Other hosts are documented, not claimed as tested.

```bash
docker version
docker compose version
git clone https://github.com/Tetsuya-Uchimura/commerce-radar-global.git
cd commerce-radar-global
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Open **http://localhost:5173** after both services show healthy. The loopback bind
prevents LAN/public exposure. Initial downloads require Internet access and may
take time; there is no fixed startup-time promise. No environment file is required.
For an existing native development server, stop its frontend before using port
5173; do not run both on that port.

| Feature | No keys | Optional configuration |
|---|---|---|
| Persona, synthetic history, map, deterministic strategy | Available | None |
| Statistical explanation / concierge fallback | Labelled fallback | OpenAI enables AI interpretation/explanation |
| Current daily FX | Frankfurter connectivity, no key | Historical snapshot remains explicitly historical |
| Automatic product cards | Labelled fictional Demo Products | Channel3 key enables bounded automatic real search |
| Dated official listing evidence | Separate curated provider | Prices can be stale; pending destinations stay disabled |
| Simulated checkout | Available, no PayPal transaction | None |
| PayPal Sandbox checkout | Disabled | Sandbox Client ID + Secret, manual buyer approval |
| PayPal Live | Unsupported | Do not supply Live credentials |

The README includes a five-minute walkthrough. Price, listing currency,
storefront market, seller origin, shipping and tax evidence remain separate.
Neither a favorable FX region nor an unknown purchase total proves a cheapest
market. A manual priority override is not an automatic model conclusion.

## Optional APIs: a separate local file

Create the ignored file **only if it does not already exist**.

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

Use unquoted `KEY=value` lines in this **raw** env file; do not add shell `export`
statements. `$`, `#` inside a value are literal. An empty value disables that
integration. Do not put buyer credentials in this file.

```dotenv
CLIENT_ID=
CLIENT_SECRET=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-6-luna
CHANNEL3_API_KEY=
```

Each integration is independent. PayPal does not require OpenAI/Channel3. New keys
take effect after container **recreation**, not just `restart`:

```bash
docker compose config --quiet
docker compose up -d --force-recreate --wait backend
docker compose ps
```

Reload/reselect the persona afterward. The frontend never receives API keys.
`APP_URL=http://localhost:5173`, the absolute Docker DB URL, demo mode and Sandbox
URL are fixed in Compose and take precedence over this optional file. The PayPal
client also hardcodes the Sandbox host; changing an env value cannot enable Live.

### Interpolation, injection and secrets

Compose can read a root `.env` for **interpolation**; that does not automatically
inject it into containers. Our YAML uses no `${...}` or bare variable pass-through.
Only the optional **`.env.docker.local` `env_file`** injects user settings, and only
into the backend. The developer `.env` is neither mounted nor copied. Optional
files and raw format are supported by the official
[Compose environment documentation](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/).

Environment variables remain visible to Docker administrators through container
inspection. Keep the local file private and don't share raw inspections, environment
dumps, full rendered Compose config or browser storage. Use `config --quiet` for
validation. Docker [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/)
can mount service-specific files, but this app reads environment variables and has
no `_FILE` interface. The minimal judge setup deliberately avoids a new secret
loader/manager. Do not invent `_FILE` settings that the backend will ignore.

## Health, logs, lifecycle and persistence

```bash
docker compose ps
docker compose exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status)"
docker compose exec -T frontend wget -q -O - http://127.0.0.1:8080/api/health
docker compose logs --tail=80 backend frontend
docker compose stop
docker compose start
docker compose down
docker compose up -d
```

Access logs are disabled in both services to avoid logging checkout URLs. Logs
can still contain error/provider details; review locally and redact before sharing.
Do not run `env`, `printenv`, an unrestricted `docker inspect` or rendered
`docker compose config` when handling real keys.

Data survives restart/recreation/rebuild/`down`. Default volume name is
`commerce-radar_radar-data`; `-p` changes the project prefix. Containers use nonroot
UIDs, dropped capabilities and read-only root filesystems; only the DB volume and
temporary directories are writable. One backend worker preserves in-memory
sessions/payment locks. A restart clears sessions but not saved orders/history.

For an ordinary demo reset use **Demo Reset** in the application: existing completed
payments are preserved. To reset **only Docker data completely**, first check the
project and stop it. **The next command permanently deletes this Compose project's
named volume, including its Docker payment history. It does not touch the native
Windows DB. Execute only when that deletion is intended.**

```bash
docker compose down --volumes
docker compose up --build -d
```

Do not use that destructive reset for a stale browser session or failed payment.

## PayPal redirect path

Browser → Nginx `/api` → backend → real PayPal Sandbox approval →
`http://localhost:5173/payment/{local_order_id}?approved=1` → SPA → backend order
lookup → **Capture approved payment** → server verification. Cancellation uses
`?cancelled=1`. Nginx preserves request URI, Host, Origin, cookies and the existing
`X-Commerce-Radar` marker, and serves `index.html` for direct frontend routes.
Backend API/asset 404s are not replaced with HTML. Dynamic backend DNS supports
container recreation. No checkout security rules were relaxed.

Use `localhost` throughout, not a mixture of IP and hostname. A new browser
session must select the purchasing persona before accessing its order. A return
URL alone is never approval/capture evidence. See the
[PayPal Sandbox setup guide](paypal-sandbox-setup.md).

## Troubleshooting

Commands below run from the repository root. No solution requires deleting the DB.
`up --force-recreate` renews environment values; `restart` does not.

| Symptom | Likely cause and exact check | Safe resolution / recreation |
|---|---|---|
| 1. Docker daemon unavailable | `docker version` has client but no server | Start Docker Desktop / Linux daemon; choose Linux containers. Retry, no data deletion. |
| 2. Compose unavailable/old | `docker compose version` | Install/update the Compose plugin/Desktop to ≥2.30. No app recreation until retry. |
| 3. Build fails | `docker compose build`; inspect failing download/compile stage locally | Restore registry/proxy access, retain locks, retry build. Do not put proxy credentials in Dockerfiles/build args. |
| 4. Port 5173 in use | PowerShell `Get-NetTCPConnection -LocalPort 5173 -State Listen`; Linux/macOS `lsof -iTCP:5173 -sTCP:LISTEN` | Stop the identified conflicting local frontend. Retry `up`; don't arbitrarily change the PayPal origin. |
| 5. Blank frontend | Browser DevTools Network: inspect JS requests; `docker compose ps` | Rebuild frontend (`docker compose up --build -d frontend`), hard reload. Missing JS must return 404, not SPA HTML. |
| 6. Backend unhealthy | `docker compose logs --tail=80 backend`; backend health command above | Fix startup/volume/network error, then `docker compose up -d backend`. No keys are required for health. |
| 7. API 401 | Reload app, reselect Coffee Enthusiast | In-memory session expired after backend restart. Browser must retain the session cookie on localhost. No volume reset. |
| 8. API 403 | DevTools request Origin and `X-Commerce-Radar: 1`; ensure URL is localhost:5173 | Use the same origin and application UI; don't disable the guard. Fixed Compose APP_URL is canonical. |
| 9. SQLite cannot write | `docker compose exec -T backend python -c "import os; print(os.access('/app/data', os.W_OK))"` | Remove custom host bind mounts/user overrides. Restore default named volume/UID. Do not chmod unrelated host files or erase history. Recreate backend after correcting mounts. |
| 10. Session invalid after restart | `docker compose ps`, then reload/reselect persona | Expected single-process memory behavior; orders remain stored. No recreation needed. |
| 11. OpenAI missing | App analysis/explanation source label | Expected statistical fallback. Optionally add only that key, recreate backend and reload. Never claim fallback is OpenAI. |
| 12. Channel3 missing | App product data mode / provider status | Expected Demo Products. Optionally add only that key and recreate backend. Real provider failure still uses honest cache/Demo fallback. |
| 13. Frankfurter unreachable | App FX warning and observation date; backend logs | Keep missing/stale labels; select the saved historical scenario explicitly. Restore egress; use normal FX refresh, no key needed. |
| 14. PayPal rejected | Checkout displays credential rejection; check Apps & Credentials in Sandbox | Use a matching Sandbox REST ID/Secret pair, not login password or Live values. Recreate backend after correction; retry the saved order, not a blind new purchase. |
| 15. Buyer cannot sign in | Developer Dashboard → Testing Tools → Sandbox Accounts → Personal → View/Edit account → Login Info | Use Personal Sandbox login on PayPal's own page; inspect/reset only that test account password if necessary. No app recreation. |
| 16. Redirect wrong origin | Inspect browser return URL and canonical localhost:5173 | Keep default APP_URL and hostname. Recreate backend if using an old custom Compose file; old orders retain old approval URLs. Do not modify saved payment records. |
| 17. Return 404 | Visit `/payment/<local-order-id>` directly; inspect whether response is HTML or API error | `docker compose up --build -d frontend` to load Nginx SPA config. An API 'Order not found' instead means wrong persona/DB, not routing. |
| 18. Approval but no Capture | On receipt choose **Refresh status**; inspect APPROVED/PENDING/COMPLETED | Capture only APPROVED with the same saved order. Retry safely; server reconciliation/idempotency prevents duplicate capture. Never alter status in SQLite. |
| 19. Seller activity absent | Sign in to the app's associated Business Sandbox account; inspect Activity/Transactions and date filters | Confirm capture COMPLETED, allow dashboard refresh and match identifiers. Approval alone is insufficient. No new payment merely to populate activity. |
| 20. Wrong merchant | Apps & Credentials → Sandbox → selected app's Business account | Use credentials for the intended seller; recreate backend. Earlier orders/payments still belong to their original merchant. |
| 21. Old frontend after rebuild | `docker compose up --build -d frontend`, hard reload | Rebuild image, not `restart` alone. No volume deletion. |
| 22. Clean install differs | Run `scripts/verify_docker_checkout.py` with .venv Python; confirm no `.env`, data or host dependencies copied | Use shipped locks, Compose file and separate optional env. Record missing provider/data conditions instead of copying the developer DB. |

## Maintainer verification

From the native development `.venv` (Docker itself does not require it):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts/audit_publication.py
.\.venv\Scripts\python.exe scripts/verify_docker_checkout.py
```

The last script requires a free port 5173 and creates a separate named project and
clean source copy under `.verification`. It tests actual Nginx proxying, a labelled
Simulation, direct routing, session guards, persistence and a real exported Docker
build context. Dummy PayPal values test configuration presence only, never OAuth
or Capture. It stops its containers by default and preserves its test volume;
`--keep-running` is useful for local browser checks. Its report includes the project
name for subsequent `docker compose -p <reported-project> down`. No developer
keys or payment DB are copied. Recorded outcomes are in
[docker-verification.md](docker-verification.md).
