# BudgetHive — Re-Audit After Remediation

Full re-read of every source file. Most Phase 1-6 items from `goal.md` are actually fixed. Below are the issues that remain — including new ones introduced by the fixes.

---

## Still broken / regressed

### CRITICAL

**R1. `backend/.env` is still tracked in git and still contains live secrets**
- File: `backend/.env` (lines 6, 9, 14)
- Only the JWT_SECRET_KEY changed value (old one is now in git history anyway). The Neon password and Gemini key are byte-for-byte identical to what was in the original audit — never rotated, never purged.
- The `.gitignore` line 15 lists `.env` but a `git ls-files backend/.env` will still return the path because it was tracked before ignore was added. Phase 1 item C1 is marked `[x]` but was not actually done.

**R2. `alembic/env.py` does not import `PriceSnapshot`**
- File: `backend/alembic/env.py` line 22 — imports `User, PurchaseHistory, VerdictHistory, AgentResult` but NOT `PriceSnapshot`.
- Also: `backend/app/models/__init__.py` does not export `PriceSnapshot`.
- Consequence: `Base.metadata` seen by alembic does not include `price_snapshots`. The hand-written migration works, but the very next `alembic revision --autogenerate` will emit `op.drop_table('price_snapshots')` because the metadata "no longer has" that model. This will silently destroy price history on the next migration.
- Fix: add `from app.models.price_snapshot import PriceSnapshot` in both `models/__init__.py` and `alembic/env.py`.

### HIGH

**R3. `PlaywrightPriceSourceProvider` shares browser state across instances**
- File: `backend/app/agents/deal_hunter_agent.py` lines 320-357
- `_browser` and `_playwright` are declared as CLASS attributes (line 321-322), not instance attributes. When `find_best_deal()` creates two providers concurrently, both mutate `PlaywrightPriceSourceProvider._browser`. When one calls `.close()`, `self._browser = None` shadows the class attr on that instance only — the other instance still points at the class-level attribute which now references a closed browser.
- Under FastAPI's concurrent request handling, this will cause "Browser has been closed" errors intermittently.
- Fix: initialise `self._browser = None` and `self._playwright = None` in `__init__`.

**R4. `PlaywrightPriceSourceProvider.__init__` never runs `super().__init__()`**
- File: `backend/app/agents/deal_hunter_agent.py` lines 324-325
- Inherits from `WebPriceSourceProvider` which has `__init__(self, client, timeout)`. Playwright subclass skips it entirely, so `self._client` and `self._timeout` are never set. That's ok because every method that used them is overridden — but if a future patch calls `super()._safe_fetch_text()` or reads `self._client`, it'll `AttributeError`. A hidden landmine.
- Fix: either don't inherit (compose or make PriceSourceProvider the common base), or set both attrs in `__init__`.

**R5. Playwright chromium binary is not installed by `pip install`**
- The README documents `playwright install chromium` — good — but the code doesn't fall back cleanly when it's missing. `find_best_deal` line 456-462:
```python
try:
    owned_playwright_provider = PlaywrightPriceSourceProvider()
    provider_obj = owned_playwright_provider
except Exception:
    ...  # fallback to httpx
```
`PlaywrightPriceSourceProvider()` constructor is now essentially a no-op — it does NOT try to launch the browser and therefore cannot raise. The playwright import happens later in `_ensure_browser`, inside `_safe_fetch_text`, which catches its own exception and returns `None`. So every fetch silently returns None → every product returns "could not verify a live match". The httpx fallback is **unreachable**.
- Fix: eagerly probe playwright availability (try to import in `__init__`) and raise there so the outer `try/except` in `find_best_deal` actually fires.

