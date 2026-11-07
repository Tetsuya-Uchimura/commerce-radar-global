# Commerce Radar — AI Shopping Strategy Engine

**Know What to Buy. Know Where to Buy.**

Supporting message: What you love. Where your dollar goes further.

## Current repository status — 2026-11-08 (JST)

The AI Shopping Strategy Engine is already merged into `main`: merge commit `a7fb8a0` (implementation `ebab01e`), following the FX merge `5af176e`. At the start of the final submission checks, local `main` and the recorded `origin/main` pointed to `a7fb8a0`. The final label/link/documentation polish builds on that baseline. Its original verification took place before commit and publication; the owner subsequently requested GitHub publication and integration into `main`. Consult the subsequent `main` history for the final integration commit. Repository visibility remains Private; this work makes no visibility change. MIT License is retained.

Current final verification and merchant-review instructions: [final-submission-check.md](final-submission-check.md). The historical sections below describe evidence collected at their stated dates, rather than tests rerun during the final polish.

## Architecture and data flow

The existing Python/React app is extended, not rebuilt. History statistics and current OpenAI category hypotheses feed the existing interest plan. Genuine Frankfurter daily observations support relative currency comparisons. A new deterministic strategy engine consumes that plan, selected reference period/currency, preferences and normalized real candidates.

The cache-only `/api/strategy/initial` supplies a conservative strategy without any FX/product/AI provider call, including cold/offline startup. `/api/discovery` then supplies refreshed daily evidence before external product search completes. `/api/products/automatic` replaces it with a version-matched, evidence-backed strategy alongside cards/map data. Query generation considers domestic/overseas/comparison priority rather than always appending a foreign currency. Existing query-scoped provider caches, quotas, single-flight locks, debounce, timeouts and stale-result guards remain.

`POST /api/strategy/explanation` accepts only the signature of a server-computed, persona-scoped strategy. It cannot accept client-invented prices or decisions. It rejects another persona's, expired, changed-history or changed-FX evidence. Existing OpenAI explanation caching and cost controls are reused. The prompt requests at most 65 words; oversized output falls back to the concise deterministic summary. Concurrent automatic enrichment and Ask AI Why recheck the same cache under a lock and use conflict-safe inserts, preventing duplicate calls/saves. Failure never blocks the card. Pure map/chart navigation reuses the same signature and explanation.

`POST /api/strategy/preference` persists auto/domestic/overseas/compare in existing per-persona ChatState. It clears incompatible old targets, and Clear Chat resets the preference. Concierge structured intent can apply the same preferences and receives the computed strategy/source facts to explain. AI cannot create orders or capture payments. The viewed card signature is passed to the concierge. Ask AI Why is an explicit explanation action: it reuses the scoped server card and cached explanation without an intent-model call or product search. Natural-language conversations can also reference the current card; outdated or other-persona signatures are not accepted.

No production dependency was added. No new shipping/tax verification or external-merchant checkout was implemented.

## Decision rules

Python calculates all numbers and selects the strategy; the LLM explains it.

1. Select the explicit category when present, otherwise the strongest measured/AI-blended interest.
2. Select usable real FX observations for the chosen period and, when supplied, target listing currency.
3. Require relevant products to match the primary interest and minimum personal-match score. Never derive merchant origin from listing currency.
4. **Explore Overseas:** an applicable, fresh foreign listing and price produce purchasing-power improvement **above 1%** and at least **USD 1** of hypothetical listing-price difference, with personal match at least 40/100. Both rate/reference and actual listing currency must agree.
5. **US Stores First:** usable currency observations are all within the neutral/marginal threshold or unfavorable, leaving no compelling currency reason for overseas priority. If a suitable US storefront is evidenced, suggest it; otherwise show an honest US-source search suggestion without a retailer.
6. **Compare Both:** meaningful FX without usable related prices, small/mixed signals, missing history, or other uncertainty prevents a stronger choice. Tiny absolute-dollar differences do not qualify for strong FX messaging.
7. Keep unique/interesting products in Personal Discovery even when FX is negative. Explicit user preferences change search priority; the output preserves the separate automatic assessment and never invents an economic advantage to justify an override.

Defaults: `STRATEGY_NEUTRAL_PERCENT=0.5`, `STRATEGY_MEANINGFUL_PERCENT=1`, `STRATEGY_MINIMUM_DIFFERENCE_USD=1`, `STRATEGY_MINIMUM_INTEREST=40`. Values are finite, nonnegative and validated (neutral ≤ meaningful; interest ≤100). These are configurable UX heuristics, not universal economic thresholds.

Existing Decimal formulas and half-up USD-cent rounding remain: purchasing-power change `(H/C−1)×100`; constant-local-price cost change `(C/H−1)×100`. The two percentages are different. Only an unchanged-local-price hypothetical is shown, never an observed historical product price. Strong FX candidate sections now apply strategy meaningfulness as well as factual currency/price gates.

