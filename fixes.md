# BudgetHive — Fixes Log

## [Critical] C3 — Wrong Gemini SDK package
**Issue:** `backend/requirements.txt` referenced `google-generativeai>=0.8.0` which is the old SDK; the codebase uses the new `google-genai` API.
**Fix:** Replaced with `google-genai>=1.0.0`.

## [Critical] C1 — Secrets in git
**Issue:** `backend/.env` contains live Neon DB password, Gemini API key, and JWT secret. Audit flagged it as publicly committed.
**Fix:** Verified `.env` is **not tracked** and never was committed (`.gitignore` already covers it). Secret rotation is required but needs user action — see edge cases below.

## [Critical] C2 — Auth bypass on purchase-history routes
**Issue:** `backend/app/api/purchase_history.py::get_current_user` accepted any valid UUID as a bearer token, bypassing JWT auth entirely.
**Fix:** Removed the local `get_current_user` and imported `app.api.deps.get_current_user` which validates JWTs via `decode_access_token`.

## [High] M4 — Silent insecure boot with default JWT secret
**Issue:** `backend/app/config.py` allowed the app to start in production (`DEBUG=false`) with `JWT_SECRET_KEY="CHANGE_ME_IN_PRODUCTION"`.
**Fix:** Added a `@model_validator` that raises `ValueError` when `DEBUG is False` and the JWT secret is still the default.

## [Medium] M5 — Internal error details leaked in HTTP 500 responses
**Issue:** `backend/app/api/deal_hunter.py` (lines 54-58) and `backend/app/api/alternatives.py` (line 38) echoed `str(exc)` in 500 error bodies.
**Fix:** Replaced with static error messages; exception details no longer leak to clients.

## [Critical] C4 — Empty baseline migration
**Issue:** `backend/alembic/versions/301a44efdd4f_baseline_schema.py` had empty `upgrade()`/`downgrade()` — no tables created on fresh deploy.
**Fix:** Rewrote to create all four tables (`users`, `verdict_history`, `purchase_history`, `agent_results`) with correct columns, FKs, indexes, and defaults matching the ORM models.

## [Medium] M8 — checkin_sent column missing server_default
**Issue:** `backend/alembic/versions/9da9adc518dc_add_purchase_history_checkin_support.py` added `checkin_sent` as `nullable=False` with no `server_default`, crashing on tables with existing rows.
**Fix:** Added `server_default=sa.false()` to the `add_column` call.

## [Medium] M3 — Hardcoded CORS origins
**Issue:** `backend/app/main.py` hardcoded `allow_origins` to `localhost:3000` and `localhost:5173`.
**Fix:** Added `CORS_ORIGINS` setting to `backend/app/config.py` (comma-separated string, defaults to localhost origins); `main.py` now reads and splits it.

## [Critical] C6 — Discount double-counting in deal scoring
**Issue:** `backend/app/agents/deal_hunter_agent.py::_parse_offer_window` used independent `if` blocks, so a single offer text could emit cashback + bank_discount + instant_discount simultaneously, inflating deal scores.
**Fix:** Refactored to `elif` chain with shared discount extraction — each offer window now emits exactly one offer type (coupon > bank_discount > cashback > instant_discount).

## [Critical] C5 + H6 — Sync-in-async alternative agent blocks event loop
**Issue:** `backend/app/agents/alternative_agent.py::run_alternatives_agent` was sync, used blocking `httpx.get()` and `asyncio.run()` calls inside the async FastAPI event loop.
**Fix:** Made `run_alternatives_agent` and `_search_live_web_listings` async, replaced `httpx.get()` with `httpx.AsyncClient`, replaced all `asyncio.run()` with `await`, updated caller in `alternatives.py` to `await`.

## [High] H4 — Fabricated fallback product recommendations
**Issue:** `backend/app/agents/alternative_agent.py::_build_deterministic_alternatives` returned hardcoded fake products (Vivo V70, Nothing 4a Pro, Google Pixel 8a, etc.) when live search failed.
**Fix:** Replaced with empty alternatives list, score 70, and "no verified alternatives found" reasoning.

