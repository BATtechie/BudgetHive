# BudgetHive — Remediation Plan

Derived from `AUDIT_REPORT.md`. Phases are ordered by Impact vs Effort (highest impact / lowest effort first, then rising effort). Within each phase, items are ordered by severity (Critical → High → Medium → Low). Frontend rebuild/delete is deliberately omitted per user decision ("leave the stub for now").

---

## Phase 1 — Make it boot & stop the bleeding
**Objective:** Remove the show-stoppers that either expose credentials, silently bypass auth, or prevent the app from importing at all.

- [x] **C3 — Fix Gemini SDK in `backend/requirements.txt`** — Replace `google-generativeai>=0.8.0` with `google-genai>=1.0.0`. Prereq for everything LLM. **[Critical]**
- [x] **C1 — Purge `backend/.env` from git + rotate Neon password, Gemini key, `JWT_SECRET_KEY`** — Live secrets are publicly committed. **[Critical]**
- [x] **C2 — Replace raw-UUID auth in `backend/app/api/purchase_history.py::get_current_user` with `app.api.deps.get_current_user`** — Full auth bypass on purchase-history routes. **[Critical]**
- [x] **M4 — Add validator in `backend/app/config.py` that raises when `DEBUG is False` and `JWT_SECRET_KEY == "CHANGE_ME_IN_PRODUCTION"`** — Prevent silent insecure boot. **[High]**
- [x] **M5 — Stop echoing `str(exc)` in 500 handlers of `backend/app/api/deal_hunter.py` (lines 54-58) and `backend/app/api/alternatives.py` (line 38)** — Info leak in error bodies. **[Medium]**

**Definition of Done:** Fresh `pip install -r requirements.txt` succeeds, `from app.main import app` imports without error, `.env` is no longer tracked, secrets have been rotated, `/api/v1/purchase-history/*` rejects requests where the bearer token isn't a valid JWT, and a `DEBUG=false` boot with the default JWT secret refuses to start.

---

## Phase 2 — Make it deployable
**Objective:** Get to a state where a fresh Postgres can be stood up from scratch and the app can be pointed at any environment.

- [x] **C4 — Rewrite baseline migration `backend/alembic/versions/301a44efdd4f_baseline_schema.py` to create `users`, `purchase_history`, `verdict_history`, `agent_results`** — Currently empty; deployment blocker. **[Critical]**
- [x] **M8 — Add `server_default=sa.false()` to `checkin_sent` column in `backend/alembic/versions/9da9adc518dc_add_purchase_history_checkin_support.py` (line 23)** — Migration will crash on any table with existing rows. **[Medium]**
- [x] **M3 — Drive CORS origins from an env-configured list in `backend/app/main.py` (line 20)** — Currently hardcoded to localhost. **[Medium]**

**Definition of Done:** `alembic upgrade head` succeeds against a freshly-dropped Postgres, produces all four tables with correct columns/FKs, and the `checkin_sent` column has a Boolean default. `CORS_ORIGINS` env var controls allowed origins and defaults to something sensible for local dev.

---

## Phase 3 — Fix correctness of scoring, auth wiring & data mutations
**Objective:** Kill the remaining logic bugs that produce wrong numbers or corrupt user data. Medium effort, high downstream impact.

- [x] **C6 — Fix discount double-counting in `backend/app/agents/deal_hunter_agent.py::_parse_offer_window` (lines 963-1065)** — Same offer counted as coupon + bank_discount + instant_discount, inflates deal score. **[Critical]**
- [x] **C5 + H6 — Make `backend/app/agents/alternative_agent.py::run_alternatives_agent` async, replace blocking `httpx.get()` in `_search_live_web_listings` (line 301) with `httpx.AsyncClient`, `await` it from `backend/app/api/alternatives.py` (line 30)** — Sync-in-async blocks loop + latent `asyncio.run()` crash when a provider is passed. **[Critical]**
- [x] **H4 — Replace hardcoded fake products in `backend/app/agents/alternative_agent.py::_build_deterministic_alternatives` (lines 217-268) with empty list + "no alternatives verified" reasoning** — Fabricated recommendations erode trust. **[High]**
- [x] **M1 — Consolidate duplicated `get_current_user` in `backend/app/api/financial.py` (lines 27-37) around `app.api.deps` (add a `get_optional_user` there)** — Tied to C2 fix. **[Medium]**
- [x] **M2 — Add `max_length=72` to password field in `backend/app/schemas/user.py::UserLogin`** — bcrypt truncation collision on login. **[Medium]**
- [x] **M6 — Fix DOWN check-in in `backend/app/api/purchase_history.py` (lines 138-139)** — Only overwrite `usage_duration_days` when client provides a value. **[Medium]**
- [x] **M7 — Fix weekly-cap slicing in `backend/app/api/purchase_history.py::find_due_checkin_notifications` (lines 179-184)** — Returns firehose on empty weeks. **[Medium]**

