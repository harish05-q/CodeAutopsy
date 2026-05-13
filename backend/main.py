"""
FastAPI application entry point.

Sets up:
- CORS middleware
- Request ID middleware (injects unique ID per request for tracing)
- API route mounting
- Startup/shutdown lifecycle

Design decisions:
- Lifespan context manager for clean startup/shutdown (not deprecated on_event).
- Request ID middleware for observability without external dependencies.
- CORS configured via settings for flexibility.
"""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.api.dependencies.common import get_settings
from backend.api.routes.graphs import router as graphs_router
from backend.api.routes.repositories import router as repos_router
from backend.api.routes.search import router as search_router
from backend.core.logger import get_logger, request_id_var, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Runs setup on startup and cleanup on shutdown.
    """
    settings = get_settings()
    setup_logging(
        log_level=settings.log_level,
        json_output=not settings.debug,
    )
    settings.ensure_directories()
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        debug=settings.debug,
    )
    yield
    logger.info("application_shutting_down")


app = FastAPI(
    title="CodeAutopsy",
    description=(
        "AI-powered static analysis and architecture reverse-engineering platform. "
        "Analyzes GitHub repositories and generates architecture documentation, "
        "dependency maps, call graphs, risk analysis, and PDF autopsy reports."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID Middleware ───────────────────────────────────────
@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    """
    Inject a unique request ID into every request for tracing.

    The ID is:
    - Set in a context variable for structured logging.
    - Returned as X-Request-ID header in the response.
    - Available to all downstream code via request_id_var.
    """
    req_id = uuid.uuid4().hex[:12]
    request_id_var.set(req_id)

    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start

    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time"] = f"{duration:.3f}s"

    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration=round(duration, 3),
    )

    return response


# ── Health Check ────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "codeautopsy"}


# ── Mount Routes ────────────────────────────────────────────────
app.include_router(repos_router)
app.include_router(graphs_router)
app.include_router(search_router)
