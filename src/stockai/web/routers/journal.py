"""Trade Journal API router."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["journal"])


class TradePlanCreate(BaseModel):
    symbol: str
    tujuan: str = "swing"
    modal: float = 5_000_000
    entry_low: float
    entry_high: float
    stop_loss: float
    tp1: float
    tp2: float | None = None
    tp3: float | None = None
    notes: str | None = None
    ai_summary: str | None = None


class CheckPriceRequest(BaseModel):
    price: float | None = None


@router.post("/plans", status_code=201)
async def create_plan(body: TradePlanCreate) -> dict[str, Any]:
    """Create a new trade plan."""
    if body.entry_low > body.entry_high:
        raise HTTPException(status_code=400, detail="entry_low must be <= entry_high")
    if body.stop_loss >= body.entry_low:
        raise HTTPException(status_code=400, detail="stop_loss must be < entry_low")
    if body.tp1 <= body.entry_high:
        raise HTTPException(status_code=400, detail="tp1 must be > entry_high")

    from stockai.core.journal import get_journal_service

    svc = get_journal_service()
    plan = svc.create_plan(
        symbol=body.symbol.upper(),
        tujuan=body.tujuan,
        modal=body.modal,
        entry_low=body.entry_low,
        entry_high=body.entry_high,
        stop_loss=body.stop_loss,
        tp1=body.tp1,
        tp2=body.tp2,
        tp3=body.tp3,
        notes=body.notes,
        ai_summary=body.ai_summary,
    )
    return plan


@router.get("/plans")
async def list_plans(
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    """List trade plans with optional filters."""
    from stockai.core.journal import get_journal_service

    svc = get_journal_service()
    plans = svc.list_plans(symbol=symbol, status=status, limit=limit)
    return {"plans": plans, "total": len(plans)}


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: int) -> dict[str, Any]:
    """Get a single trade plan by ID."""
    from stockai.core.journal import get_journal_service

    svc = get_journal_service()
    plan = svc.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan


@router.delete("/plans/{plan_id}")
async def cancel_plan(plan_id: int) -> dict[str, Any]:
    """Cancel a trade plan."""
    from stockai.core.journal import get_journal_service

    svc = get_journal_service()
    success = svc.cancel_plan(plan_id)
    if not success:
        return {"success": False, "message": f"Plan {plan_id} not found or already closed"}
    return {"success": True, "message": f"Plan {plan_id} cancelled"}


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Get journal statistics."""
    from stockai.core.journal import get_journal_service

    svc = get_journal_service()
    return svc.get_stats()


@router.post("/plans/{plan_id}/check")
async def check_outcome(plan_id: int, body: CheckPriceRequest = CheckPriceRequest()) -> dict[str, Any]:
    """Check outcome for a trade plan, optionally fetching live price."""
    from stockai.core.journal import get_journal_service

    svc = get_journal_service()

    # Ensure plan exists
    plan = svc.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    price = body.price
    if price is None:
        from stockai.data.sources.yahoo import YahooFinanceSource

        yahoo = YahooFinanceSource()
        info = yahoo.get_stock_info(plan["symbol"])
        price = info.get("current_price") or info.get("previousClose")
        if price is None:
            raise HTTPException(status_code=502, detail="Could not fetch live price for symbol")

    result = svc.check_outcome(plan_id, price)
    return {
        "plan_id": plan_id,
        "symbol": plan["symbol"],
        "price": price,
        "outcome": result["outcome"],
        "pnl_pct": result.get("pnl_pct"),
        "message": result["message"],
    }


@router.get("/plans/{plan_id}/history")
async def get_plan_history(plan_id: int) -> dict[str, Any]:
    """Get outcome check history for a trade plan."""
    from stockai.data.database import session_scope
    from stockai.data.models import TradeOutcome

    with session_scope() as sess:
        rows = (
            sess.query(TradeOutcome)
            .filter(TradeOutcome.plan_id == plan_id)
            .order_by(TradeOutcome.checked_at.desc())
            .limit(100)
            .all()
        )
        return {
            "history": [
                {
                    "id": r.id,
                    "checked_at": r.checked_at.isoformat(),
                    "price": r.price_at_check,
                    "outcome": r.outcome,
                    "pnl_pct": r.pnl_pct,
                }
                for r in rows
            ]
        }


class ClosePlanRequest(BaseModel):
    exit_price: float
    notes: str | None = None


@router.post("/plans/{plan_id}/close")
async def close_plan_manually(plan_id: int, body: ClosePlanRequest) -> dict[str, Any]:
    """Manually close a trade plan with the actual exit price."""
    from stockai.core.journal import get_journal_service
    from stockai.data.database import session_scope
    from stockai.data.models import TradePlan, TradeOutcome
    from datetime import datetime

    svc = get_journal_service()
    plan = svc.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    if plan["status"] not in ("OPEN",):
        raise HTTPException(status_code=400, detail=f"Plan {plan_id} is already closed (status={plan['status']})")

    entry_mid = (plan["entry_low"] + plan["entry_high"]) / 2
    pnl_pct = round((body.exit_price / entry_mid - 1) * 100, 2) if entry_mid else None

    # Determine outcome label
    if pnl_pct is not None and pnl_pct < 0:
        outcome = "SL_HIT"
    elif plan["tp3"] and body.exit_price >= plan["tp3"]:
        outcome = "TP3_HIT"
    elif plan["tp2"] and body.exit_price >= plan["tp2"]:
        outcome = "TP2_HIT"
    elif body.exit_price >= plan["tp1"]:
        outcome = "TP1_HIT"
    else:
        outcome = "MANUAL_CLOSE"

    with session_scope() as sess:
        p = sess.get(TradePlan, plan_id)
        p.status = outcome
        p.exit_price = body.exit_price
        p.exit_date = datetime.utcnow()
        p.pnl_pct = pnl_pct
        p.days_held = (datetime.utcnow() - p.created_at).days
        p.updated_at = datetime.utcnow()
        if body.notes:
            p.notes = (p.notes or "") + f"\n[Close note] {body.notes}"
        rec = TradeOutcome(
            plan_id=plan_id,
            price_at_check=body.exit_price,
            outcome=outcome,
            pnl_pct=pnl_pct,
            notes=body.notes,
        )
        sess.add(rec)

    return {
        "plan_id": plan_id,
        "symbol": plan["symbol"],
        "outcome": outcome,
        "exit_price": body.exit_price,
        "pnl_pct": pnl_pct,
        "message": f"Plan {plan_id} closed as {outcome} @ Rp {body.exit_price:,.0f} ({pnl_pct:+.1f}%)",
    }


@router.get("/ai-feedback")
async def get_ai_feedback() -> dict[str, Any]:
    """Get AI coaching feedback based on trade journal history."""
    from stockai.core.journal import get_journal_service
    from stockai.core.journal.ai_feedback import analyze_journal_patterns

    svc = get_journal_service()
    stats = svc.get_stats()
    plans = svc.list_plans(limit=100)

    feedback = analyze_journal_patterns(stats, plans)
    return {"stats": stats, "feedback": feedback}