**R6. Verdict endpoint feeds a dummy history string when neither answers nor real history are provided**
- File: `backend/app/api/verdict.py` lines 118-120
```python
if not need_answers and not need_history:
    need_history = "No purchase history available."
```
This forces the Need Agent into `PURCHASE_HISTORY` path (need_agent line 367: `if purchase_history_summary:` truthy) and asks the LLM to score based on the string "No purchase history available." The LLM will hallucinate a score with no real signal. The right behaviour is to leave both `None` and let `run_need_agent` return the neutral fallback.
- Fix: delete lines 118-120.

**R7. Verdict endpoint assigns 50.0 on agent failure, silently dragging the composite toward MAYBE**
- File: `backend/app/api/verdict.py` line 146
- If Deal Hunter times out on Playwright, the composite pulls toward 50 for that 0.25 weight. Combined with confidence at 75% and MAYBE threshold at 40, a user might get a "MAYBE" verdict when in reality the system had no idea. The confidence field is correct (drops to 75%) but the verdict label is unchanged.
- Better: drop the failing agent's weight from the denominator so remaining agents' scores are renormalised, or lower the confidence threshold for producing a verdict at all.

### MEDIUM

**R8. `still_using` field in `PurchaseCheckIn` schema is never consumed**
- File: `backend/app/schemas/purchase_history.py` line 37 declares `still_using: Optional[bool]`.
- File: `backend/app/api/purchase_history.py` — the DOWN branch (lines 110-119) no longer reads `payload.still_using`. Any client sending it is ignored. If a user clicks "I stopped using this", the flag is dropped on the floor.
- Fix: either remove the field from the schema or use it (e.g. `if payload.still_using is False: history.usage_duration_days = ... ; history.is_returned = False`).

**R9. `find_due_checkin_notifications` hard-codes `weekly_cap = 1` and ignores prior check-ins this week**
- File: `backend/app/api/purchase_history.py` lines 150-151
```python
weekly_cap = 1
return tiered_rows[:weekly_cap]
```
This "fixed" M7 but overshoots: the endpoint no longer tracks whether a check-in was already surfaced this week. Every call returns up to 1 row regardless. If the frontend polls this endpoint twice in the same session, it sees the same reminder twice. Also the variable is essentially dead — it's a magic 1.
- Fix: query `checkin_sent = True` rows created within `today - 7 days` and skip returning anything if that count already hit the cap.

**R10. In-memory `PRICE_HISTORY_CACHE` still active as a fallback for the DB-backed path**
- File: `backend/app/agents/deal_hunter_agent.py` lines 156, 636-644
- When `db is None` (e.g. `run_deal_hunter_agent` called from a script without a DB), history falls back to the process-local cache. That's fine for scripts, but the fallback ALSO fires when DB writes fail (line 640-642). If Postgres briefly disconnects, history silently starts being written to the in-memory cache — and then never migrates back to the DB when the connection recovers. Divergent history across workers persists.
- Fix: on DB failure, either return the empty summary and log, or retry — do not silently switch backends.

**R11. Deal Hunter reasoning still says "in-memory 90-day price history"**
- File: `backend/app/agents/deal_hunter_agent.py` line 844
```python
"I do not yet have enough in-memory 90-day price history..."
```
Now that H3 moved history to Postgres, the phrase "in-memory" is a lie. Cosmetic but user-facing.

**R12. `_get_client` performs a network probe on every call**
- Files: `financial_agent.py:50`, `need_agent.py:143`, `alternative_agent.py:79`
- `genai.Client(api_key=key)` is instantiated on every request. Each agent has 1-4 helper functions that each call `_get_client`. On a single `/verdict/evaluate` call this creates ~4 clients. Minor overhead but a code smell.
- Fix: module-level lazy singleton.

**R13. `_run_need`, `_run_financial`, `_run_alternatives` in verdict.py are declared `async def` but call synchronous inner functions**
- File: `backend/app/api/verdict.py` lines 34-93
- `evaluate_financials`, `run_need_agent` are sync but wrapped in `async def`. They're invoked via `asyncio.gather` (line 139). Sync work runs inline on the event loop thread — during Gemini LLM latency (up to 30s), the loop is blocked. `run_alternatives_agent` and `find_best_deal` are actually async so those are fine.
- Fix: either make the underlying agents async, or use `asyncio.to_thread(...)` for the sync wrappers.

