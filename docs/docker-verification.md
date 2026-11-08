# Docker judge setup — implementation and verification

Verified locally on **2026-11-08**, on branch `main`. This report records local
validation before publication; publishing is a separate owner-authorized step.
Setup instructions are maintained in English. No repository visibility change
or new Sandbox transaction was part of this work.

## Implementation

Added:

- `compose.yaml`
- `.dockerignore`
- `docker/backend.Dockerfile`
- `docker/frontend.Dockerfile`
- `docker/nginx.conf`
- `docker/env.example`
- `docs/docker-quickstart.md`
- `docs/paypal-sandbox-setup.md`
- `docs/docker-verification.md`
- `scripts/verify_docker_checkout.py`
- `tests/test_docker_setup.py`

Modified:

- `README.md` — judge quick start, walkthrough and guide links; native Windows procedure retained.
- `.env.example` — blank optional PayPal defaults instead of placeholder credentials.
- `.gitignore` — exclude optional Docker secret material in addition to existing local env rules.
- `scripts/audit_publication.py` — check Docker local env/secret paths and private media, including force-tracked files.
- `tests/test_publication_audit.py` — regressions for force-tracked local/private artifacts.

Application frontend/backend behavior, checkout endpoints, calculation logic,
database schema and session/payment safety code were not changed. The MIT License,
existing developer `.env`, payment records and final video were preserved.

### Runtime and connection

- Official `python:3.13-slim-bookworm`; locked Python dependencies; nonroot UID10001;
  one Uvicorn worker listening on internal port8000.
- Official `node:22-bookworm-slim` build stage, `npm ci`, TypeScript/Vite production
  build; official `nginx:1.30-alpine` final stage running as UID101 on port8080.
- Only Nginx publishes **127.0.0.1:5173**. It proxies `/api/` without changing paths,
  Host, Origin, cookies or the existing same-origin marker, and supplies SPA fallback
  for direct `/payment/{local_order_id}` requests. API/asset404s remain404s.
- Named `radar-data` volume, absolute SQLite URL, writable WAL/sidecars. No native
  DB bind mount. Health checks, healthy dependency ordering, dropped capabilities,
  read-only root filesystems and temporary writable directories are configured.
- `.env.docker.local` is optional, raw-format, backend-only runtime injection.
  Root `.env` is neither injected, mounted nor copied. No secrets/build args enter
  the frontend build. Compose secrets were considered; no unsupported `_FILE`
  convention or extra secret service was introduced. Docker administrators can
  inspect runtime env values; that tradeoff is documented.
- Base runtime families are pinned by version, not `latest`; their patch updates
  can change future image digests. Python/npm dependencies remain locked.

## Exact judge startup

On Docker Desktop Linux containers or Docker Engine with Compose≥2.30 and a free
local port5173:

```bash
git clone https://github.com/Tetsuya-Uchimura/commerce-radar-global.git
cd commerce-radar-global
docker compose up --build -d
docker compose ps
```

Open **http://localhost:5173**. No Python/Node installation or API keys are needed
on the judge's host. Synthetic personas/history, deterministic strategy/statistical
explanations, map, labelled Demo Products, historical FX demonstrations and
Simulation checkout are available. Current FX requires network access to
Frankfurter. Fresh OpenAI analysis, automatic Channel3 real discovery and real
Sandbox checkout need their respective independent optional credentials.

The English guide covers Business seller, Personal buyer, associated REST
app, Client ID/Secret versus login password, safe local configuration, recreation,
explicit approval/Capture and identifier-aware transaction checks. Native PayPal
buyer/seller IDs can differ; there is no automatic buyer/seller ID crosswalk in
Commerce Radar. Equal amounts alone do not prove a match.

## Executed verification

Host: Windows11, Docker Desktop4.43.2, Engine28.3.2, Compose2.38.2, Linux/amd64
containers. Dependency installs/builds occurred inside the Docker build stages.
The clean run used a source-only copy under
`.verification/docker-clean-20261108-164021` and its own project/volume
`radar-verify-20261108-164021`. No developer env, databases, `.venv`, node_modules,
dist, Git metadata or video assets were copied into that initial checkout.
Docker layer cache was reused for later isolation/restart runs; host dependencies
were not used in the container build. The first root build executed the locked
dependency installations and frontend build.

