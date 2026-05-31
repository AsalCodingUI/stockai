"""Candlestick pattern scoring."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class CandleResult:
    """Candlestick interpretation."""

    pattern: str
    score: float


def detect_bullish_pattern(history: pd.DataFrame) -> CandleResult:
    if history is None or history.empty or len(history) < 3:
        return CandleResult(pattern="None", score=0.0)

    candles = history.tail(3).reset_index(drop=True)
    prev2 = candles.iloc[0]
    prev1 = candles.iloc[1]
    curr = candles.iloc[2]

    checks = [
        _bullish_engulfing(prev1, curr),
        _hammer(curr),
        _morning_star(prev2, prev1, curr),
        _bullish_harami(prev1, curr),
        _piercing_line(prev1, curr),
    ]

    for pattern, score, matched in checks:
        if matched:
            return CandleResult(pattern=pattern, score=min(15.0, score))

    return CandleResult(pattern="None", score=0.0)


def _body(candle: pd.Series) -> float:
    return abs(float(candle["close"]) - float(candle["open"]))


def _bullish_engulfing(prev: pd.Series, curr: pd.Series) -> tuple[str, float, bool]:
    matched = (
        float(prev["close"]) < float(prev["open"])
        and float(curr["close"]) > float(curr["open"])
        and float(curr["open"]) <= float(prev["close"])
        and float(curr["close"]) >= float(prev["open"])
    )
    return ("Bullish Engulfing", 15.0, matched)


def _hammer(curr: pd.Series) -> tuple[str, float, bool]:
    body = _body(curr)
    high = float(curr["high"])
    low = float(curr["low"])
    open_ = float(curr["open"])
    close = float(curr["close"])
    upper = high - max(open_, close)
    lower = min(open_, close) - low
    matched = body > 0 and lower >= (2 * body) and upper < body
    return ("Hammer", 12.0, matched)


def _morning_star(prev2: pd.Series, prev1: pd.Series, curr: pd.Series) -> tuple[str, float, bool]:
    mid_prev2 = (float(prev2["open"]) + float(prev2["close"])) / 2
    matched = (
        float(prev2["close"]) < float(prev2["open"])
        and _body(prev1) <= (_body(prev2) * 0.5)
        and float(curr["close"]) > float(curr["open"])
        and float(curr["close"]) > mid_prev2
    )
    return ("Morning Star", 15.0, matched)


def _bullish_harami(prev: pd.Series, curr: pd.Series) -> tuple[str, float, bool]:
    matched = (
        float(prev["close"]) < float(prev["open"])
        and float(curr["close"]) > float(curr["open"])
        and float(curr["open"]) >= min(float(prev["open"]), float(prev["close"]))
        and float(curr["close"]) <= max(float(prev["open"]), float(prev["close"]))
    )
    return ("Bullish Harami", 8.0, matched)


def _piercing_line(prev: pd.Series, curr: pd.Series) -> tuple[str, float, bool]:
    midpoint = (float(prev["open"]) + float(prev["close"])) / 2
    matched = (
        float(prev["close"]) < float(prev["open"])
        and float(curr["open"]) < float(prev["close"])
        and float(curr["close"]) > midpoint
        and float(curr["close"]) < float(prev["open"])
    )
    return ("Piercing Line", 10.0, matched)
