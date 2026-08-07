from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.config import settings
from app.api import auth, users, deal_hunter, financial, need, alternatives, purchase_history, verdict, regret_predictor

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered purchase decision assistant — BUY / MAYBE / SKIP",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ------------------------------------------------------------------
# CORS — allow the React frontend to talk to this API
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(deal_hunter.router)
app.include_router(financial.router)
app.include_router(need.router)
app.include_router(alternatives.router)
app.include_router(purchase_history.router)
app.include_router(verdict.router)
app.include_router(regret_predictor.router)


# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "1.0.0",
    }


# ------------------------------------------------------------------
# Root
# ------------------------------------------------------------------
@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API 🐝",
        "docs": "/docs",
    }


# ------------------------------------------------------------------
# SPA fallback for frontend routes (login, signup, dashboard, etc.)
# ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend_app(request: Request, full_path: str):
    if full_path.startswith(("api/", "auth/", "users/", "health", "docs", "redoc", "openapi.json")):
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    if FRONTEND_DIST.exists():
        candidate_path = FRONTEND_DIST / full_path
        if candidate_path.exists() and candidate_path.is_file():
            return FileResponse(candidate_path)

        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(index_file)

    return HTMLResponse(
        """
        <!doctype html>
        <html lang=\"en\">
          <head>
            <meta charset=\"utf-8\">
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
            <title>BudgetHive</title>
          </head>
          <body>
            <h1>BudgetHive</h1>
            <p>The frontend bundle is not built yet. Run the frontend build to enable the app shell.</p>
          </body>
        </html>
        """,
        status_code=200,
    )