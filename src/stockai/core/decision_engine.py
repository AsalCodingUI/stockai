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
    tp3 = decision.target2 * 1.08 if decision.target2 else None
    return {
        "entry_low": float(decision.entry_low or 0) or None,
        "entry_high": float(decision.entry_high or 0) or None,
        "stop_loss": float(decision.stop_loss or 0) or None,
        "tp1": float(decision.target1 or 0) or None,
        "tp2": float(decision.target2 or 0) or None,
        "tp3": float(tp3 or 0) or None,
        "rr": float(decision.risk_reward or 0) or None,
        "source": "unified_decision_engine_v1",
    }

