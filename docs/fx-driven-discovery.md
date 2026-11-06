# FX-driven discovery — implementation and verification

Verified 2026-11-07 (Asia/Tokyo). Work is on `feature/fx-driven-discovery`; no commit/push or repository visibility change was performed. Existing `.gitignore` changes excluding demo-video were retained. Existing .env, PayPal credentials and completed video were not edited. No new package dependency was needed.

## Resulting pipeline

Current history/statistics and OpenAI hypotheses → eight real Frankfurter currency comparisons → favorable currency target → interest/target-currency query → Channel3 observed offers plus clearly dated, relevant official price observations → original listing-currency validation → Decimal conversion/FX scoring → distinct FX-backed, personal-discovery and delivered-value selections → linked map/cards/concierge.

An emerging-interest query and the strongest established-interest query share the default bounded search, preserving both new interests and historical fit. Explicit category/query/currency conditions override that scope. A query's country/currency intent is never promoted to a fact about its returned listings. The original category counts remain inspectable.

Core formulas, historical reference dates, evidence gates, configurable weights and API/cache behavior are documented at the top of README. The existing cost assumptions apply only to Demo Merchant estimates; real products require actual complete cost evidence for Delivered Value. The standalone chart remains independent of paid product/AI searches.

## Actual market/product checks

The live API returned 2026-11-07 observations. At the inspected 90-day reference, SEK, EUR, AUD, CHF, GBP and CAD were favorable; JPY was neutral and SGD unfavorable. These classifications will change with data. Do not guarantee them at judging time.

EUR, GBP and JPY targeting was attempted through the real Channel3 pipeline once each, then repeated from cache. Returned sets contained USD listings and source-labelled curated foreign-currency observations. Foreign currency in that combined set must not be attributed to Channel3 without checking each item's source. The official-price snapshots were separately retrieved from publisher JSON-LD or Open Graph metadata, with no invented prices or locations.