## [Medium] M1 — Duplicated get_current_user in financial.py
**Issue:** `backend/app/api/financial.py` had its own `get_optional_user` duplicating auth logic instead of using `app.api.deps`.
**Fix:** Moved `get_optional_user` to `backend/app/api/deps.py`, updated `financial.py` to import from deps.

## [Medium] M2 — bcrypt truncation on login password
**Issue:** `backend/app/schemas/user.py::UserLogin` had no `max_length` on `password`, allowing >72-byte passwords that bcrypt silently truncates, causing collision on login.
**Fix:** Added `min_length=8, max_length=72` to `UserLogin.password` field.

## [Medium] M6 — DOWN check-in overwrites usage_duration_days
**Issue:** `backend/app/api/purchase_history.py` DOWN check-in branch set `usage_duration_days = history.usage_duration_days or 0` when `still_using` was provided, clobbering `None` to `0` regardless of client intent.
**Fix:** Removed the unconditional overwrite — `usage_duration_days` is no longer touched in the DOWN path since the schema has no field for it.

## [Medium] M7 — Weekly-cap slicing returns firehose on empty weeks
**Issue:** `backend/app/api/purchase_history.py::find_due_checkin_notifications` filtered by `created_at >= week_start` which checked purchase creation date, not checkin history — when no purchases were created that week, it returned all due rows uncapped.
**Fix:** Replaced with a simple `tiered_rows[:weekly_cap]` slice that always respects the cap regardless of purchase dates.

## [Medium] M14 — Financial agent test was a demo script, not real tests
**Issue:** `backend/test/test_financial_agent.py` was a `run_demo()` script with `print()` calls and no assertions — it never validated scores, reasoning, or edge cases.
**Fix:** Rewrote as 7 pytest test functions with real assertions covering all scoring branches (exceeds budget, moderate, cheap, zero discretionary, clamping, >50% ratio) plus LLM fallback.

## [Medium] M15 — Alternative agent test hit real network
**Issue:** `backend/test/test_alternative_agent.py::test_alternative_agent_returns_price_range_matches_for_phone_search` called real HTTP endpoints and fell through to fake-fallback data when they failed.
**Fix:** Removed the network-hitting test. All tests now patch `_get_client` to return `None` and inject the `StubProvider` — runs fully offline. Added a fallback test that patches `_search_live_web_listings` too.

## [Medium] Integration tests — auth + DB end-to-end
**Issue:** No integration tests existed for the signup -> login -> JWT-protected route -> purchase-history CRUD path.
**Fix:** Added `backend/test/test_integration.py` with 8 tests using `httpx.ASGITransport` against real Postgres (derived from `DATABASE_URL` in `.env`). Each test creates/drops all tables via a fresh engine to avoid connection conflicts. Covers signup, duplicate signup (409), login, wrong password (401), unauthenticated access (401), invalid JWT (401), purchase-history create + list, and returned-status flag mapping. Also supports `TEST_DATABASE_URL` env var override; skips gracefully if no DB URL is configured.

## [High] H2 — Build the verdict orchestrator
**Issue:** The PRD's centerpiece — a single endpoint that fans out to all four agents and returns BUY/MAYBE/SKIP — was completely missing. No verdict API, schemas, or orchestration logic existed.
**Fix:** Created `backend/app/schemas/verdict.py` (request/response models) and `backend/app/api/verdict.py` with `POST /api/v1/verdict/evaluate`. The endpoint requires auth, fans out to A1_Financial, A2_Need, A3_DealHunter, A4_Alternatives concurrently via `asyncio.gather`, computes a weighted composite score (30/30/25/15), classifies as BUY (≥70) / MAYBE (40-69) / SKIP (<40), persists one `VerdictHistory` row + one `AgentResult` per agent, and returns the full breakdown. Agent failures default to a neutral 50 score with reduced confidence.

## [High] H3 — Move PRICE_HISTORY_CACHE to Postgres price_snapshot table
**Issue:** `PRICE_HISTORY_CACHE` in `backend/app/agents/deal_hunter_agent.py` (line 156) was a per-process in-memory `defaultdict` — data lost on restart, inconsistent across workers.
**Fix:** Created `backend/app/models/price_snapshot.py` ORM model with `(product_identifier, price, platform, checked_at)`, added migration `a3b7c9d1e2f4`. Added `_record_price_history_db` and `_load_history_summary_db` async functions that write/read `PriceSnapshot` rows using aggregate SQL. `find_best_deal` uses DB path when `db` is passed, falls back to in-memory otherwise. Deal Hunter API and Verdict orchestrator both pass the session now.

