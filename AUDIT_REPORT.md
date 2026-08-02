# BudgetHive — Full Codebase Audit

**Scope:** Entire repo (backend FastAPI app, agents, DB layer, alembic migrations, frontend, tests, config).
**Date:** 2026-08-01

---

## 1. Bug & Issue Report

### CRITICAL (security / data / crash)

**C1. `backend/.env` is committed with live Neon DB credentials, Gemini API key, and JWT secret**
- File: `backend/.env` (lines 6, 9, 14)
- Problem: Anyone with repo access has full production DB access, ability to forge JWTs for any user, and can rack up Gemini API bills. `.gitignore` line 15 lists `.env` but the file is already tracked.
- Fix: `git rm --cached backend/.env`, rotate the Neon password, rotate `JWT_SECRET_KEY`, revoke and reissue the Gemini API key. Force-push if the history matters or run BFG to purge.

**C2. Purchase-history auth completely bypassed — bearer token treated as raw UUID, not JWT**
- File: `backend/app/api/purchase_history.py` lines 24–47
```python
try:
    user_id = UUID(credentials.credentials)   # <-- NOT decode_access_token
except ValueError:
    raise credentials_exception
```
- Problem: Anyone who knows or guesses a user's UUID can read/create/modify their purchase history. Full auth bypass on every `/api/v1/purchase-history/*` route. UUIDs are also visible in the `Token.user.id` field returned at login, so the token itself is redundant.
- Fix: Import `get_current_user` from `app.api.deps` and delete the local shadow. `financial.py` should do the same instead of rolling its own `get_optional_user`.

**C3. `google-generativeai` in requirements.txt but code uses new `google-genai` SDK**
- File: `backend/requirements.txt` line 24 (`google-generativeai>=0.8.0`) vs. `backend/app/agents/financial_agent.py` line 5 / `need_agent.py` line 18 / `alternative_agent.py` line 16 / `llm_utils.py` line 4 (`from google import genai` + `genai.Client(api_key=...)`)
- Problem: `google-generativeai` is `import google.generativeai as genai`. `google-genai` (the new SDK) is `from google import genai` with a `Client()` class. On a clean install, all four LLM-using modules will raise `ImportError` / `AttributeError` at import time, taking down the entire FastAPI app on startup (main.py imports these routers, which import the agents).
- Fix: Replace `google-generativeai>=0.8.0` with `google-genai>=1.0.0` (or matching version). Verify with `pip install -r requirements.txt && python -c "from app.main import app"`.

**C4. Baseline alembic migration is empty — running migrations on a fresh DB creates zero tables**
- File: `backend/alembic/versions/301a44efdd4f_baseline_schema.py` lines 21–30 (`upgrade`/`downgrade` both `pass`)
- Problem: The follow-up migration `9da9adc518dc` then does `op.add_column('purchase_history', ...)`, which will crash with `UndefinedTable` on any fresh DB. The current Neon DB must have been populated via `Base.metadata.create_all()` or by hand — there is no reproducible way to stand up a new environment.
- Fix: Autogenerate the baseline against a clean DB: `alembic revision --autogenerate -m "baseline schema"` after dropping the empty one, or manually write the `op.create_table(...)` calls for `users`, `purchase_history`, `verdict_history`, `agent_results`.

**C5. `alternative_agent.run_alternatives_agent` is sync but calls `asyncio.run()` inside an async endpoint**
- Files: `backend/app/api/alternatives.py` line 30 (`return run_alternatives_agent(...)` inside `async def evaluate_alternatives`) + `backend/app/agents/alternative_agent.py` lines 346, 351, 365 (`asyncio.run(provider.resolve_input(...))`)
- Problem: `asyncio.run()` inside a running event loop raises `RuntimeError: asyncio.run() cannot be called from a running event loop`. The endpoint's `provider` default is `None`, which skips this branch, so it *appears* to work in production — but the moment anyone passes a provider (as the tests do successfully by NOT going through the endpoint), it breaks. Even the `provider=None` branch calls `httpx.get()` synchronously (line 301), blocking the FastAPI event loop for up to 6 s per call.
- Fix: Make `run_alternatives_agent` `async`, use `httpx.AsyncClient`, and `await` provider methods directly. Update `alternatives.py` to `await`.

