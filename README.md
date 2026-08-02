# BudgetHive

AI-powered purchase decision assistant — BUY / MAYBE / SKIP.

BudgetHive evaluates whether a purchase is worth making by running four independent AI agents (Financial, Need, Deal Hunter, Alternatives) and aggregating their scores into a single verdict.

## Prerequisites

- Python 3.11+
- PostgreSQL (or Neon serverless Postgres)
- A Google Gemini API key

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# One-time: install Playwright's Chromium for Deal Hunter scraping
playwright install chromium
```

Copy the example env file and fill in your values:

```bash
cp .env.example .env
# Required vars: DATABASE_URL, GEMINI_API_KEY, JWT_SECRET_KEY
```

## Database

```bash
alembic upgrade head
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

API docs are served at `http://localhost:8000/docs`.

## Test

```bash
pytest backend/test
```

Set `TEST_DATABASE_URL` to point at a test Postgres instance. Tests skip gracefully if no DB URL is configured.

## Project Structure

```
backend/
  app/
    agents/       — AI agent implementations (financial, need, deal_hunter, alternatives)
    api/          — FastAPI route handlers
    db/           — SQLAlchemy engine & session
    models/       — ORM models
    schemas/      — Pydantic request/response schemas
  alembic/        — Database migrations
  test/           — Test suite
```
