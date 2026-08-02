from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import auth, users, deal_hunter, financial, need, alternatives, purchase_history, verdict

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