## Evidence and source separation

The response separates `strategy`, `calculated_strategy`, `recommended_sources`, price/FX facts, market proof, access status, reason codes, limitations and next action. Confidence is an evidence label (`partial` / `search_suggestion`), not a calibrated probability.

- A USD price does not verify a US retailer. Explicit `storefront_market=US` needs a safe source URL, observation date and documented basis; current-mode proof older than 30 days is not used as current US-market evidence.
- The Apple adapter's official API explicitly requests the US store. This says nothing about a software seller's legal origin.
- The curated KINTO listing is supported by official published price metadata and an official FAQ discussing Western/Eastern USA delivery. It supports a US shopping-market source, not a legal-incorporation, per-item delivery-cost or payment-method claim.
- Foreign-currency listings without country proof stay **Origin Unknown**. Source URLs are observed, never constructed from a currency or invented retailer.
- Disabled/unsafe destinations do not enter source recommendations. User-pending destinations can be price-evidenced candidates, but their links remain disabled. The existing manual merchant allow/exclude list was not relaxed.
- US storefronts, foreign-currency listings, and market-unverified USD/unknown-currency listings are separate comparison sections. Items are not assumed like-for-like; no market is declared cheaper.
- Shipping, tax, customs, settlement and delivered-price verification remain out of scope and Unknown unless independently evidenced.

## UI and actions

The home-page full-width **Your AI Shopping Strategy** panel shows the main recommendation, primary interest, selected currency focus, comparison period, evidence chips, short explanation and actual sources/access labels. It stacks on mobile. Detailed currency controls are expandable so the world map remains visible; reference-period switching remains directly available.

Explore Recommended Products opens the real-product view with interest/currency context. View Currency Trends opens the working daily chart. Compare Markets sets comparison priority and shows the three exploration sections. Ask AI Why explains the current strategy through the concierge. None is a payment action.

All four existing map layers remain. Gold marker rings show strategy search focus: US for domestic priority, relevant currency regions for overseas/comparison. Underlying FX colors are unchanged. A US focus is not a mathematical claim that all foreign markets are worse, and currency focus is not seller-country evidence.

## Genuine historical demonstration

Run from the project root:

```powershell
.\.venv\Scripts\python.exe scripts/strategy_demo.py
```

The script uses the archived genuine `fx_observed_snapshot.json` and immutable `strategy_historical_prices.json`, dated **2026-11-07**, plus an explicitly synthetic Coffee-interest profile. It performs no network, payment or developer-DB writes. Later live curated refreshes do not overwrite this archive. Historical conversions/budget filters use saved rates; historical market proof is evaluated against the scenario date, not presented as current proof.

| Case | Genuine observed evidence and explicit conditions | Result |
|---|---|---|
| EUR / Coffee | Observed EUR 59.90 HARIO Europe listing, saved positive 90D EUR movement and ≥USD 1 hypothetical difference | Explore Overseas |
| JPY / Coffee | Saved 90D JPY comparison is neutral; KINTO provides a separately evidenced US storefront source | US Stores First |
| EUR / Coffee, USD 10 cap | Meaningful EUR movement exists, but no recorded relevant EUR product meets the stated listing cap | Compare Both |

These are historical scenarios, not three simultaneous current-market recommendations. The third uses an explicit real budget condition rather than fabricating a price or changing FX data.

## Actual external/source verification

