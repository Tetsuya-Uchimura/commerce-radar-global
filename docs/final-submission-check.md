# Final submission polish — 2026-11-08 (JST)

## Current repository status

The Strategy Engine baseline is `a7fb8a0a27e88d85e81c41cbc9cfc138b033babc`, confirmed on local and remote `main` before these final checks. The final polish was originally verified as an uncommitted working-tree update. The owner subsequently requested GitHub publication and integration into `main`; consult the subsequent `main` history for that integration commit. GitHub visibility was not changed and remains Private for the pre-submission workflow. MIT License is unchanged. Earlier implementation/test records in the other guides are explicitly historical.

## FX presentation

The existing Decimal formulas, mathematical classification, strategy thresholds and three strategies are unchanged. A single Python presentation helper supplies currency labels, listing labels and strategy evidence labels. React displays these supplied labels in the currency strip, map details, strategy chips, recommended sources and product evidence.

| Evidence | Before | Current label |
| --- | --- | --- |
| Small positive movement, above 0.01% through the configured meaningful percentage (default 1%) | Favorable Currency on map/list; Small or marginal FX context on cards | Slight FX Improvement |
| Below −0.01% | Unfavorable | Unfavorable FX Trend |
| Within ±0.01% | Neutral | Neutral FX Trend |
| Above the meaningful percentage, without a qualifying listing | Favorable Currency | Favorable Currency Trend — Product Advantage Unverified |
| Above the meaningful percentage, fresh relevant listing, at least the configured USD difference and interest score | FX-Backed Find | Meaningful Shopping Opportunity |

The strong default gates remain **power >1%, hypothetical difference >=USD 1, interest >=40/100, fresh verified price/currency/FX**. The decision engine also retains its separate 0.5% marginal boundary for domestic versus comparison search priority. Displaying Slight FX Improvement therefore does not force Explore Overseas. All configured thresholds continue to apply. A good currency movement without adequate product-price evidence never becomes a meaningful listing recommendation.

The FX Advantage Map and currency strip deliberately describe currency context, so they cannot assert a product advantage. The Personalized Opportunities map can use the meaningful label when actual qualifying listings exist. Shared-currency countries do not become merchant-origin evidence. Small positive regions use the subdued neutral/small color. Unknown origin, unknown delivered costs, historical mode and US-price caveats remain explicit.

## Merchant checks and existing approval rules

Read-only checks were performed at approximately **2026-11-08 00:24 JST** (2026-11-07 15:24 UTC). The two page URLs match their current curated fixture entries exactly. No fixture price/date, archive or merchant approval was changed.