| Actual source observation | Listing | Current FX equivalent | Hypothetical at 90D reference | Interpretation |
|---|---:|---:|---:|---|
| [HARIO Europe Ceramic Immersion Colour Dripper Switch 02](https://www.hario-europe.com/products/v60-ceramic-immersion-colour-dripper-switch-02-size) | EUR 59.90 | USD 67.20 | USD 69.11 | USD 1.91 lower under unchanged-EUR-price assumption |
| [Hario UK V60 Plastic 02 White](https://www.hario.co.uk/products/hario-v60-coffee-dripper-plastic-size-02-white) | GBP 9.00 | USD 12.10 | USD 12.12 | Very small FX difference; no delivered-value claim |
| [Kurasu HARIO V60, variant 01](https://jp.kurasu.kyoto/products/hario-v60-dripper) | JPY 2,750 | About USD 17.39 | Approximately unchanged | Neutral 90D FX; no favorable FX badge |

EUR USD purchasing-power advantage was approximately +2.85%; the constant-local-price USD cost change was approximately −2.77%. They use different denominators. Displayed dollar differences are differences of the displayed half-up-rounded USD cents. Neither value is an observed historical product price, discount, comparison with buying in the US, or a PayPal quote.

All these merchants remain **Origin Unknown** without location evidence. US delivery, shipping, taxes and payment conversion costs are unknown. They were not added to the user's approved merchant list. The existing manual-review policy leaves their destination links disabled (`user_pending`); they can appear as price/FX-evidenced candidates, but cannot become a confirmed-access winner. Best Verified Delivered Value remains unavailable. EUR metadata may require variant confirmation. Current live price eligibility expires after seven days; refresh the allowlisted official observations deliberately using scripts/refresh_curated.py.

The real concierge returned OpenAI structured intent and an OpenAI-generated explanation of the actual 90D comparisons. Its answer correctly treated USD listings as having no foreign-FX benefit. Numeric calculations and selections are supplied by Python. Existing low-cost model settings were retained.

## Verification

| Check | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -q` | 114 passed; one existing Starlette/httpx deprecation warning |
| `npm --prefix frontend test -- --run` | 36 passed, six test files |
| `npm --prefix frontend run build` | Passed, TypeScript + Vite production build |
| `scripts/verify_clean_checkout.py` | Passed: fresh venv locked install, npm ci, build, FastAPI lifespan/session, keyless automatic Demo, live-missing/historical FX checks |
| `scripts/audit_publication.py` | Passed; no forbidden files or known credential/private-key matches |
| Actual Chromium UI | No page exceptions; FX map and real computed price evidence visible |
| Existing PayPal tests | Included in the passing backend suite; no new buyer approval/Capture/Live payment |

Tests cover 30D/90D/1Y reference direction, separate power/cost percentages, half-up cents and JPY units, positive/neutral/negative FX, stale/missing data, USD exclusion, price/currency absence, personal-fit gate, origin unknown, currency-aware query generation, per-period cache reuse, chart independence, saved observations, curated parsing and semantic matching, shared-currency map evidence, exact card amounts and existing automatic history/chat/payment flows.

Real-browser verification exposed an old long-range-cache freshness bug: an old MAX chart row caused repeated retrievals despite fresh currency observations. This was fixed and regression-tested. Final server was restarted with the tested implementation. Local verification artifacts remain ignored under .verification; clean-install output is `.verification/clean-20261107-070416`.

## Three-minute judging sequence

1. **0:00–0:25** Select Coffee Enthusiast. Show “What you love. Where your dollar goes further.” and the current interest chips. History → profile analysis shows current OpenAI interpretation and statistical evidence. Do not reset actual captured payments.
2. **0:25–0:55** FX Advantage Map: default 90D; inspect EUR/GBP/JPY classifications and source dates. Switch to 1Y, then back. Historical Demonstration Scenario uses saved real observations, not a guaranteed favorable current market.
3. **0:55–1:35** Select Coffee category; automatic discovery updates. If Channel3 produces USD-heavy results, choose “Curated official listings · dated” to demonstrate verified external-currency math. Show EUR listing price, current/reference hypothetical USD amounts, the difference and unknown total/access conditions. Do not enable an unreviewed merchant or claim US shipping.
4. **1:35–2:00** Switch map to Personalized Opportunities: listing-currency regions with FX-evidenced candidates. Switch to Verified Product Origins: unknown-origin products do not create seller-country scores. Open the daily chart for a selected supported country.
5. **2:00–2:30** Ask: “Which product best combines my interests and favorable currency conditions? Explain the observed listing currency and unknown costs.” AI must use supplied calculations and cannot claim a confirmed winner while destination review is pending.
6. **2:30–2:55** Explicitly switch to Demo Products for the fictional Demo Merchant payment flow, or open the existing genuine USD COMPLETED receipt and say it is a previous Sandbox capture. A fresh test requires the account owner's buyer approval; no external merchant item is proxy-purchased through the demo.

No video was recreated for this revision. The previous finished MP4 describes the earlier concept and is preserved. A new video, fresh Sandbox payment, new merchant approvals, full mobile/keyboard QA and any GitHub push remain outside completed work.

## Changed files

Backend: `backend/fx_opportunities.py`, `backend/fx.py`, `backend/search_plan.py`, `backend/products.py`, `backend/curated.py`, `backend/automatic_discovery.py`, `backend/discovery.py`, `backend/conversation.py`, `backend/enhancements.py`, `backend/main.py`; public observations in `backend/fixtures/curated_products.json` and `backend/fixtures/fx_observed_snapshot.json`.

Frontend: `frontend/src/FXOpportunities.tsx`, `frontend/src/MapLayerControls.tsx`, `frontend/src/mapLayers.ts`, `frontend/src/WorldMap.tsx`, `frontend/src/useRadar.ts`, `frontend/src/useAutomaticDiscovery.ts`, `frontend/src/AutomaticProducts.tsx`, `frontend/src/App.tsx`, `frontend/src/Pages.tsx`, `frontend/src/api.ts`, `frontend/src/ui.tsx`, `frontend/src/global.css`, `frontend/index.html`.

Tests/tooling/docs: `tests/test_fx_opportunities.py`, `tests/test_api.py`, `tests/conftest.py`, `frontend/src/__tests__/fxOpportunities.test.tsx`, `frontend/src/__tests__/App.test.tsx`, `scripts/refresh_curated.py`, `scripts/verify_clean_checkout.py`, `.env.example`, `README.md`, `docs/fx-driven-discovery.md`, `docs/implementation-status.md`. The pre-existing uncommitted `.gitignore` change protecting demo-video remains unchanged by this revision.
