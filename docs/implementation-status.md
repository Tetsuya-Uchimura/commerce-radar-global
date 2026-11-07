# Commerce Radar — implementation and verification

## Current repository status — 2026-11-08 (JST)

The AI Shopping Strategy Engine is already merged into `main`: merge commit `a7fb8a0` (implementation `ebab01e`), following the FX merge `5af176e`. At the start of the final submission checks, local `main` and the recorded `origin/main` pointed to `a7fb8a0`. The final label/link/documentation polish builds on that baseline. Its original verification took place before commit and publication; the owner subsequently requested GitHub publication and integration into `main`. Consult the subsequent `main` history for the final integration commit. Repository visibility remains Private; this work makes no visibility change. MIT License is retained.

Current final verification and merchant-review instructions: [final-submission-check.md](final-submission-check.md). The historical sections below describe evidence collected at their stated dates, rather than tests rerun during the final polish.

## Historical US/USD enhancement record — 2026-11-04

## Phase 0 — audit and preservation

- Reviewed React/FastAPI/SQLite, purchase APIs, PayPal lifecycle, Frankfurter, OpenAI,
  map/catalog, tests and ignore rules. Git was uninitialized at this initial audit; the current repository is initialized and merged as described above.
- Created source ZIP and consistent DB backups at
  `.migration-backups/20261104-084956-us-enhancement/`.
- Existing `.env`, account credentials and successful legacy orders were not overwritten.
- Confirmed gpt-6-luna model access with the configured API key: HTTP 200.
- Decision: reuse the existing stack, add schema columns/tables, preserve historic
  payment currency/amount, and make all new estimates/default quotes USD-based.

## Phase 1 — US defaults and daily Frankfurter v2

- Implemented US delivery, USD budgets/estimates and new fixed USD Sandbox quotes.
- Stored/displayed USD-per-foreign-unit rates and correct inverse purchasing power.
- Added 1M/3M/6M/1Y/5Y/MAX charts, high/low/period changes, 30/90/365-day comparisons,
  common-observed-date 2–5 currency indices, source/retrieval dates and explicit retry.
- Preserved cached/synthetic source distinctions and stale warnings; no local observation
  interpolation is performed. Duplicate range requests are cached.
- Files: `backend/{fx,costs,discovery,us_migration,models,db,main}.py`, frontend USD types,
  `Enhancements.tsx`, map home marker, sidebar/profile/detail formatting.
- Real check: 8 foreign currency series; EUR 5Y 1,836 observations; JPY 1Y 375;
  latest observation 2026-11-04. Currency arithmetic/index tests pass.

## Phase 2 — editable history and automatic interest analysis

- Added validated add/edit/soft-delete plus scoped synthetic restore. Actual Sandbox,
  simulation payment and imported payment receipts are immutable.
- Added versioned 1.5-second debounce, serialized per-persona jobs, stale-result rejection,
  scoped cache, bounded tokens, timeout, transient retry/backoff and per-persona rate gate.
- OpenAI generates structured top/emerging interests, categories, uncertain intentions,
  price-range interpretation, novel ideas, explanation and missing information.
- Added before/after deterministic scores, feedback, preserved prior analysis on failure,
  manual reanalysis, API usage metadata and frontend polling. No sensitive attributes are inferred.
- Files: `backend/{analysis,history,enhancements,usage,models}.py`, `frontend/src/Enhancements.tsx`,
  `useRadar.ts`, `Pages.tsx`, history/analysis tests.
- Real gpt-6-luna analysis passed: initial request 1,667 input / 285 output tokens.
  A subsequent paid purchase triggered and completed analysis version 2.
- Tests cover CRUD/validation, protected payments, cache invalidation, stale versions,
  API failure preservation and scoped reset.

## Phase 3 — actual product/store discovery

- Implemented a hosted web-search provider using the existing OpenAI key, source/title
  normalization, HTTPS/public URL checks, duplicate removal, evidence-limited ranking,
  cache/rate limit and explicit failure state.
- Real results are derived only from actual search sources or citation annotations, not
  freely generated product objects. External products are Visit Store only.
- Files: `backend/products.py`, source normalization tests, RealProductSearch UI,
  country panels, real-product route and conversation search actions.
- Real check found 4 source product/store pages; no separate search API key was needed.
- Limitation: source metadata lacks independently verified structured prices, shipping,
  tax, origin, stock and reputation. These remain Unknown. No false cheapest/quality
  winner or budget qualification is asserted. A licensed priced-feed adapter remains
  a future extension; Channel3 was investigated but not integrated.