| Merchant / public page | Server observation | Chromium observation | Effective application access |
| --- | --- | --- | --- |
| [HARIO Europe](https://www.hario-europe.com/products/v60-ceramic-immersion-colour-dripper-switch-02-size) | HTTP 200, reachable; no HTTP redirect | Product title and EUR 59.90 shown. Same product path; page selected `?variant=49095653982531`. No disabled/error page. | `user_pending`: navigation stays disabled; `hario-europe.com` is absent from the user's approved domains. |
| [KINTO USA](https://kinto-usa.com/products/27574) | HTTP 200, reachable; no HTTP redirect | SCS-S04 brewer 2cups, USD 24.80 shown; URL unchanged. No disabled/error page. | `user_confirmed`: already approved in the user's 2026-11-04 representative-site review; Open recommended source is allowed under the existing policy. |

These are observations from this machine at one time, not guarantees of regional access, stock, tax, delivery or future availability. The checks are stored as local verification evidence only, separate from application authorization. Browser and server access can differ. No user approval was inferred from HTTP 200.

The existing URL checks still block private/non-public destinations, restrict ports, pin validated DNS destinations, bound redirects/body/timeouts, and detect disabled pages, login, browser challenges and HTTP errors. Manual mode does not automatically probe new merchants. A cached known unsafe/unavailable destination remains disabled even for an approved merchant.

### What the user should do

There is **no approval screen/button in the app**. On the World radar screen, read Recommended Shopping Sites and its visible URL. Open the HARIO URL directly in your own browser, confirm the expected product rather than an error/interstitial, and report `hario-europe.com: T` or `F` in this chat. After that explicit review, the existing maintenance process records the domain in `backend/merchant_access.json` (`allow` or `exclude`). This task intentionally does not make that decision for you. A developer can apply the same user-approved change to that JSON directly. Reload/Refresh Products to apply the new policy. The reviewed date/scope should accurately describe the user's check.

KINTO already has that approval; no additional approval is needed. Choose Coffee and the existing Curated official listings provider, then US stores first if you want to inspect that source explicitly. Open recommended source follows the existing link rule. This changes search priority, not the automatic currency judgment or seller-country facts.

Top source entries now show merchant, product, observed price/currency/date, recommendation reason, price source, evidence status and the same access-status explanation used on product cards. Pending review displays its reason, and the disabled destination remains visible as text.

## Executed verification

| Check | Result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | 149 passed; one existing Starlette/httpx deprecation warning. |
| `npm --prefix frontend test -- --run` | 50 passed, 7 test files. |
| `npm --prefix frontend run build` | TypeScript and Vite production build passed. |
| `.\.venv\Scripts\python.exe scripts/audit_publication.py` | Passed: 121 candidate files, 13 ignored-path checks, zero missing ignore rules, forbidden publish files or known credential/private-key matches. |
| `git diff --check` | Passed. |

New regressions cover tiny positive/negative and exact boundaries, meaningful percentage plus absolute difference, missing price, configurable thresholds, matching top/card/currency/map labels, pending HARIO versus already-approved KINTO, and current versus historical documentation. Existing automatic discovery, history, FX and payment regressions remain passing.

Actual Chromium UI verification used the local backend and genuine curated/cache data with Coffee Enthusiast. The initial 90D result was Explore Overseas (EUR +2.88%, relevant HARIO EUR listing). The strategy and product showed Meaningful Shopping Opportunity; the currency-only layer correctly showed Product Advantage Unverified. Other observed currency labels included GBP +0.22% Slight FX Improvement, JPY near zero Neutral FX Trend, and SGD −0.16% Unfavorable FX Trend. Domestic priority showed US Stores First and the already-approved KINTO link; automatic priority was restored. Product navigation (`#real`), the daily FX chart (`#fx`) and opening/closing AI Concierge worked. No page exceptions occurred; the 390px viewport had a 366px panel and 390px document width. Desktop/FX/mobile screenshots were visually inspected.

Optional OpenAI explanation calls were suppressed during this local UI inspection to avoid paid regeneration; the deterministic strategy remained visible. The existing dated/cache FX notice remained visible. HARIO and KINTO were independently checked in Chromium as described above. No new live Channel3 search, OpenAI analysis, chat message generation, clean-install verification or payment was needed or claimed for this final-polish run; mocked provider regression tests still executed. The 139 backend / 46 frontend counts in the original implementation guide refer to the earlier implementation run.

Local verification evidence and screenshots are under ignored `.verification/final-*`; they are excluded from publication.

## Changed files

- Backend presentation/evidence: `backend/fx_opportunities.py`, `backend/products.py`, `backend/shopping_strategy.py`.
- Frontend labels/access presentation: `frontend/src/FXOpportunities.tsx`, `frontend/src/ShoppingStrategy.tsx`, `frontend/src/AutomaticProducts.tsx`, `frontend/src/mapLayers.ts`, `frontend/src/WorldMap.tsx`, `frontend/src/MapLayerControls.tsx`.
- Regression tests: `tests/test_submission_polish.py`, `frontend/src/__tests__/ShoppingStrategy.test.tsx`.
- Documentation: `README.md`, `docs/shopping-strategy.md`, `docs/fx-driven-discovery.md`, `docs/implementation-status.md`, `docs/final-submission-check.md`.

No dependency, merchant-policy or historical-price fixture was modified.

## Preservation during original verification and remaining limits

No .env/secret, payment history, completed video, approval policy or historical-price archive was changed. No new payment, GitHub push, visibility change, model upgrade or dependency addition was performed during the original verification task. GitHub publication was authorized separately afterward; repository visibility and secret exclusions remain unchanged. Paid product/analysis calls are kept to a minimum; the final local UI inspection uses existing curated/cache evidence. The live market may legitimately return US Stores First or Compare Both; a historical demonstration must stay visibly historical.

HARIO's pending user approval is the remaining demo navigation limitation. Price/stock/access may change, and unknown shipping/tax/payment fees still prevent a cheapest delivered-price claim.