**R14. `_run_deal_hunter` inside verdict.py, and `_run_alternatives`, don't renormalise scores against the alternatives sign convention**
- File: `backend/app/api/verdict.py` lines 26-31 + `_classify`
- Alternatives score semantics per docstring: "100 = no good alternative exists. Lower = a strong alternative undercuts the original." So a great cheaper alternative → alternative score drops → composite drops → SKIP. That direction is actually consistent with "should you buy this exact product". No bug; keeping this note to document the design because the naming is confusing.

**R15. `_search_live_web_listings` uses `response` after the `async with` client exits**
- File: `backend/app/agents/alternative_agent.py` lines 228-235, then 240 uses `response.text` outside the block.
- `httpx.Response.text` is decoded lazily from `response.content` which was already read inside the block (raise_for_status implies body available). In practice it works, but the pattern is fragile.
- Fix: move `soup = BeautifulSoup(response.text, ...)` inside the `async with`.

**R16. `alternative_agent.py` no longer imports `asyncio` at top but tests import it**
- File: `backend/app/agents/alternative_agent.py` line 5 (was line 5 previously imported `asyncio`) — the module no longer needs it, correctly removed. But `_search_live_web_listings` now uses `async with httpx.AsyncClient()` correctly. Fine, no bug — just noting the diff was clean.

### LOW

**R17. `_extract_offers_from_page` still emits duplicate offers when the same line matches multiple types**
- File: `backend/app/agents/deal_hunter_agent.py` lines 1187-1256 (`_parse_offer_window`)
- Better than before (bank/cashback/discount branch is now `if/elif/elif` and mutually exclusive), but coupon still emits alongside any of the three. A line "Save ₹500 with HDFC coupon HDFC500" now produces both a `coupon` and a `bank_discount` offer. Both flow into `_effective_price` → double-count of ₹500.
- Fix: track "already emitted for this window" and skip if any offer already added.

**R18. `AgentResult.raw_data` writes may fail for non-serialisable Pydantic types**
- File: `backend/app/api/verdict.py` line 76 uses `.model_dump(mode="json")` for Deal Hunter (good) but lines 42, 59, 93 use plain `.model_dump()`. Financial/Need/Alternatives currently have no datetime/enum-in-JSON fields (alternative_type is a `str, Enum` which serialises fine), so no runtime error today. If any of those schemas gets a datetime field later, the DB insert will explode. Consistency fix: use `mode="json"` everywhere.

**R19. `test_deal_hunter_agent.py` patches `_load_history_summary` (in-memory) but production now prefers `_load_history_summary_db`**
- File: `backend/test/test_deal_hunter_agent.py` line 220
- The test still passes because tests call `find_best_deal(..., provider=...)` without a `db`, so it falls back to the in-memory path. But this test no longer exercises the production code path (Postgres-backed history). New tests should mock a `db` param and assert the DB-write happened.

**R20. `test_integration.py` uses `Base.metadata.create_all` instead of running alembic**
- File: `backend/test/conftest.py` lines 77-79
- The integration tests bypass migrations. This means the alembic scripts are still not exercised in CI. If a future model change lands without the corresponding migration, tests pass while `alembic upgrade head` fails.
- Fix: run `alembic upgrade head` in `_setup_db` instead of `create_all`.

**R21. `test_integration.py` fixture is `autouse=True` but sync tests would still trigger DB setup**
- Not a bug today (all tests are async), but noted.

**R22. Frontend still stub (per user decision to defer)**
- File: `frontend/src/App.jsx` (single line placeholder). Deferred, not a bug.

