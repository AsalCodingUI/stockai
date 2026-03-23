"""FastAPI Application for StockAI Web Dashboard.

Provides web interface for stock analysis, portfolio management,
and sentiment tracking.
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from stockai import __version__
from stockai.config import get_settings

logger = logging.getLogger(__name__)

# Get templates directory
WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI instance
    """
    app = FastAPI(
        title="StockAI Dashboard",
        description="AI-Powered Indonesian Stock Analysis Dashboard",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Setup templates and static files
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Store templates in app state
    app.state.templates = templates

    # Include routers
    from stockai.web.routes import api_router, pages_router

    app.include_router(api_router, prefix="/api")
    app.include_router(pages_router)

    @app.on_event("startup")
    async def startup_event():
        from stockai.scheduler.runner import start_scheduler
        from stockai.core.monitor import get_monitor

        app.state.scheduler = start_scheduler()
        app.state.watchlist_monitor = get_monitor()
        app.state.watchlist_monitor.start()
        logger.info("✅ Scheduler started")
        logger.info("✅ Watchlist monitor started")

    @app.on_event("shutdown")
    async def shutdown_event():
        from stockai.scheduler.runner import shutdown_scheduler

        shutdown_scheduler(wait=False)
        monitor = getattr(app.state, "watchlist_monitor", None)
        if monitor is not None:
            monitor.stop()

    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if request.headers.get("accept") == "application/json":
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail},
            )
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": exc.detail, "status_code": exc.status_code},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": __version__}

    logger.info("StockAI Web Dashboard initialized")
    return app


# Create app instance
app = create_app()