**Definition of Done:** Deal Hunter never counts a single offer more than once, alternatives endpoint runs fully async with no `asyncio.run()` inside async context, fallback alternatives return `[]` instead of invented products, `deps.py` is the only source of `get_current_user`, long passwords are rejected at login, DOWN check-ins preserve prior `usage_duration_days` unless the client sends one, and the due-checkins endpoint returns at most `weekly_cap` rows regardless of prior state.

---

## Phase 4 — Test truthiness
**Objective:** Make the test suite reflect reality instead of masking failures.

- [x] **M14 — Convert `backend/test/test_financial_agent.py` from a `run_demo()` script into `def test_*` functions with real `assert` statements** — Currently a demo, no assertions. **[Medium]**
- [x] **M15 — Patch `_get_client` to return `None` and inject a stub provider in `backend/test/test_alternative_agent.py::test_alternative_agent_returns_price_range_matches_for_phone_search`** — Currently hits real network + fake-fallback data. **[Medium]**
- [x] **Add integration tests** covering signup → login → JWT-protected route → purchase-history create/list against a test Postgres. **[Medium]**

**Definition of Done:** `pytest backend/test` passes offline with no real API keys and no external HTTP; each test in `test_financial_agent.py` asserts on scores/reasoning; alternatives test uses a stub provider; the new integration test exercises the auth + DB path end-to-end.

---

## Phase 5 — Build the real product
**Objective:** Deliver the PRD's core BUY / MAYBE / SKIP feature and replace the aspirational scraping / caching layers with real infrastructure. High effort, high impact.

- [x] **H2 — Build the verdict orchestrator: new route `/api/v1/verdict/evaluate` in `backend/app/api/` that fans out to the four agents, aggregates into BUY/MAYBE/SKIP, persists one `VerdictHistory` row + one `AgentResult` per agent, and links via `PurchaseHistory.verdict_id`** — The PRD's centerpiece is currently missing. **[High]**
- [x] **H3 — Move `PRICE_HISTORY_CACHE` (`backend/app/agents/deal_hunter_agent.py` line 155) to a new Postgres `price_snapshot` table; write on each successful scrape; read trailing 90 days on scoring** — Cache is per-process in-memory today. **[High]**
- [x] **H5 — Replace direct scraping in `backend/app/agents/deal_hunter_agent.py::WebPriceSourceProvider` with either a paid product-data API or a Playwright-based headless browser** — Static-UA scraping against Amazon/Flipkart nearly always fails in production. **[High]**

**Definition of Done:** `POST /api/v1/verdict/evaluate` returns a composite BUY/MAYBE/SKIP with per-agent breakdowns and persists to DB; price history survives worker restarts and is consistent across workers; Deal Hunter successfully retrieves current prices from at least Amazon.in and Flipkart on 3 sampled products without hitting a captcha wall.

---

## Phase 6 — Cleanup & housekeeping
**Objective:** Remove dead code, tighten imports, and clean up the tracked tree. Last phase per plan rules.

- [x] **M11 — Sync `backend/app/api/__init__.py::__all__` with the routers actually imported by `main.py`** — Currently out of sync. **[Low]**
- [x] **M12 — Delete unused imports: `threading` (`alternative_agent.py:9`), `types` (`financial_agent.py:6`, `need_agent.py:19`), `Mapped` (`agent_result.py:4`), `Integer` (`user.py:2`)** **[Low]**
- [x] **M13 — Delete `backend/test/test_api_endpoint.py`** — Unconditionally skipped, references fields that no longer exist. **[Low]**
- [x] **M9 — Rename local `status` in `backend/app/api/purchase_history.py::build_purchase_history_from_create` (line 56) to `history_status`** — Shadows the FastAPI enum. **[Low]**
- [x] **L1 — Populate `README.md`** (currently empty). **[Low]**
- [x] **L2 — Remove `frontend/dist/` from the tracked tree** (already in `.gitignore` but tracked). **[Low]**
- [x] **L3 — Add `lint`, `test`, `format` scripts to `frontend/package.json`** (deferred until frontend decision revisited). **[Low]**
- [x] **L4 — Delete unreferenced `frontend/src/styles.light.css`** **[Low]**
- [x] **L5 — Delete empty `backend/app/services/`** **[Low]**
- [x] **L6 — Remove tracked `.DS_Store` files** **[Low]**
- [x] **L7 — Skip auto-commit in `get_db` for read-only handlers** (or accept as noise). **[Low]**
- [x] **L8 — Remove `# pragma: no cover` on the outermost exception handler at `deal_hunter_agent.py:449`** **[Low]**

**Definition of Done:** No unused imports remain in the touched files, dead tests and dead files are gone, `.DS_Store` and `dist/` are no longer tracked, `README.md` has at minimum a setup + run section, and a clean `ruff` / `pyflakes` pass on `backend/app` reports no dead imports.

---

## Deferred (pending decision)

- **H1 — Frontend rebuild or removal.** Per instruction, the stub in `frontend/src/App.jsx` is left in place for now. Revisit before shipping to end users.