**R23. `Integer` unused import in `models/user.py:2`, `Mapped` unused in `agent_result.py:4`**
- Phase 6 checklist item was marked done but these two are still present.

**R24. `frontend/dist/` still checked in**
- Phase 6 L2 marked done, but files present at `frontend/dist/assets/index-BnB5sfDg.js` etc. Untracked from git? Can't verify from filesystem alone.

**R25. `.ruff_cache/` at repo root**
- Not in `.gitignore`. Should be ignored.

**R26. `backend/app/services/` still exists as an empty scaffolding folder**
- Phase 6 L5 marked done but the folder is still there with `__init__.py`.

**R27. `AUDIT_REPORT.md` and `fixes.md` present at root**
- Not code; keep or move to `docs/`.

---

## Confirmed fixed (spot-check)

- C1 partial — `.gitignore` change acknowledged, JWT secret rotated. **DB + Gemini creds NOT rotated, `.env` still tracked.**
- C2 — purchase_history now uses `deps.get_current_user`. Fully fixed.
- C3 — `google-genai>=1.0.0` in requirements. Fully fixed.
- C4 — baseline migration now creates all four core tables. Fully fixed.
- C5 + H6 — `run_alternatives_agent` is `async`, `_search_live_web_listings` uses `httpx.AsyncClient`, endpoint `await`s. Fully fixed apart from R15.
- C6 — offer double-counting mostly resolved (bank/cashback/discount are mutually exclusive). Still one gap: coupon can co-emit with bank_discount (R17).
- H2 — `/api/v1/verdict/evaluate` endpoint exists, persists to `verdict_history` + `agent_results`. Works apart from R6, R7, R13.
- H3 — Postgres `price_snapshots` table + DB-backed history summary. Works apart from R2 (metadata not exported), R10 (silent fallback), R11 (stale reasoning text).
- H4 — deterministic alternatives returns empty list, no fabricated products. Fully fixed.
- H5 — Playwright provider wired in. Works apart from R3, R4, R5.
- M1 — `deps.py` is now the single source. Fully fixed.
- M2 — `UserLogin.password` has `max_length=72`. Fully fixed.
- M3 — CORS from env. Fully fixed.
- M4 — validator on JWT secret. Fully fixed.
- M5 — 500 handlers no longer leak exception text. Fully fixed.
- M6 — DOWN check-in no longer clobbers `usage_duration_days`. Fully fixed. (Introduces R8 though.)
- M7 — weekly-cap slice unconditional. Fixed apart from R9.
- M8 — `checkin_sent` has `server_default=sa.false()`. Fully fixed.
- M9 — `status` local renamed to `history_status`. Fully fixed.
- M11 — `api/__init__.py` `__all__` in sync. Fully fixed.
- M13 — `test_api_endpoint.py` deleted. Confirmed absent.
- M14 — `test_financial_agent.py` rewritten with real `assert`s. Fully fixed.
- M15 — `test_alternative_agent.py` uses stub provider and patches `_get_client`. Fully fixed.
- Integration tests exist (`test_integration.py`). Weak on migrations (R20).

---

## Summary

The Phase 1-6 fixes landed in the code, but three of the highest-severity items are only nominally done:
1. **R1** — `.env` was never actually purged and secrets never rotated. Same DB / Gemini creds are live.
2. **R2** — `PriceSnapshot` not registered in metadata → any future autogenerate will drop the table.
3. **R5** — the whole Playwright fallback is unreachable because instantiation can't fail; when chromium is missing, every deal query silently returns "unavailable" and the httpx branch never runs.

Everything else is either a moderate correctness bug (R6, R7, R8, R9, R13, R17) or cleanup that was checked off but not actually done (R23, R24, R26). Nothing crashes on import, but the "core product feature" (verdict orchestrator) still has silent-degradation paths that make its output unreliable.

Recommend fixing R1–R5 immediately, then R6–R9 as a small correctness pass, then the rest at leisure.