| Verification | Result | Evidence / scope |
|---|---|---|
| `docker compose config --quiet` | **Passed** | Root and isolated source configuration; no secret-bearing config printed |
| `docker compose build` | **Passed** | Both official-image builds, locked pip install and npm ci/build |
| Clean `up --build -d --wait` | **Passed** | Both containers healthy; no optional env or API keys |
| Frontend and proxied `/api/health` | **Passed** | Actual HTTP through localhost:5173 |
| Backend exposure / database configuration | **Passed** | Resolved config checked in memory; backend has no published port; loopback frontend and named volume |
| Runtime credential absence | **Passed** | All four API variables absent/empty in clean backend; no `.env` in runtime app; no frontend node_modules/env artifact |
| Session / Coffee persona / USD profile | **Passed** | Actual HTTP cookie HttpOnly/Lax, same-origin requests and seeded data |
| Marker and Origin rejection | **Passed** | Missing marker or unrelated origin returned403 |
| Strategy, Demo Products, world map | **Passed** | Actual HTTP + Chromium; source labels retained |
| Saved historical FX | **Passed** | HTTP returns explicit historical mode |
| API and asset404s | **Passed** | Not converted to index.html |
| Direct valid payment SPA | **Passed** | Actual Simulation order URL served React; Chromium showed its labelled COMPLETED simulated receipt |
| Simulation idempotency | **Passed** | Repeated local simulation capture created one history row; zero Sandbox rows |
| Backend restart/persistence | **Passed** | Saved budget and completed Simulation persisted; old cookie401, persona renewal succeeds |
| Optional PayPal-only env | **Passed** | Dummy values only: status false→true→false; raw `$`/`#` preserved; Channel3 still unconfigured. No authentication claim |
| Backend recreation/proxy DNS | **Passed** | HTTP recovered after both configuration recreations |
| Actual Docker build context | **Passed** | Scratch `COPY .` exported85 allowed source files. Synthetic env/DB/node_modules/dist/metadata/cache/video/payment/ZIP sentinels were excluded |
| `down` then `up --build` persistence | **Passed** | Separate actual lifecycle test retained budget, one completed simulated purchase and no Sandbox purchases |
| Chromium priority controls | **Passed** | All three manual strategies after asynchronous updates settled; manual override distinction retained |
| Chromium concierge | **Passed** | Ask AI Why produced `Statistical template · no LLM` with no key |
| Chromium history and page exceptions | **Passed** | History route works; no page exceptions |
| `.venv` `python -m pytest -q` | **Passed:160** | Offline/mock suite, including existing checkout amount/approval/capture/idempotency regression tests |
| Focused Docker/publication tests | **Passed:14** | Final focused rerun after Docker guide/audit work |
| `npm --prefix frontend test -- --run` | **Passed:50** | Seven test files |
| `npm --prefix frontend run build` | **Passed** | Native TypeScript/Vite production build, plus container production build |
| Publication audit | **Passed** | No forbidden publish files or known credential/private-key matches;16 ignored-path probes |
| Whitespace / changed-file review | **Passed** | `git diff --check`; no application/payment/License/video edits |
| Preservation | **Passed** | `.env`, native DB file and final MP4 hashes matched; native checkout-order rows/count unchanged |
| Restore native development frontend | **Passed** | Test containers stopped; original Vite frontend restored; existing backend health200 |

The full Python suite retained one existing Starlette/httpx deprecation warning;
it is not a test failure. An initial verifier call correctly received401 before
session creation; the harness was corrected to create the persona first.
Browser priority changes are asynchronous: the final browser script waits for
automatic discovery to settle before requesting an explanation. No guard was
relaxed to make either test succeed.

Private machine-readable reports, screenshots and source copies remain Git-ignored:

- `.verification/docker-judge/result.json` — clean Compose/HTTP/context checks.
- `.verification/docker-judge/browser-result.json` — actual Chromium checks.
- `.verification/docker-judge/down-rebuild-result.json` — full lifecycle persistence.
- `.verification/docker-judge/preservation-after.json` — developer asset preservation.
- `.verification/docker-judge/development-restored.json` — native frontend restoration.

Test containers/network were removed without `--volumes`; their isolated named
volumes are retained. The ordinary default `commerce-radar` project was not
populated with the developer's payment DB. The native Vite server has been
restored on5173, so stop it before starting a default Docker deployment there.

## Limitations / not performed

- **No new real Sandbox OAuth/order/approval/capture was executed in Docker.**
  Return/cancel URLs and safety behavior are covered by offline mocked regressions;
  the production SPA route/proxy/session behavior was verified with an actual
  local Simulation. New real approval/Capture still requires the owner's/judge's
  explicit manual checkout using their own Sandbox accounts.
- The pre-existing final-video Sandbox purchase is historical native-environment
  evidence, not evidence of a new Docker Sandbox transaction. No cross-account ID
  matching claim was added.
- No paid OpenAI/Channel3 call was made in this verification. Their existing
  automatic behavior was retained; no-key and error/cached/Demo contracts remain
  covered by regression tests. Frankfurter availability and current market data
  can vary; honest missing/stale/historical labels are retained.
- macOS, native Linux hosts and arm64 hardware were not directly tested. The
  Compose setup uses Linux images/named volumes and documented cross-platform
  commands; it does not bind a Windows development path.
- No authenticated PayPal Developer dashboard walkthrough, screenshot automation,
  public hosting, visibility change or Devpost upload was performed. GitHub
  publication is separate from the local verification described here.
- `scripts/verify_clean_checkout.py` was inspected and retained, but not rerun in
  this change. This task's clean dependency/build/startup verification was the
  actual Docker path. Native tests/build passed independently.

There are no unresolved failures in the executed final checks. Further manual
Sandbox verification should follow the English guide and use the
same saved order for safe retries; do not modify payment state or delete volumes
to manufacture a result.