**C6. Discount double-counting in Deal Hunter**
- File: `backend/app/agents/deal_hunter_agent.py` lines 963–1065 (`_parse_offer_window`) + line 734 (`_effective_price`)
- Problem: A single scraped offer line containing "10% instant discount with HDFC Bank cards" hits the `coupon` block (if "code" nearby), the `bank/card` block, AND the fallback `discount` block. Each appends a separate `OfferDetail`, all summed in `_effective_price`. Real Amazon offer text like "Bank Offer: Save extra ₹500 with HDFC / Coupon SAVE500 / 10% off" can be counted 3×, producing a negative or absurdly-low effective price and inflating deal-quality scores.
- Fix: Restructure `_parse_offer_window` to pick exactly one offer type per window (cascade with early return), or dedupe by conditions text.

### HIGH (functional break / dead feature)

**H1. Entire frontend is a stub**
- File: `frontend/src/App.jsx` (single line — returns "Frontend removed" placeholder)
- Problem: `frontend/src/api.js` has a full client, `vite.config.js` proxies to the backend, but the app renders nothing. Everything shipped as "UI" is non-functional. The only signup/login/verdict path users can hit is via curl.
- Fix: Rebuild the UI or clearly mark the repo as backend-only.

**H2. `VerdictHistory` + `AgentResult` models are dead code**
- Files: `backend/app/models/verdict_history.py`, `backend/app/models/agent_result.py`
- Problem: No endpoint reads or writes these tables. `PurchaseHistory.verdict_id` FK is never populated. There is no orchestrator that composes the four agents into a single BUY / MAYBE / SKIP verdict — the PRD's core deliverable is missing. Each agent has its own endpoint but nothing aggregates them.
- Fix: Either implement the orchestrator (`/api/v1/verdict/evaluate` that fans out to the four agents and persists `VerdictHistory` + one `AgentResult` per agent), or delete the unused models + FK.

**H3. Deal Hunter's 90-day price history is per-process in-memory**
- File: `backend/app/agents/deal_hunter_agent.py` line 155 (`PRICE_HISTORY_CACHE: defaultdict[str, list[PriceHistoryEntry]]`)
- Problem: Under any real deployment (multiple uvicorn workers, container restarts, autoscaling), each worker maintains its own cache. "Historical average 90d" is essentially random per request. The PRD claims price snapshots; there's a `price_snapshot.cpython-313.pyc` in `__pycache__` implying a model existed and was removed — but the current model dir doesn't have it.
- Fix: Persist snapshots in Postgres (a `price_snapshot` table keyed on `product_identifier + platform + checked_at`) and query the trailing 90 days on read.

**H4. Alternatives agent returns hardcoded fake products**
- File: `backend/app/agents/alternative_agent.py` lines 217–268 (`_build_deterministic_alternatives`)
- Problem: When Gemini fails or isn't configured, it returns literal made-up products ("Vivo V70" at ₹38,999, "Nothing 4a Pro" at ₹42,999, "Google Pixel 8a" at ₹39,999) with `data_source="FALLBACK"`. For any other product name the fallback names it `"Budget {product}"` and `"Value {product}"` at 80% / 90% of the price — pure fabrication. Users see plausible-looking alternatives that don't exist.
- Fix: On fallback, return `alternatives: []` with a clear "no alternatives verified" message; never invent products.

**H5. Web scraping is expected to always fail against real Amazon/Flipkart**
- File: `backend/app/agents/deal_hunter_agent.py` lines 30–36 (static Chrome UA)
- Problem: Real Amazon.in and Flipkart aggressively block direct scraping and return CAPTCHA / 503 to static-UA GETs. In production this agent will almost always return the "low confidence — could not verify a live match" fallback (line 328). The mock tests pass because they use `httpx.MockTransport`, not because real scraping works.
- Fix: Use a paid product data API (RapidAPI/Serpapi/Oxylabs), a headless browser (Playwright), or drop the "live scrape" claim and use static seed data.

**H6. `_search_live_web_listings` is sync inside an async server**
- File: `backend/app/agents/alternative_agent.py` line 301 (`httpx.get(...)`)
- Problem: Blocks the event loop for up to 6 s. Combined with the fact that `run_alternatives_agent` is a `def` called from `async def evaluate_alternatives`, this blocks all concurrent request processing.
- Fix: `httpx.AsyncClient` + `await`.

### MEDIUM (correctness / security hygiene / UX)

**M1. `financial.py` and `purchase_history.py` each redefine `get_current_user`**
- Files: `backend/app/api/financial.py` lines 27–37 (optional variant, correct JWT), `backend/app/api/purchase_history.py` lines 24–47 (broken raw-UUID variant — see C2)
- Fix: Use `app.api.deps.get_current_user` everywhere; add a `get_optional_user` beside it in `deps.py`.