## Phase 4 — stateful structured concierge

- Added validated OpenAI intent extraction and allowlisted actions: filters, country
  selection, country comparison, chart currency/period, real search, and detail review.
- Persisted budget, category, preferred/excluded countries, digital/physical selection,
  goal and feedback per persona. Clear Chat clears only that persona's conversation.
- Added country side-by-side FX/demo/real-source views. The LLM has no payment tool.
- Files: `backend/conversation.py`, `ChatState`, `useRadar.ts`, `Pages.tsx`, `Concierge.tsx`.
- Real intent check: “Show the last year of EUR/USD” returned a validated show_fx action
  with EUR and 1Y; explanation was OpenAI-generated.
- UI integration covers map linkage, persona selection, chat actions, safe buy-intent
  detail opening, editable-history form, historical-period requests and quote separation.

## Phase 5 — USD payment, regression and handoff

- Kept the existing validated OAuth/create/approval/Capture/re-query/idempotency lifecycle.
  New orders use fixed server-owned USD cents; existing JPY orders remain supported.
- Actual USD Sandbox order for $39.45 was created, explicitly approved by the buyer,
  and verified COMPLETED with a COMPLETED Capture. Repeating Capture did not duplicate
  the history record. Exactly one matching immutable Sandbox purchase is stored.
- Automatic OpenAI reanalysis after that purchase completed at version 2; history and
  recommendation features include the new country/product.
- Updated README, environment example, online diagnostics, API schema and version 3.
- Ordinary tests use mocks and isolated SQLite; no external calls or payments are made.
- Latest final test/build totals are reported in the handoff. One upstream TestClient
  deprecation notice does not fail the backend suite.
- Secret scan checks the new source against existing configured credential values;
  databases, source backups, `.env`, dependencies and build outputs remain ignored.

## Remaining limitations

- Channel3 offers provide structured listing prices when configured; shipping, tax,
  origin and reputation remain Unknown. Live Channel3 authentication and app search were subsequently verified (see below).
- Actual-browser visual/mobile/keyboard QA is not established by jsdom tests.
- Local trusted demo only: no production identity, public hosting, real charges, external
  merchant settlement, payment webhooks/refunds or reservation-expiry worker.
- Backend jobs, sessions and request gates are process-local; use one uvicorn worker.
- No additional API key was created, no expensive model fallback occurred, and no GitHub
  publication or external deployment was performed.


