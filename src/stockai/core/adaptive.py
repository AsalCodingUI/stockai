"""Adaptive weighting engine for signal confidence tuning."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WEIGHTS_FILE = Path.home() / ".stockai" / "adaptive_weights.json"
OUTCOMES_FILE = Path.home() / ".stockai" / "adaptive_outcomes.jsonl"


@dataclass
class AdaptiveWeights:
    technical: float = 1.0
    sentiment: float = 1.0
    breadth: float = 1.0
    mtf: float = 1.0
    rr: float = 1.0
    version: int = 1


class AdaptiveWeightEngine:
    """Simple online weight tuner for confidence calibration."""

    def __init__(self) -> None:
        self.weights = AdaptiveWeights()
        self._load()

    def _load(self) -> None:
        try:
            if not WEIGHTS_FILE.exists():
                return
            raw = json.loads(WEIGHTS_FILE.read_text(encoding="utf-8"))
            self.weights = AdaptiveWeights(
                technical=float(raw.get("technical", 1.0)),
                sentiment=float(raw.get("sentiment", 1.0)),
                breadth=float(raw.get("breadth", 1.0)),
                mtf=float(raw.get("mtf", 1.0)),
                rr=float(raw.get("rr", 1.0)),
                version=int(raw.get("version", 1)),
            )
        except Exception as exc:
            logger.warning("Adaptive weights load failed: %s", exc)

    def _save(self) -> None:
        try:
            WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            WEIGHTS_FILE.write_text(
                json.dumps(self.weights.__dict__, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Adaptive weights save failed: %s", exc)

    def adjust_confidence(
        self,
        *,
        decision: Any,
        snapshot: Any,
        mtf_score: int = 0,
    ) -> tuple[int, list[str]]:
        """Return adjusted confidence and reason tags."""
        base = int(getattr(decision, "confidence", 50))
        adj = 0.0
        reasons: list[str] = []

        gate_total = max(1, int(getattr(snapshot, "gate_total", 8) or 8))
        gate_score = int(getattr(snapshot, "gate_score", 0) or 0)
        gate_ratio = gate_score / gate_total
        if gate_ratio >= 0.7:
            adj += 7 * self.weights.technical
            reasons.append("technical_strong")
        elif gate_ratio <= 0.35:
            adj -= 9 * self.weights.technical
            reasons.append("technical_weak")

        sentiment_label = str(getattr(snapshot, "sentiment_label", "NEUTRAL")).upper()
        sentiment_score = float(getattr(snapshot, "sentiment_score", 50.0) or 50.0)
        if sentiment_label in {"POSITIVE", "BULLISH"} and sentiment_score >= 55:
            adj += 5 * self.weights.sentiment
            reasons.append("sentiment_positive")
        elif sentiment_label in {"NEGATIVE", "BEARISH"} and sentiment_score <= 45:
            adj -= 7 * self.weights.sentiment
            reasons.append("sentiment_negative")

        breadth = str(getattr(snapshot, "market_breadth", "MIXED")).upper()
        if breadth == "RISK_ON":
            adj += 4 * self.weights.breadth
            reasons.append("breadth_risk_on")
        elif breadth == "RISK_OFF":
            adj -= 6 * self.weights.breadth
            reasons.append("breadth_risk_off")

        if mtf_score >= 2:
            adj += 6 * self.weights.mtf
            reasons.append("mtf_aligned")
        elif mtf_score <= -2:
            adj -= 10 * self.weights.mtf
            reasons.append("mtf_conflict")

        rr = float(getattr(decision, "risk_reward", 0.0) or 0.0)
        if rr >= 2.0:
            adj += 4 * self.weights.rr
            reasons.append("rr_good")
        elif rr <= 1.1:
            adj -= 5 * self.weights.rr
            reasons.append("rr_poor")

        adjusted = int(max(1, min(99, round(base + adj))))
        return adjusted, reasons

    def record_outcome(
        self,
        *,
        symbol: str,
        action: str,
        predicted_confidence: int,
        realized_return_pct: float,
        hold_days: int = 1,
    ) -> dict[str, Any]:
        """Update weights with lightweight online learning."""
        action_u = str(action or "WAIT").upper()
        reward = float(realized_return_pct)

        # Only train on actionable entries.
        if action_u == "ENTRY_NOW":
            if reward > 0:
                self.weights.technical = min(1.8, self.weights.technical + 0.01)
                self.weights.mtf = min(1.8, self.weights.mtf + 0.01)
                self.weights.rr = min(1.8, self.weights.rr + 0.008)
            else:
                self.weights.technical = max(0.4, self.weights.technical - 0.015)
                self.weights.mtf = max(0.4, self.weights.mtf - 0.012)
                self.weights.rr = max(0.4, self.weights.rr - 0.01)

            # Sentiment and breadth are treated as lower-confidence priors.
            if reward > 0:
                self.weights.sentiment = min(1.6, self.weights.sentiment + 0.005)
                self.weights.breadth = min(1.6, self.weights.breadth + 0.005)
            else:
                self.weights.sentiment = max(0.5, self.weights.sentiment - 0.006)
                self.weights.breadth = max(0.5, self.weights.breadth - 0.006)

        self._save()
        row = {
            "time": datetime.now().isoformat(),
            "symbol": symbol.upper().strip(),
            "action": action_u,
            "predicted_confidence": int(predicted_confidence),
            "realized_return_pct": reward,
            "hold_days": int(hold_days),
            "weights": self.weights.__dict__,
        }
        try:
            OUTCOMES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with OUTCOMES_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("Adaptive outcome append failed: %s", exc)
        return row

    def get_status(self) -> dict[str, Any]:
        return {"weights": self.weights.__dict__, "weights_file": str(WEIGHTS_FILE)}


_engine: AdaptiveWeightEngine | None = None


def get_adaptive_weight_engine() -> AdaptiveWeightEngine:
    global _engine
    if _engine is None:
        _engine = AdaptiveWeightEngine()
    return _engine