**M2. bcrypt password truncation silently collides**
- File: `backend/app/core/security.py` lines 25, 32
- Problem: Two different passwords whose first 72 bytes match will verify as equal. Comment claims "handled defensively" but it's a real hash collision.
- Fix: Reject passwords longer than 72 bytes at the schema layer (already `max_length=72` in `UserCreate` — good — but `UserLogin` has no length constraint, so long-password login attempts still hit the truncation path).

**M3. CORS is hardcoded to localhost**
- File: `backend/app/main.py` line 20
- Fix: Drive from `settings.CORS_ORIGINS` (comma-separated env var) so staging/prod work.

**M4. `settings` default JWT secret allows silent boot with `"CHANGE_ME_IN_PRODUCTION"`**
- File: `backend/app/config.py` line 18
- Problem: If `.env` is missing at runtime, the app boots with a known secret and issues forgeable tokens.
- Fix: In `Settings.__init__` (or a validator), raise if `JWT_SECRET_KEY == "CHANGE_ME_IN_PRODUCTION"` and `DEBUG is False`.

**M5. Deal Hunter endpoint wraps all exceptions in a 500 with the exception message leaked**
- File: `backend/app/api/deal_hunter.py` lines 54–58
- Problem: `detail=f"Deal Hunter Agent evaluation error: {str(exc)}"` leaks internal error messages (stack strings, DB connection strings if any propagate). Same pattern in `alternatives.py` line 38.
- Fix: Log the exception, return a generic 500 body. Same for alternatives.

**M6. `checkin_purchase_history` clobbers usage duration on DOWN check-in**
- File: `backend/app/api/purchase_history.py` lines 138–139
```python
if payload.still_using is not None:
    history.usage_duration_days = history.usage_duration_days or 0
```
- Problem: Sets duration to 0 if it was previously None, even though `still_using` might be `True`. This intent is unclear: the field should record actual days, not be zeroed on a check-in.
- Fix: Only overwrite when the client actually provides a value; otherwise leave alone.

**M7. `find_due_checkin_notifications` "weekly cap" logic is off-by-one and returns wrong slice**
- File: `backend/app/api/purchase_history.py` lines 179–184
```python
weekly_cap = 1
...
if len(week_rows) >= weekly_cap:
    return week_rows[:1]
return tiered_rows
```
- Problem: Returns just 1 row if any check-in already went out this week; otherwise returns ALL tiered rows across all time. So a user with no check-ins this week gets a firehose (e.g. 12 due notifications on Monday morning); a user with 1 check-in gets 1. Not the "weekly cap of 1" the code appears to want.
- Fix: `return tiered_rows[:1]` unconditionally when a weekly cap is desired.

**M8. `checkin_sent` migration is not nullable but has no server default**
- File: `backend/alembic/versions/9da9adc518dc_add_purchase_history_checkin_support.py` line 23
```python
op.add_column('purchase_history', sa.Column('checkin_sent', sa.Boolean(), nullable=False))
```
- Problem: On any existing table with rows, this `ALTER` will fail on Postgres with "column contains null values" because no `server_default` is provided.
- Fix: `sa.Column('checkin_sent', sa.Boolean(), nullable=False, server_default=sa.false())`.

**M9. Ambient shadowing of `status` in `build_purchase_history_from_create`**
- File: `backend/app/api/purchase_history.py` line 56 (`status = payload.status`) inside a module that imports `from fastapi import ... status`. Local `status` shadows the FastAPI enum for the rest of the function — safe here (only used as string) but fragile if someone later writes `HTTPException(status_code=status.HTTP_...)` in the same function.
- Fix: Rename to `history_status`.

**M10. Frontend has no error boundary, no auth persistence, no route guard — because it doesn't exist**
- File: `frontend/src/App.jsx` (stub)
- See H1.

**M11. `api/__init__.py` exports out of sync with actual routes**
- File: `backend/app/api/__init__.py` line 2 — only `auth, users, purchase_history` in `__all__`, but `main.py` imports `deal_hunter, financial, need, alternatives` too. Not a runtime bug, but confusing.
- Fix: Sync the `__all__`.

