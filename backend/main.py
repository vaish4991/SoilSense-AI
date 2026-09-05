"""
SoilSense AI — FastAPI Application Entry Point

Startup sequence:
  1. Configure structured logging
  2. Load environment variables
  3. Load ML model (train automatically if not found)
  4. Mount API router
  5. Start server
"""
from __future__ import annotations
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before anything imports settings
load_dotenv()

from backend.api.routes import router
from backend.ml.predict import load_model, is_model_loaded

# ─────────────────────────────────────────────────────────────
# Logging configuration
# ─────────────────────────────────────────────────────────────
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("soilsense.main")

# ─────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan — runs on startup and shutdown."""
    logger.info("SoilSense AI starting up…")
    loaded = load_model()
    if not loaded:
        logger.warning("ML model not found. Attempting to train automatically…")
        try:
            project_root = Path(__file__).resolve().parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from backend.ml.train import train
            train()
            loaded = load_model()
            if loaded:
                logger.info("Model trained and loaded successfully.")
            else:
                logger.error("Model training completed but model still not loadable.")
        except Exception as exc:
            logger.error("Auto-training failed: %s", exc, exc_info=True)
            logger.warning("Run 'python -m backend.ml.train' manually.")
    logger.info("ML model loaded: %s", is_model_loaded())
    logger.info("SoilSense AI ready.")
    yield
    logger.info("SoilSense AI shutting down.")


app = FastAPI(
    title="SoilSense AI",
    description=(
        "AI-powered soil intelligence agent. "
        "Estimates soil pH from natural-language descriptions using ML, "
        "integrates live weather data, and recommends suitable crops."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# CORS — allow frontend dev server and production origins
cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Mount routes
# ─────────────────────────────────────────────────────────────
app.include_router(router)




@app.get("/")
async def root():
    return {
        "service": "SoilSense AI",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
