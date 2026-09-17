"""
FastAPI application entry point.

Sets up:
  - CORS middleware (configured via env vars)
  - Database table creation on startup
  - Logging configuration
  - API router registration
  - Health check endpoint
  - Global exception handler
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import create_tables
from app.routers.addresses import router as address_router

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("Starting UrbanDash Address Parser")
    create_tables()
    logger.info("Database tables created")
    logger.info("Claude API configured: %s", "Yes" if settings.has_claude_key else "No (using fallback parser)")
    yield
    logger.info("Shutting down UrbanDash Address Parser")


app = FastAPI(
    title="UrbanDash Address Parser",
    description="AI-powered Indian address parsing system for quick-commerce delivery",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(address_router)


# -------------------------------------------------------------------
# Health check
# -------------------------------------------------------------------

@app.get("/api/health", tags=["system"])
def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "urbandash-address-parser",
        "claude_configured": settings.has_claude_key,
    }


# -------------------------------------------------------------------
# Global exception handler — never expose stack traces
# -------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, str(exc)[:300])
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )
