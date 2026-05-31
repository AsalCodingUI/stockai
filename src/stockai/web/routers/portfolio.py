"""Portfolio router — all /portfolio/* and /alerts/* endpoints."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from stockai.data.database import init_database
from stockai.web.utils import (
    _WEB_RUNTIME,
    ALERT_DISMISS_TTL_SECONDS,
    _compose_alerts,
    _now_iso,
    _portfolio_history,
    _risk_metrics_from_history,
)
from stockai.web.utils import PortfolioPositionCreate, PortfolioPositionUpdate

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio/summary")
async def get_portfolio_summary_v2() -> dict:
    init_database()
    from stockai.core.portfolio import PnLCalculator

    summary = PnLCalculator().get_portfolio_summary()
    history = _portfolio_history(days=30)
    metrics = _risk_metrics_from_history(history, summary.get("positions", []))
    return {
        "summary": summary.get("summary", {}),
        "positions": summary.get("positions", []),
        "risk_metrics": metrics,
    }


@router.get("/portfolio/history")
async def get_portfolio_history(days: int = Query(30, ge=7, le=365)) -> dict:
    init_database()
    history = _portfolio_history(days=days)
    return {"days": days, "history": history}


@router.post("/portfolio/position")
async def add_portfolio_position(payload: PortfolioPositionCreate) -> dict:
    init_database()
    from stockai.core.portfolio import PortfolioManager

    manager = PortfolioManager()
    try:
        result = manager.add_position(
            symbol=payload.symbol.upper(),
            shares=payload.shares,
            price=payload.price,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "position": result}


@router.put("/portfolio/position/{symbol}")
async def update_portfolio_position(symbol: str, payload: PortfolioPositionUpdate) -> dict:
    clean_symbol = symbol.upper().strip()
    meta = _WEB_RUNTIME.setdefault("portfolio_meta", {})
    current = dict(meta.get(clean_symbol, {}))
    if payload.stop_loss is not None:
        current["stop_loss"] = payload.stop_loss
    if payload.take_profit is not None:
        current["take_profit"] = payload.take_profit
    if payload.notes is not None:
        current["notes"] = payload.notes
    current["updated_at"] = _now_iso()
    meta[clean_symbol] = current
    return {"ok": True, "symbol": clean_symbol, "meta": current}


@router.delete("/portfolio/position/{symbol}")
async def delete_portfolio_position(symbol: str) -> dict:
    init_database()
    from stockai.core.portfolio import PortfolioManager

    manager = PortfolioManager()
    try:
        result = manager.remove_position(symbol.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "result": result}


@router.get("/portfolio")
async def get_portfolio() -> dict:
    """Get portfolio positions with P&L."""
    init_database()

    from stockai.core.portfolio import PnLCalculator

    pnl_calc = PnLCalculator()
    summary = pnl_calc.get_portfolio_summary()

    return summary


@router.get("/portfolio/analytics")
async def get_portfolio_analytics() -> dict:
    """Get portfolio analytics."""
    init_database()

    from stockai.core.portfolio import PortfolioAnalytics

    analytics = PortfolioAnalytics()
    analysis = analytics.get_full_analysis()
    insights = analytics.generate_ai_insights(analysis)

    analysis["insights"] = insights
    return analysis


@router.get("/alerts")
async def list_alerts() -> dict:
    return {"alerts": _compose_alerts(), "generated_at": _now_iso()}


@router.delete("/alerts")
async def clear_alerts() -> dict:
    _WEB_RUNTIME["alerts_dismissed_until"] = datetime.utcnow() + timedelta(seconds=ALERT_DISMISS_TTL_SECONDS)
    return {"ok": True, "dismissed_until": _WEB_RUNTIME["alerts_dismissed_until"].isoformat()}
