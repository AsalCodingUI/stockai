"""Breakout quality scoring."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stockai.scoring.support_resistance import find_support_resistance


@dataclass
class BreakoutResult:
    """Breakout quality summary."""

    volume_ratio: float
    breakout_score: float
    broke_resistance: bool


def evaluate_breakout_quality(history: pd.DataFrame) -> BreakoutResult:
    if history is None or history.empty:
        return BreakoutResult(volume_ratio=0.0, breakout_score=0.0, broke_resistance=False)

    df = history.tail(60).copy()
    closes = df["close"].astype(float)
    volumes = df["volume"].astype(float)
    latest_close = float(closes.iloc[-1])
    latest_volume = float(volumes.iloc[-1])
    avg_volume_20d = float(volumes.tail(20).mean()) if len(volumes) >= 20 else float(volumes.mean())
    volume_ratio = latest_volume / avg_volume_20d if avg_volume_20d > 0 else 0.0

    if volume_ratio >= 2.0:
        score = 20.0
    elif volume_ratio >= 1.5:
        score = 12.0
    elif volume_ratio >= 1.0:
        score = 5.0
    else:
        score = 0.0

    sr = find_support_resistance(df)
    broke_resistance = bool(sr.nearest_resistance and latest_close > sr.nearest_resistance)
    if broke_resistance:
        score = min(25.0, score + 5.0)

    return BreakoutResult(
        volume_ratio=float(volume_ratio),
        breakout_score=float(score),
        broke_resistance=broke_resistance,
    )
