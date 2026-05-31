"""System router — status, dashboard, scheduler, search."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from stockai import __version__
from stockai.core.calendar import market_status
from stockai.data.database import init_database
from stockai.data.listings import get_stock_database
from stockai.data.sources.yahoo import YahooFinanceSource
from stockai.web.utils import (
    _WEB_RUNTIME,
    _is_scan_cache_fresh,
    _now_iso,
    _rank_search_results,
)

router = APIRouter(tags=["system"])


@router.get("/status")
async def api_status() -> dict:
    """Get API status and version."""
    return {
        "status": "ok",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat(),
        "market_status": market_status(),
    }


@router.get("/dashboard")
async def get_dashboard() -> dict:
    """Dashboard aggregate data."""
    yahoo = YahooFinanceSource()
    ihsg_history = []
    ihsg_quote = {"price": None, "change_pct": None}

    try:
        import yfinance as yf

        df = yf.Ticker("^JKSE").history(period="7d", interval="1d")
        if not df.empty:
            for idx, row in df.iterrows():
                ihsg_history.append({
                    "time": idx.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                })
            if len(df) >= 2:
                last_close = float(df["Close"].iloc[-1])
                prev_close = float(df["Close"].iloc[-2])
                change_pct = ((last_close / prev_close) - 1) * 100 if prev_close else 0
                ihsg_quote = {"price": round(last_close, 2), "change_pct": round(change_pct, 2)}
    except Exception:
        pass

    init_database()
    from stockai.core.portfolio import PnLCalculator

    portfolio = PnLCalculator().get_portfolio_summary()
    last_scan = _WEB_RUNTIME.get("last_scan") if _is_scan_cache_fresh() else None
    results = (last_scan or {}).get("results", [])
    ready_count = len([r for r in results if r.get("status") in ("A+", "A", "READY")])
    watch_count = len([r for r in results if r.get("status") in ("B", "WATCH")])

    scheduler_info = {"running": False, "next_scan": None}
    try:
        from stockai.scheduler.runner import scheduler_status

        status = scheduler_status()
        next_scan = None
        for row in status.get("jobs", []):
            if row.get("id") == "morning_scan":
                next_scan = row.get("next_run")
                break
        scheduler_info = {"running": status.get("running", False), "next_scan": next_scan}
    except Exception:
        pass

    return {
        "server_time": _now_iso(),
        "live_status": "LIVE",
        "scheduler": scheduler_info,
        "ihsg": {"quote": ihsg_quote, "history_7d": ihsg_history},
        "regime": (last_scan or {}).get("regime"),
        "last_scan": {
            "index": (last_scan or {}).get("index", "ALL"),
            "scanned": int((last_scan or {}).get("scanned", 0)),
            "ready": ready_count,
            "watch": watch_count,
            "timestamp": (last_scan or {}).get("timestamp"),
            "results": results[:20],
        },
        "portfolio_summary": portfolio.get("summary", {}),
    }


@router.get("/scheduler/status")
async def get_scheduler_status() -> dict:
    try:
        from stockai.scheduler.runner import scheduler_status

        return scheduler_status()
    except Exception as exc:
        return {"running": False, "jobs": [], "error": str(exc)}


@router.get("/search")
async def api_search_stocks(
    q: str = Query("", description="Stock query by symbol/name"),
) -> dict:
    """Global stock search endpoint with autocomplete-friendly response."""
    query = (q or "").strip()
    if len(query) < 2:
        return {"results": [], "total": 0, "query": query}

    db = get_stock_database()
    matches = db.search(query, limit=20)
    matches = _rank_search_results(matches, query)
    results = []
    for row in matches[:10]:
        symbol = str(row.get("symbol", "")).upper().strip()
        if not symbol:
            continue
        results.append(
            {
                "symbol": symbol,
                "name": str(row.get("name", "")).strip(),
                "sector": str(row.get("sector", "Unknown")).strip() or "Unknown",
                "url": f"/stock/{symbol}",
            }
        )

    return {"results": results, "total": len(results), "query": query}
