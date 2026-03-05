"""
HealthGuard Central Server – FastAPI Application Entry Point.

Receives synced data from HealthGuard edge nodes.
Designed for deployment on Render.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database.database import init_db
from app.routes import sync

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("healthguard-central")

settings = get_settings()


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("=" * 60)
    logger.info("  HealthGuard Central Server  –  Starting Up")
    logger.info(f"  Allowed API keys : {len(settings.api_keys_list)} configured")
    logger.info("=" * 60)

    # Create tables on startup
    await init_db()
    logger.info("✅ Database initialised")

    yield

    logger.info("👋 HealthGuard Central Server stopped")


# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="HealthGuard Central Server",
    description="Receives synced vital signs from HealthGuard edge nodes",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(sync.router)


# ── Health check ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "HealthGuard Central Server",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint for Render."""
    return {"status": "healthy"}
