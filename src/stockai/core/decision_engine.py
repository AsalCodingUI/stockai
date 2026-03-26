"""Unified decision engine for TP/SL and action consistency across app."""

from __future__ import annotations

import logging
from typing import Any

from stockai.core.adaptive import get_adaptive_weight_engine
from stockai.core.coach import CoachDecision, analyze_entry

logger = logging.getLogger(__name__)


async def generate_unified_decision(
    *,
    symbol: str,
    df: Any,
    modal: int = 5_000_000,
    tujuan: str = "swing",
    ihsg_trend: str = "UNKNOWN",
    sentiment_label: str = "NEUTRAL",
    sentiment_score: float = 50.0,
    news_bias: str = "NEUTRAL",
    market_breadth: str = "MIXED",
    advance_ratio: float = 0.5,
    leading_sector: str = "UNKNOWN",
    lagging_sector: str = "UNKNOWN",
    mtf_score: int = 0,
) -> CoachDecision:
    """Generate one canonical decision used by web/monitor/alerts."""
    decision = await analyze_entry(
        symbol=symbol,
        df=df,
        modal=modal,
        tujuan=tujuan,
        ihsg_trend=ihsg_trend,
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        news_bias=news_bias,
        market_breadth=market_breadth,
        advance_ratio=advance_ratio,
        leading_sector=leading_sector,
        lagging_sector=lagging_sector,
    )

    # Stage-3 adaptive calibration.
    adaptive = get_adaptive_weight_engine()
    if decision.snapshot:
        adjusted_conf, reason_tags = adaptive.adjust_confidence(
            decision=decision,
            snapshot=decision.snapshot,
            mtf_score=mtf_score,
        )
        decision.confidence = adjusted_conf
        if reason_tags:
            reason_label = f"Adaptive: {', '.join(reason_tags)}"
            if reason_label not in decision.warning:
                decision.warning.append(reason_label)

    # Enforce consistency rules in one place.
    if mtf_score <= -2 and decision.action == "ENTRY_NOW":
        decision.action = "WAIT"
        decision.confidence = max(25, decision.confidence - 20)
        decision.warning.append("MTF conflict: trend kecil tidak searah dengan trend besar.")
    if decision.risk_reward > 0 and decision.risk_reward < 1.1 and decision.action == "ENTRY_NOW":
        decision.action = "WAIT"
        decision.warning.append("Risk/reward kurang ideal untuk entry agresif.")

    return decision


def decision_to_trade_plan(decision: CoachDecision) -> dict[str, Any]:
    """Normalize decision fields to canonical trade plan schema."""
    tujuan = str(getattr(decision, "tujuan", "swing") or "swing").lower()
    entry_low = float(decision.entry_low or 0) or None
    entry_high = float(decision.entry_high or 0) or None
    stop_loss = float(decision.stop_loss or 0) or None
    tp1 = float(decision.target1 or 0) or None
    tp2 = float(decision.target2 or 0) or None
    tp3 = (tp2 * 1.08) if tp2 else None

    # Intraday/swing-harian profile: tighten targets and risk window.
    if tujuan == "scalp" and entry_high:
        scalp_tp1 = round(entry_high * 1.03, 2)
        scalp_tp2 = round(entry_high * 1.06, 2)
        scalp_tp3 = round(entry_high * 1.09, 2)
        scalp_sl = round(entry_low * 0.98, 2) if entry_low else round(entry_high * 0.98, 2)

        tp1 = min(tp1, scalp_tp1) if tp1 else scalp_tp1
        tp2 = min(tp2, scalp_tp2) if tp2 else scalp_tp2
        tp3 = min(tp3, scalp_tp3) if tp3 else scalp_tp3
        if stop_loss:
            stop_loss = max(stop_loss, scalp_sl)
        else:
            stop_loss = scalp_sl

    rr = None
    if entry_low and stop_loss and tp1:
        risk = entry_low - stop_loss
        reward = tp1 - entry_low
        rr = round((reward / risk), 2) if risk > 0 else None

    return {
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "rr": rr if rr is not None else (float(decision.risk_reward or 0) or None),
        "tujuan": tujuan,
        "source": "unified_decision_engine_v1",
    }