Publisher price metadata was read for the curated products, including [KINTO SCS-S04 brewer 2cups](https://kinto-usa.com/products/27574), observed at **USD 24.80**. Its [official FAQ](https://kinto-usa.com/pages/faq) explicitly describes USA delivery regions and USD currency. Shipping totals and tax were not calculated or claimed.

The [HARIO Europe listing](https://www.hario-europe.com/products/v60-ceramic-immersion-colour-dripper-switch-02-size) was observed at **EUR 59.90**. GBP and JPY observations remain in the curated set. Dates and sources are stored with each item; no price was supplied by an LLM.

Actual Chromium verification showed Explore Overseas for the Coffee/EUR source, an explicit user-priority override to US Stores First with a US focus ring (not a claim that live FX was neutral), working real-products and FX-chart routes, no page exceptions, and a 390px mobile viewport without horizontal overflow. Market overrides were restored to Automatic after the check. This did not edit purchase history or execute a payment. Existing completed Sandbox evidence was not recreated.

Automated tests use mocked FX/product/LLM data for edge cases; their results are not external merchant verification. Live/current strategies may change as rates, product availability and evidence freshness change. Channel3 may still return mostly USD results, which never acquire an unrelated foreign-FX advantage. Missing external keys retain labelled automatic Demo Products with an honest strategy/search suggestion.

## Under-three-minute recording plan

1. **0:00–0:20:** show the hero message and actual strategy card immediately.
2. **0:20–0:50:** Coffee Enthusiast, history and current measured/OpenAI interests. Avoid duplicating synthetic transactions merely for filming.
3. **0:50–1:20:** inspect actual 90D FX and reference dates; show that tiny gains do not force overseas priority.
4. **1:20–1:50:** demonstrate the resulting strategy. To reproduce all outcomes independently of live rates, clearly label the archived historical script/scenario conditions above.
5. **1:50–2:15:** show an actual recommended shopping source, observed price/currency, market evidence and unknown costs/access conditions. Use Curated official listings if Channel3 provides no usable foreign listing.
6. **2:15–2:35:** Ask AI Why; explain evidence rather than claiming savings or legal seller location.
7. **2:35–2:55:** show existing genuine USD Sandbox COMPLETED evidence for a clearly fictional Demo Merchant, explicitly as a prior capture. Do not imply that an external listing was purchased through the demo account.

No video was overwritten or recreated in this revision. No new real/Sandbox payment, external-merchant purchase automation, GitHub push or visibility change is part of this work. Existing secrets and completed payment data remain unchanged.

## Historical implementation verification — 2026-11-07

Checks executed for the original implementation (2026-11-07); see the final-check report for the subsequent rerun:

- Backend: **139 passed**, including the existing PayPal regression suite and a two-session explanation-cache concurrency regression. One existing Starlette/httpx deprecation warning remains.
- Frontend: **46 passed** across seven test files. This includes the strategy panel, source/access evidence, action routing, reference-period changes, navigation without extra product calls, and existing automatic discovery tests.
- Production TypeScript/Vite build: **passed**.
- Clean dependency install and first backend startup: **passed**, using `.verification/clean-20261107-233952`, without developer .env, DB or node_modules.
- Publication audit: **passed**, 119 candidate files, 13 ignored-path checks, no forbidden files or known credential/private-key matches.
- Cache-only initial strategy was observed responding in approximately 0.08 seconds on the local machine; this is a local observation, not a performance guarantee.
- Actual scoped strategy explanation returned the HARIO EUR source, explicit explanation intent, no search actions, and preserved USD Sandbox verification. Its text came from OpenAI; no price/rate was created by the LLM.
- A separate real natural-language request, “Find coffee products from US stores first,” returned OpenAI structured intent, a domestic preference, US Stores First, and the sourced KINTO US-market listing at USD 24.80. The automatic assessment remained separately visible as Compare Both. Automatic preference was restored after verification.
- Actual desktop/mobile Chromium checks: no page exceptions, valid product/FX navigation, correct US search-focus ring, 366px panel width in a 390px viewport, document width 390px.

The concurrency bug discovered during live verification was fixed by checking the cache again after acquiring the explanation lock and using conflict-safe SQLite inserts. The regression verifies a single model call for two concurrent requests. No model upgrade or new service was introduced.

## Historical implementation changed-file inventory — 2026-11-07

New files:

- `backend/shopping_strategy.py`
- `backend/fixtures/strategy_historical_prices.json`
- `frontend/src/ShoppingStrategy.tsx`
- `frontend/src/__tests__/ShoppingStrategy.test.tsx`
- `scripts/strategy_demo.py`
- `tests/test_shopping_strategy.py`
- `docs/shopping-strategy.md`

Modified backend/data files: `backend/ai.py`, `backend/automatic_discovery.py`, `backend/conversation.py`, `backend/curated.py`, `backend/enhancements.py`, `backend/fixtures/curated_products.json`, `backend/fx_opportunities.py`, `backend/main.py`, `backend/products.py`, `backend/search_plan.py`.

Modified frontend files: `frontend/index.html`, `frontend/src/App.tsx`, `frontend/src/AutomaticProducts.tsx`, `frontend/src/FXOpportunities.tsx`, `frontend/src/MapLayerControls.tsx`, `frontend/src/WorldMap.tsx`, `frontend/src/api.ts`, `frontend/src/global.css`, `frontend/src/ui.tsx`, `frontend/src/useAutomaticDiscovery.ts`, `frontend/src/useRadar.ts`, `frontend/src/__tests__/App.test.tsx`, `frontend/src/__tests__/setup.ts`.

Other changes: `scripts/refresh_curated.py`, `tests/test_ai.py`, `tests/test_automatic_discovery.py`, `.env.example`, `README.md`, `docs/fx-driven-discovery.md`, `docs/implementation-status.md`.

Historical development state before integration: work was performed on `feature/shopping-strategy`, based on `5af176e`. It was subsequently committed as `ebab01e`, merged into `main` as `a7fb8a0`, and pushed. The final submission polish follows that implementation. MIT License, actual .env, PayPal configuration/payment records, video assets and their Git exclusions are preserved.