**M12. Import of unused `types` in agents**
- Files: `financial_agent.py` line 6, `need_agent.py` line 19 (both `from google.genai import types` — `types` unused directly; only referenced inside `llm_utils.py`). Also `threading` imported in `alternative_agent.py` line 9 and never used.
- Fix: Remove dead imports.

**M13. `test_api_endpoint.py` is dead**
- File: `backend/test/test_api_endpoint.py` line 3 — `pytest.skip(..., allow_module_level=True)` unconditional skip. Then unreachable code below still references response fields (`data1['category']`, `'scanned_deals'`, `'ai_recommendation'`) that don't exist on `DealHunterResult`. If ever re-enabled it will crash immediately.
- Fix: Delete or rewrite against the current schema.

**M14. `test_financial_agent.py` has no assertions**
- File: `backend/test/test_financial_agent.py` — a demo `run_demo()` script, not a pytest test. Pytest may pick nothing up here; nothing is verified.
- Fix: Convert to `def test_*` with real `assert` statements.

**M15. `alternative_agent` test relies on real Gemini (or fallback fake data)**
- File: `backend/test/test_alternative_agent.py::test_alternative_agent_returns_price_range_matches_for_phone_search`
- Problem: No provider passed → real network call to Gemini + DuckDuckGo. In CI without a key, hits the hardcoded-fake-products fallback (H4). Test still passes because it only checks price bounds — but it's testing fabricated data.
- Fix: Patch `_get_client` to return `None` and inject a stub provider.

### LOW (code smell / consistency)

**L1.** `README.md` is empty.
**L2.** `frontend/dist/` is checked in (see `frontend/dist/*` in git tree despite being in `.gitignore` — probably tracked before ignore was added).
**L3.** `frontend/package.json` declares no lint, no test, no format scripts.
**L4.** `styles.light.css` is not referenced; probable dead file.
**L5.** `backend/app/services/` is empty scaffolding.
**L6.** `.DS_Store` files tracked at repo root (see file tree).
**L7.** `get_db` commits every session on success — for read-only endpoints this is a wasted network round-trip; not incorrect but noise.
**L8.** Deal Hunter uses `# pragma: no cover` on the outermost exception handler (line 449), hiding real coverage gaps.
**L9.** `Mapped` imported but unused in `agent_result.py` line 4.
**L10.** `Integer` imported but unused in `models/user.py` line 2.

---

## 2. Feasibility Check

| Module / Feature | Status | Notes |
|---|---|---|
| **Auth (signup / login)** | Partially works | JWT flow in `auth.py` + `deps.py` is correct. But `.env` leak (C1) means the secret is public; `purchase_history` bypasses it entirely (C2). |
| **User profile CRUD (`/users/me`)** | Works | Uses correct JWT dependency. |
| **Financial Agent** | Works (rule-based); LLM broken | Rule-based scoring is deterministic and correct. LLM path is dead until requirements.txt is fixed (C3). |
| **Need Agent** | Works (fallback only) | Same as Financial — LLM path broken by C3. Fallback returns generic neutral score. Tests only exercise the fallback branch. |
| **Deal Hunter Agent** | Broken in production | Scraping real Amazon/Flipkart with static UA will nearly always fail (H5). In-memory price history resets per worker (H3). Discount double-counting inflates savings (C6). Passes tests because tests mock every HTTP call. |
| **Alternatives Agent** | Non-functional / misleading | Async/sync mismatch will crash on non-null provider (C5); event loop blocked otherwise (H6). Fallback fabricates products (H4). LLM path broken by C3. |
| **Purchase History create + list** | Works, but insecure | Endpoints function, but auth is bypassed (C2). |
| **Purchase History check-in** | Partially works | UP path OK. DOWN path has data-loss bug (M6). "Due check-ins" weekly-cap logic is wrong (M7). |
| **Verdict orchestrator (BUY/MAYBE/SKIP)** | **Never wired up** | The PRD centerpiece. No route, no service, no aggregation. `VerdictHistory` and `AgentResult` models sit unused (H2). `PurchaseHistory.verdict_id` FK is never populated. |
| **Watchlist / price alerts** | Never wired up | `VerdictHistory.is_on_watchlist`, `target_price`, `last_checked_price` fields exist; nothing writes or reads them. |
| **Frontend (React app)** | Non-functional | Placeholder component only (H1). |
| **Alembic migrations** | Broken on fresh DB | Empty baseline (C4). Second migration will crash. Current DB was created out-of-band. |
| **CORS** | Works locally only | Hardcoded to `localhost:3000` / `:5173` (M3). |
| **Tests** | Partially useful | 3/6 test files are real unit tests. Others are skipped, demo scripts, or exercise fallbacks. No integration tests hit the DB or auth flow end-to-end. No frontend tests. |

