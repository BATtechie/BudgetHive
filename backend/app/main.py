from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.init_db import init_db

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered purchase decision assistant — BUY / MAYBE / SKIP",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()

# ------------------------------------------------------------------
# CORS — allow the React frontend to talk to this API
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
