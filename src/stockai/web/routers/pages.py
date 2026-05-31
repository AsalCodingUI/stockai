"""Pages router — all HTML page routes."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from stockai import __version__
from stockai.data.database import init_database
from stockai.data.sources.idx import IDXIndexSource

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Dashboard home page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "StockAI Dashboard",
            "version": __version__,
        },
    )


@router.get("/stocks")
async def stocks_page():
    """Redirect compatibility stocks to home page."""
    return RedirectResponse(url="/", status_code=302)


@router.get("/analyze/{symbol}", response_class=HTMLResponse)
async def analyze_page(request: Request, symbol: str):
    """Legacy analyze page (kept for compatibility)."""
    return await stock_page(request, symbol)


@router.get("/scan")
async def scan_page():
    """Redirect scan page to home dashboard."""
    return RedirectResponse(url="/", status_code=302)


@router.get("/backtest")
async def backtest_page():
    """Redirect backtest page to home dashboard."""
    return RedirectResponse(url="/", status_code=302)


@router.get("/coach", response_class=HTMLResponse)
async def coach_page(request: Request):
    """AI entry coach page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "coach.html",
        {
            "request": request,
            "title": "AI Entry Coach",
        },
    )


@router.get("/stock/{symbol}", response_class=HTMLResponse)
async def stock_page(request: Request, symbol: str):
    """Stock detail page."""
    templates = request.app.state.templates

    idx_source = IDXIndexSource()
    info = idx_source.get_stock_details(symbol.upper())

    if not info:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    return templates.TemplateResponse(
        "stock.html",
        {
            "request": request,
            "title": f"Analyze {symbol.upper()}",
            "symbol": symbol.upper(),
            "stock_info": info,
        },
    )


@router.get("/portfolio")
async def portfolio_page():
    """Redirect portfolio page to journal/performance page."""
    return RedirectResponse(url="/journal", status_code=302)


@router.get("/sentiment")
async def sentiment_page():
    """Redirect legacy sentiment page to alerts."""
    return RedirectResponse(url="/alerts", status_code=302)


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request):
    """Notification center page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "alerts.html",
        {
            "request": request,
            "title": "Alerts Feed",
        },
    )


@router.get("/journal", response_class=HTMLResponse)
async def journal_page(request: Request):
    """Signal Performance page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "journal.html",
        {
            "request": request,
            "title": "Signal Performance",
        },
    )


@router.get("/watchlist")
async def watchlist_page():
    """Redirect watchlist to AI coach focus list page."""
    return RedirectResponse(url="/coach", status_code=302)