**Dead code inventory:** `VerdictHistory`, `AgentResult`, `PurchaseHistory.verdict_id`, `frontend/src/App.jsx` current content, `frontend/src/styles.light.css`, `backend/app/services/`, `test_api_endpoint.py`, `threading` import in `alternative_agent.py`, `types` imports in `financial_agent.py` / `need_agent.py`, `Mapped`/`Integer` unused imports.

---

## 3. Impact vs Effort Matrix

| Item | Description | Impact | Effort | Bucket |
|---|---|---|---|---|
| C1 Rotate leaked secrets + purge `.env` from git | Neon DB creds + JWT + Gemini key are public in repo | H | L | Quick win |
| C2 Fix purchase_history auth bypass | Replace raw-UUID with `deps.get_current_user` | H | L | Quick win |
| C3 Switch `google-generativeai` → `google-genai` in requirements | Whole app fails to import LLM paths otherwise | H | L | Quick win |
| M4 Fail-fast if default JWT secret in non-debug | 5-line validator | H | L | Quick win |
| M5 Stop leaking exception text in 500s | 2 endpoints | M | L | Quick win |
| M8 Add `server_default` on `checkin_sent` migration | 1-line edit | M | L | Quick win |
| M11 Sync `api/__init__.py` `__all__` | Trivial | L | L | Batch later |
| M12 Delete unused imports | Trivial | L | L | Batch later |
| L1–L10 Cleanup: empty README, dead files, .DS_Store, unused CSS | Housekeeping | L | L | Batch later |
| M13 Delete `test_api_endpoint.py` | Dead skipped test | L | L | Batch later |
| C4 Rewrite baseline alembic migration | Deployability blocker | H | M | High impact / plan for |
| C6 Fix Deal Hunter offer double-counting | Correctness of core scoring | H | M | High impact / plan for |
| H4 Stop fabricating alternatives in fallback | User trust; recommendation credibility | H | L–M | Quick win / plan-for hybrid |
| H2 Build the verdict orchestrator + wire up `VerdictHistory`/`AgentResult` | The PRD's core BUY/MAYBE/SKIP feature | H | H | Major project |
| H1 Rebuild the frontend | Product is unusable without UI | H | H | Major project |
| H3 Move price history to Postgres | Cache correctness under multi-worker deploy | H | M | High impact / plan for |
| H5 Replace direct scraping with a real product API or headless browser | Live-price feature only nominally works today | H | H | Major project |
| C5 + H6 Make `run_alternatives_agent` async | Concurrent throughput; async correctness | M | M | Plan for |
| M6 Fix DOWN check-in usage-duration overwrite | Data loss | M | L | Quick win |
| M7 Fix due-checkins weekly-cap logic | Notification firehose | M | L | Quick win |
| M1 Consolidate duplicated auth dependencies | Code hygiene, tied to C2 fix | M | L | Quick win |
| M2 Reject overlong passwords at login schema | Small security tightening | M | L | Quick win |
| M3 Env-driven CORS | Non-local deployment blocker | M | L | Quick win |
| M9 Rename shadowed `status` local | Fragile symbol | L | L | Batch later |
| M14 Convert `test_financial_agent.py` demo into real asserts | Test coverage credibility | M | L | Quick win |
| M15 Patch out network in `test_alternative_agent.py` | CI reliability + real coverage | M | L | Quick win |
| Add integration tests hitting auth + DB | Regression net | M | M | Plan for |
| Frontend deletion or rebuild decision | Product direction | H | L (delete) / H (rebuild) | Depends on choice |

---

## 4. Prioritized Action List

**Do today (< 30 min each, mostly config/auth):**
1. Rotate the Neon DB password, the JWT secret, and the Gemini API key; `git rm --cached backend/.env`, commit, force-push (or BFG). *[C1 — public credentials.]*
2. Delete the local `get_current_user` in `purchase_history.py` and import from `app.api.deps` instead. *[C2 — full auth bypass on all purchase-history routes.]*
3. Change `requirements.txt`: `google-generativeai>=0.8.0` → `google-genai>=1.0.0`. Reinstall and boot the app to confirm agent imports succeed. *[C3 — every LLM path currently un-importable.]*
4. Fix migration `9da9adc518dc`: add `server_default=sa.false()` to the `checkin_sent` column. *[M8 — migration crashes on any table with existing rows.]*
5. Add a Pydantic validator in `config.py` that raises when `DEBUG is False` and `JWT_SECRET_KEY == "CHANGE_ME_IN_PRODUCTION"`. *[M4 — silent-insecure boot.]*
6. Stop echoing `str(exc)` in `deal_hunter.py` and `alternatives.py` 500 handlers; log server-side, return a generic detail. *[M5 — info leak.]*
7. Fix the DOWN check-in usage-duration overwrite (`purchase_history.py:138`) and the `weekly_cap` slicing in `find_due_checkin_notifications` (`purchase_history.py:183`). *[M6, M7 — data loss + notification firehose.]*
8. Drive CORS origins from an env-configured list. *[M3 — required to ship beyond localhost.]*

**Do this week:**
9. Rewrite the alembic baseline migration to actually create `users`, `purchase_history`, `verdict_history`, `agent_results`. Prove it works by dropping and re-migrating a scratch DB. *[C4 — no reproducible deployment today.]*
10. Fix the discount double-counting in `_parse_offer_window` (early-return once one offer type matches, or dedupe by conditions text). *[C6 — deal quality inflated.]*
11. Replace the hardcoded fake alternatives in `_build_deterministic_alternatives` with an empty list + explicit "no alternatives verified" reasoning. *[H4 — fabricated recommendations.]*
12. Make `run_alternatives_agent` async, switch to `httpx.AsyncClient`, and `await` from the endpoint. *[C5 + H6 — event loop blocking + latent crash.]*
13. Convert `test_financial_agent.py` from a demo script into real `assert`-based tests; patch out the network in `test_alternative_agent.py`; delete `test_api_endpoint.py`. *[M13, M14, M15.]*
14. Consolidate duplicated auth dependencies (`financial.py`, `purchase_history.py`) around `deps.py`. *[M1.]*
15. Delete dead imports (`threading`, `types`, `Mapped`, `Integer`) and clean up `.DS_Store` + `frontend/dist/` from the tracked tree. *[L2, L6, M12.]*

**Plan into a sprint:**
16. **Build the Verdict Orchestrator.** Add `/api/v1/verdict/evaluate` that fans out to the four agents, aggregates into BUY/MAYBE/SKIP, and persists `VerdictHistory` + one `AgentResult` per agent. Wire `PurchaseHistory.verdict_id` when the user commits to the purchase. *[H2 — the PRD's core feature is missing.]*
17. **Move Deal Hunter price history to Postgres** (new `price_snapshot` table; write on each scrape; read trailing 90 days on scoring). *[H3.]*
18. **Replace direct scraping** with either a paid product-data API or Playwright. *[H5 — the "live prices" claim is aspirational today.]*
19. **Rebuild the frontend** (or officially deprecate it and mark this as a backend-only repo). *[H1.]*
20. Add integration tests that exercise signup → login → protected route → purchase-history create against a test Postgres. *[Overall regression net.]*

---

## 5. Summary

**Overall health:** The backend has real ambition — four agents, structured Pydantic schemas, an async DB layer — but the shipped product is much smaller than it appears. The verdict orchestrator that the entire app is named for isn't wired up, the LLM SDK isn't installable, one auth path is completely bypassed, and the frontend is a placeholder. Roughly 30% of the code is dead or non-functional.

**Biggest risks (in order):**
1. **Credential exposure** — Neon DB, Gemini key, and JWT signing key are all in the committed `.env`. Assume compromised and rotate immediately.
2. **Auth bypass on purchase-history routes** — anyone with a user UUID (returned publicly in the login response) has full read/write access.
3. **App won't start on a clean install** — `requirements.txt` pins the wrong Gemini SDK; every agent import breaks.
4. **No reproducible DB** — baseline migration is empty; the current DB was populated out-of-band.
5. **The core BUY/MAYBE/SKIP verdict feature doesn't exist.**

**This week vs later:**
- **This week (safety + reproducibility):** items 1–8 in the action list. All small edits, all high-impact.
- **Next week (correctness):** items 9–15. Fix migrations, discount math, async plumbing, and dead tests.
- **Sprint after (product):** items 16–20. Build the orchestrator, move price history to Postgres, replace scraping, rebuild the frontend.

Once items 1–4 are done, the app is at least honest about what it is. Items 5–12 make it defensible. Items 16–19 are the real product work.