## [High] H5 — Replace direct scraping with Playwright headless browser
**Issue:** `WebPriceSourceProvider` in `backend/app/agents/deal_hunter_agent.py` used static-UA `httpx` requests against Amazon/Flipkart, which nearly always get blocked by bot detection in production.
**Fix:** Added `PlaywrightPriceSourceProvider` that launches headless Chromium, renders pages with JS, waits for DOM content, and extracts the full rendered HTML. Reuses all existing parsing logic. `find_best_deal` defaults to Playwright when available, falls back to httpx if Playwright is not installed. Added `playwright==1.52.0` to `requirements.txt` (requires one-time `playwright install chromium`).

## [Low] M11 — __init__.py __all__ out of sync with main.py
**Issue:** `backend/app/api/__init__.py::__all__` listed only `auth`, `users`, `purchase_history` — missing `deal_hunter`, `financial`, `need`, `alternatives`, `verdict`.
**Fix:** Updated `__all__` and the import statement to include all eight routers matching `main.py`.

## [Low] M12 — Unused imports in multiple files
**Issue:** `types` unused in `financial_agent.py:6` and `need_agent.py:19`, `Mapped` unused in `agent_result.py:4`, `Integer` unused in `user.py:2`. `threading` was already removed from `alternative_agent.py` in a prior fix.
**Fix:** Removed all four unused imports.

## [Low] M13 — Dead test file test_api_endpoint.py
**Issue:** `backend/test/test_api_endpoint.py` was unconditionally skipped and referenced fields that no longer exist.
**Fix:** Deleted the file.

## [Low] M9 — Local variable shadows FastAPI status enum
**Issue:** `backend/app/api/purchase_history.py::build_purchase_history_from_create` used `status = payload.status` which shadowed `fastapi.status` used on line 55 (`status.HTTP_201_CREATED`).
**Fix:** Renamed local variable to `history_status`.

## [Low] L1 — Empty README.md
**Issue:** `README.md` was empty — no setup, run, or project structure docs.
**Fix:** Populated with prerequisites, setup instructions, database migration, run command, test command, and project structure overview.

## [Low] L2 — frontend/dist/ tracked in git
**Issue:** Goal flagged `frontend/dist/` as tracked despite `.gitignore` coverage.
**Fix:** Verified it is already untracked (`git ls-files` returns nothing). No action needed.

## [Low] L3 — Missing lint/test/format scripts in frontend package.json
**Issue:** `frontend/package.json` had only `dev`, `build`, `preview` scripts — no `lint`, `test`, or `format`.
**Fix:** Added placeholder `lint`, `test`, `format` scripts (echo stubs) since the frontend is deferred.

## [Low] L4 — Unreferenced styles.light.css
**Issue:** `frontend/src/styles.light.css` was not imported or referenced anywhere.
**Fix:** Deleted the file.

## [Low] L5 — Empty backend/app/services/ directory
**Issue:** `backend/app/services/` contained only an `__init__.py` with comments and no code. Not imported anywhere.
**Fix:** Deleted the directory.

## [Low] L6 — .DS_Store tracked in git
**Issue:** Goal flagged `.DS_Store` files as tracked.
**Fix:** Verified `.DS_Store` is already untracked (`git ls-files` returns nothing). No action needed.

## [Low] L7 — Auto-commit on read-only handlers
**Issue:** `get_db` in `backend/app/db/session.py` always calls `session.commit()`, even for read-only GET handlers.
**Fix:** Accepted as noise — the no-op commit is functionally harmless and changing it would require touching every read-only endpoint's dependency injection. The goal itself noted "(or accept as noise)."

## [Low] L8 — pragma: no cover on outermost exception handler
**Issue:** `backend/app/agents/deal_hunter_agent.py` line 623 had `# pragma: no cover` suppressing coverage on the final safety-net exception handler.
**Fix:** Removed the `# pragma: no cover` comment.