Official digital-product provider: Real Products also supports the public
[Apple iTunes Search API](https://performance-partners.apple.com/search-api) for US App Store software.
No additional API key is needed. An actual search returned seven listings with seven
observed USD upfront prices. Storefront country does not establish seller origin.
Tax, in-app purchases, device/account eligibility and final total remain unverified;
external purchases use Visit Store. Text-only listings avoid reusing promotional media.
Results are cached for four hours with a 10-second per-persona search gate; Apple's
published approximate 20 requests/minute limit is subject to change.
Store ratings support a provisional quality-evidence leader, never a guaranteed
quality or cheapest-total claim. Physical-product price/shipping feeds remain incomplete.

Final verification: 43 backend tests and 8 frontend tests passed; production build passed.


## 3.1 — Analysis-to-real-product recommendation integration (2026-11-04)

- `backend/search_plan.py`: current AI top/emerging/preferred interests plus intentions
  and novel opportunities become versioned, attributable queries. Category frequency
  and recency remain visible. Emerging categories get an exploration slot. Stale AI is
  excluded immediately after an edit. Explicit category choices constrain the plan.
- `backend/analysis.py`, `backend/discovery.py`: concrete shopping-hypothesis prompt,
  prompt-version cache namespace and reproducible 70/30 statistical/AI category rubric.
- `backend/channel3.py`, `backend/products.py`, `backend/enhancements.py`: optional
  Channel3 structured offer adapter, automatic provider selection, plan endpoint,
  real-FX listing conversions, deterministic evidence scores and strict unknown-total
  handling. Source price/currency/domain/URL/retrieved time are normalized independently
  from AI. No external PayPal checkout, origin inference or guessed shipping/tax.
- `backend/conversation.py`: validated requires_search and provider intent drive searches,
  including keyword-free refinements. Budget/category/country/kind/exclusions and the
  same recommendation pipeline drive the returned UI actions. Deterministic keywords
  remain only as a labelled unavailable/offline fallback.
- `backend/main.py`: verified Sandbox currencies derive from completed captured orders,
  rather than the old hardcoded USD-awaiting-approval string; app version 3.1.
- `frontend/src/RealProducts.tsx`, `Enhancements.tsx`, `useRadar.ts`, `api.ts`, `App.tsx`,
  `Pages.tsx`, `components.tsx`, `Detail.tsx`: current-plan search proposals, real-product
  auto search on its dedicated page, guarded obsolete responses, country/budget linkage,
  FX metadata, separate listing estimate vs unknown total, prominent fictional badges,
  and accurate post-payment AI-pending wording. Analysis completion refreshes discovery
  from every workspace, not only the analysis panel.
- Setup: `.env.example` documents optional CHANNEL3_API_KEY, `requirements.txt` documents
  shared HTTP dependency (no new SDK required), package/lock versions are synchronized,
  `.gitignore` excludes verification outputs, `scripts/verify_clean_checkout.py` validates
  a clean install without secrets or existing data. Existing requirements-lock is valid.
- Tests changed/added: `tests/conftest.py` now performs the same US migration as startup;
  `tests/test_api.py`, `tests/test_discovery.py` reflect Japan/Germany coverage;
  `tests/test_recommendation_flow.py` covers the complete mocked flow, edited-history
  invalidation, Channel3 schema/errors, real-only FX/rounding/unknowns, Japanese intent,
  keyword-free refinement, no-search intent, and captured USD verification status;
  `frontend/src/__tests__/App.test.tsx` and `RealProducts.test.tsx` cover linked UI search,
  updated plan requests, budget/FX unknowns and obsolete-result suppression.

Validation: 49 backend tests and 11 frontend tests passed; production build passed.
Locked Python and npm installs plus production build and initial lifespan/seed/session/
USD-discovery/search-plan checks passed in a clean source copy. GitHub is not initialized
or published, so no literal remote clone was possible. Real online verification with
newly seeded fictional data returned Photography after adding Photography Course,
linked two real overseas source pages to the applied AI version, and interpreted Japanese
coffee-under-$100 into JP + 10000 cents + product search (three real source pages).
Original history/payment DB was not changed by that online test.

Channel3 live calls were subsequently verified after CHANNEL3_API_KEY was configured (see below). Official API
contracts were checked at https://channel3.ai/docs/guides/make-a-search and
https://channel3.ai/docs/guides/response-overview (2026-11-04); keyless/error/schema tests
pass. Real website source metadata still has no verified listing price; official Apple
prices remain supported. Full delivered totals and cheapest claims stay unavailable
when charges are unknown. Manual browser layout/mobile/keyboard QA remains outstanding.


## Channel3 live activation — 2026-11-04

User configured CHANNEL3_API_KEY in the existing .env. No key value was printed or
written to documentation. Backend restarted to load the new setting. Direct search
returned eight normalized offers; seven remained after the $100 sticker-price cap.
The actual app POST /api/products/search with provider=auto returned HTTP 200,
source Channel3 product API, seven listings, seven observed USD prices and seven USD
listing estimates. External checkout stayed disabled; shipping/tax/final totals stayed
Unknown. No additional payment or purchase-history edit was performed.


## Final v3.1 — automatic discovery and explicit source modes

Changed files:
- Added backend/product_runtime.py (startup probe, single-flight raw cache, failure
  circuit, persisted provider attempt limits and safe logging), backend/automatic_discovery.py
  (versioned source-mode envelope, fallbacks, evidence-only map groups).
- backend/products.py: shared bounded cache service, current-history novelty factor,
  evidenced cost-component validation, Best Discovery / Best Verified Value separation.
- backend/channel3.py: distinguish authentication, HTTP-rate-limit and timeout failures.
- backend/enhancements.py: automatic discovery and provider-status endpoints.
- backend/main.py: actual startup availability probe after seed/migration.
- backend/conversation.py: concierge may suggest Best Discovery while explicitly
  reserving Best Verified Value for fully evidenced costs.
- Added frontend/src/useAutomaticDiscovery.ts (shared automatic lifecycle, debounce,
  abort/version checks), frontend/src/AutomaticProducts.tsx (mode controls/cards,
  recommendations, unknown-origin group and explicit demo switch).
- frontend/src/useRadar.ts, App.tsx, Pages.tsx: initial/persona/analysis/chat/filter
  triggers, one shared result across routes, current result drives map/cards, guarded
  discovery responses. WorldMap.tsx: real-vs-demo legend and evidence-based labels.
- frontend/src/components.tsx, RealProducts.tsx, Enhancements.tsx, global.css: prominent
  Demo Product badges, Refresh terminology, country comparison delegates to shared
  radar rather than starting duplicate searches; responsive automatic controls/cards.
- tests/conftest.py, tests/test_automatic_discovery.py: isolated provider state/keys,
  A-D workflows, cache/missing-key/zero-results/failures, reanalysis/query updates,
  obsolete history versions, costs/origin evidence, cap, concurrency and startup probe.
- frontend/src/__tests__/App.test.tsx, useAutomaticDiscovery.test.tsx: full mounted app
  initial/persona scenarios, cache/demo/empty-result labels and switches, hook-based
  latest-analysis/condition debounce, route reuse and stale-result suppression.
- .env.example, README.md, docs/implementation-status.md and
  scripts/verify_clean_checkout.py: cost controls, modes and clean keyless startup checks.
  No new dependencies or secret edits were required.

Automatic triggers: initial ready persona/profile, persona switch, latest completed AI
analysis after add/edit/delete/payment/reset/profile feedback, chat filter/query changes,
explicit query/category/country/budget/provider changes. Pending AI settles first; failed
AI uses current statistical features. Page navigation alone reuses the shared result.

Modes: successful upstream result -> Real Products (even zero matches); fresh matching
cache or outage-compatible cache -> Cached Real Products; missing auto-provider key or
outage without compatible cached products -> Demo Products. Empty live results never
silently mix fictional items. Explicit user demo selection is distinguished from outage.

Cost controls: 650ms frontend debounce plus existing 1.5s analysis debounce; 4h raw cache,
7-day maximum outage fallback, per-query/persona/provider coalescing lock, 60s failure
circuit, persisted 6/minute and 60/rolling-day provider attempts per persona (including
failures), 2s gate, bounded timeout and zero provider retries. Polling and cached calls do
not count as upstream attempts. Startup makes one generic availability search and warms
its cache. Backend and frontend discard outdated analysis/persona/condition results.

Map: only seller-country facts with source and observation time enter live country
ranking (mean discovery match; not a delivered-value score). Ship-from, delivery countries
and currency are separate fields and require their own evidence. Current Channel3 offers
lack these country facts, so legitimate real listings are Origin Unknown and produce no
invented country scores. The demo-country map remains available with explicit labels.

Tests: 60 backend and 17 frontend tests passed; production build passed. Scenario A-D
coverage uses deterministic offline providers; direct real service and clean-start
checks are recorded below. PayPal/FX/history/profile/concierge regression tests remain
passing. Actual browser visual/mobile/keyboard QA remains manual; process-local sessions,
locks and debounce require the documented single-worker local deployment.


Final live verification (2026-11-04): with a newly generated synthetic-only DB, startup
Channel3 probe was available; Scenario A automatically returned 16 cached real merchant
offers and a Best Discovery. Repeating the same request used cache. After adding a
fictional Photography Course and running actual OpenAI analysis, Scenario B automatically
changed to the photography/camera query and returned 11 real offers at history version 2.
All 11 were Origin Unknown and generated zero country scores; Best Verified Value
remained unavailable. Original user history and payments were not read by that verifier.

Clean-source check also passed: fresh .venv install from requirements-lock, npm ci,
production build, first seed/migration, USD discovery, automatic keyless Demo Products
and provider status=unconfigured, without .env or existing DB. No secrets were copied.


## Product destination checks — 2026-11-04

- Added backend/link_access.py: bounded public-IP-pinned GET checks, HTTP redirect and
  error-page classification, transparent agent, no credentials/cookies, independent
  result cache, bounded shared worker registry and no CAPTCHA/JavaScript execution.
- backend/products.py checks links after local filtering and excludes non-reachable
  results from recommendations; backend/conversation.py rechecks cached chat candidates;
  backend/automatic_discovery.py excludes failed/unconfirmed links from map rankings.
- Added frontend/src/LinkAccess.tsx; AutomaticProducts.tsx separates confirmed responses
  from unavailable/unconfirmed destinations. useAutomaticDiscovery.ts and RealProducts.tsx
  carry/render access metadata, reason/date/cache scope. Broken/unsafe links are disabled;
  browser-only retry options explicitly say unverified. No accessible-browser guarantee.
- tests/test_link_access.py covers soft errors, CAPTCHA, tracker interstitials, redirect
  failures, public-IP pinning, private/mixed DNS and cache/recommendation behavior.
  tests/conftest.py mocks probes to keep ordinary tests offline. Frontend link tests and
  existing App/RealProducts fixtures cover accurate scope labels and disabled destinations.
- requirements.txt now explicitly declares httpcore; the existing lock already pins it.
  README and this report document the limits; .env was not edited.

Live observations: the provided affinity.net /disabled.html returned HTTP 200 and was
correctly classified unavailable. An existing Hario product link returned HTTP 200 and
was server reachable. The Williams Sonoma Channel3 link returned an HTTP-200 human
verification page at buy.trychannel3.com; this is restricted, not a confirmed merchant
page. No challenge or regional restriction was bypassed. User-browser behavior may differ.

Validation: 85 backend tests, 20 frontend tests and production build passed. The updated backend was restarted. Pending checks use the existing automatic refresh envelope to complete without an additional paid provider search.


## Verified Shopping Opportunities / Discovery Markets — 2026-11-04

- Added backend/discovery_markets.py; backend/main.py exposes explicit exploration routes
  alongside the profile. Routes combine current AI/statistical interest queries, optional
  selected category, supported search countries and exclusions. Every route carries
  seller_location_verified=false and opportunity_score=null. No claim of product stock,
  shipping support, merchant origin, country specialties or better prices is inferred.
- backend/automatic_discovery.py now keeps known-but-restricted seller locations separate
  from truly unknown origin. Only reachable, source-confirmed seller locations enter
  verified map rankings; search targets/currency/domains cannot create those facts.
- Added frontend/src/mapLayers.ts and MapLayerControls.tsx. Discovery Markets is the
  default live layer, with amber target highlights, Explore/Search target labels and
  interest/query explanations rather than numeric opportunity scores. Verified Shopping
  Opportunities uses teal confirmed-location matches and a visible empty-evidence
  explanation plus a route back to exploration. Switching layers does not re-search.
- frontend/src/api.ts, useRadar.ts, WorldMap.tsx, App.tsx, AutomaticProducts.tsx and
  global.css integrate layer-specific legends, strip/sidebar labels and explicit target
  vs origin text. The map layout flows around controls to avoid covering the map. The
  keyless Demo Catalog remains automatic and clearly fictional. Existing source modes,
  link checks, AI analysis, cache, automatic triggers, FX and Sandbox flows are unchanged.
- Added tests/test_discovery_markets.py, frontend/src/__tests__/mapLayers.test.tsx and
  an App.test.tsx integration scenario for colored-but-unscored exploration, empty
  verified evidence, target selection/exclusions, history-driven query changes, strict
  origin grouping, Demo preservation and layer switches without another product call.
- Added scripts/audit_publication.py and tests/test_publication_audit.py; .gitignore now
  also excludes local zip archives, standalone DB/sidecars and caches. The audit uses
  actual Git ignore rules in an ignored temporary repository, scans all visible files
  and any real tracked index, checks exact configured secrets/key/private-key formats,
  and reports paths only. Tests prove that copying a secret into normal source or
  force-tracking .env is detected. No actual workspace Git repository/index was created.
- README and this report document behavior, audit commands and scope/limitations.

Validation: 91 backend tests and 24 frontend tests passed; production build passed.
The existing automatic search, failure/cache fallback, keyless demo, history/AI and
USD/legacy Sandbox regression suites remain passing. Publication audit checks 13 ignored
path cases; no dependency folders, local DB/archive/cache, dotenv secrets or key values
were found in the current Git-visible candidate set. backend.zip stays local but ignored.
No API key was modified, no user file deleted and no commit/upload/deployment performed.
Manual browser layout/mobile/keyboard QA remains outside the automated test evidence.


Restricted-link UX correction: frontend/src/LinkAccess.tsx now enables external navigation only for status=reachable. Try in browser was removed for restricted/unknown/login/rate-limit states; disabled/error destinations remain inactive. Dedicated CSS replaces the generic horizontal warning layout, fixing the narrow broken Access restricted label shown in the screenshot. LinkAccess tests cover every non-reachable state and missing checks. This frontend fix does not claim to observe redirects behind a human-verification challenge, and does not bypass it.


Product visibility correction: AutomaticProducts.tsx now separates unverified access
(restriction/human verification/login/timeout/rate limit) from observed unavailable/unsafe
destinations. Unverified provider listings stay visible in an expanded candidate section;
only unavailable/unsafe links remain collapsed. All non-reachable destination buttons
stay disabled; recommendations and verified map evidence are not relaxed. App.test.tsx
adds regression cases for visible restricted candidates and separately grouped broken
links. No backend, secret, provider/cache or payment behavior changed.


## User browser-review table applied — 2026-11-04

- backend/merchant_access.json records all 38 supplied rows: 35 allow, three exclude
  (academy.com, belk.com, jcpenney.com), representative-browser-review scope/date and
  manual review mode. No API keys are stored there.
- backend/merchant_access.py canonicalizes merchant domains, supports www/subdomain
  boundaries and reads the user-maintained policy. backend/products.py filters excluded
  merchants even from cached results and allows user-confirmed discovery candidates.
- backend/link_access.py does not probe reviewed links or unreviewed merchants in manual
  mode. User-confirmed status preserves provenance; cached server CAPTCHA observations
  are separate. Explicitly unavailable/unsafe destinations are still blocked. New sites
  await user review. backend/automatic_discovery.py still requires source-attributed
  seller location for country ranking; browser approval cannot establish geography.
- frontend/src/LinkAccess.tsx, AutomaticProducts.tsx show User-confirmed merchant and
  enable Visit Store for T merchants without falsely labelling them Server reachable.
- tests/test_merchant_access.py and LinkAccess.test.tsx cover exact 35/3 configuration,
  domain boundaries, cached exclusions, user approval overriding a server challenge
  without networking, unknown-site manual review and retained unsafe/broken protection.
  tests/conftest.py retains isolated automated-probe fixtures for legacy checker tests.
- README and this report document scope. Existing user secrets/history/payments and raw
  provider caches are preserved; user-site review creates no origin/value evidence.

Validation: 96 backend tests, 32 frontend tests and production build passed. Git-visible publication audit passed for 103 candidate files with zero forbidden artifacts or detected credential/private-key files. Backend restarted for policy activation.

## Historical FX-driven concept refinement — 2026-11-07

Implemented the FX-first currency selection/search/evidence pipeline. See [fx-driven-discovery.md](fx-driven-discovery.md) for formulas, actual EUR/GBP/JPY checks, complete changed-file list, limitations and the three-minute judging sequence. Verification: 114 backend tests, 36 frontend tests, production build, clean install and publication audit passed. No push occurred during that verification stage; the FX changes were subsequently merged and pushed as `5af176e`. Visibility was not changed; existing credentials and final video were preserved.

## Historical AI Shopping Strategy Engine implementation — 2026-11-07

Implemented deterministic Explore Overseas / US Stores First / Compare Both decisions, a cache-only immediate strategy endpoint, the responsive home strategy panel, evidenced shopping-site recommendations, contextual actions and map focus, per-persona overrides, explicit Ask AI Why without intent/product-search calls, and conservative comparison sections. Tiny FX differences no longer receive strong FX-find messaging. Existing FX, search, caches, history, model settings and Demo Merchant Sandbox boundaries remain.

Final verification: **139 backend tests and 46 frontend tests passed**; production build, clean environment install/startup and publication audit passed. Desktop/390px Chromium checks passed. A live explanation-cache concurrency bug was fixed and regression-tested; simultaneous same-evidence requests use one model call. Real natural-language domestic-priority intent and source selection were also confirmed, then restored to Automatic.

Real source metadata supports HARIO Europe EUR 59.90 and KINTO US-storefront USD 24.80, with the latter's official FAQ as market evidence. Archived genuine FX/price observations reproduce all three strategies without inventing live outcomes. The initial cache-only strategy responded in approximately 0.08 seconds locally; this is not a performance guarantee.

See [shopping-strategy.md](shopping-strategy.md) for architecture, thresholds, real versus mocked/historical evidence, complete changed-file inventory, limitations and the sub-three-minute recording sequence. The original verification preceded commit/merge/push from `feature/shopping-strategy`; integration subsequently completed as `a7fb8a0` on `main`. No visibility change, new payment or video overwrite occurred. Existing credentials and completed payment records were preserved.
