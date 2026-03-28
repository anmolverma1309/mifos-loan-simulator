"""
Mifos Loan Amortisation & What-if Simulator Service
Main FastAPI application entry point.

GSoC 2026 Project — The Mifos Initiative
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.simulator import router as simulator_router
from app.core.config import settings
from app.models.schemas import HealthResponse
from app.services.cache import init_redis, close_redis, is_connected

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_redis()
    yield
    # Shutdown
    await close_redis()
    logger.info("Service stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Mifos Loan Amortisation & What-if Simulator

A standalone Python microservice that provides flexible loan amortisation 
calculations and what-if simulations for the Mifos X ecosystem.

### Features
- **EMI Calculation** — Flat rate and declining balance methods
- **Amortisation Schedule** — Full month-by-month breakdown
- **What-if Simulations** — Prepayment, rate change, moratorium scenarios
- **Redis Caching** — High performance for repeated queries
- **Mifos X Integration** — Fetch live loan data via Apache Fineract API

### Supported Repayment Methods
- `declining_balance` — Interest on outstanding principal (most common in MFIs)
- `flat_rate` — Interest on original principal throughout tenure

### Financial Precision
All calculations use Python's `decimal.Decimal` module with `ROUND_HALF_UP` 
to ensure cent-level accuracy required in microfinance operations.

### Integration
This service integrates with:
- Mifos X Web App (`web-app` repository)
- Mifos Android Client (`android-client` repository)
- Apache Fineract API (for live loan data)

**GSoC 2026 | The Mifos Initiative**
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Mifos X web app and android client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(simulator_router)


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health Check",
)
async def health_check():
    """Service health check — confirms service is running and cache status."""
    cache_ok = await is_connected()
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        cache_connected=cache_ok,
    )


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
