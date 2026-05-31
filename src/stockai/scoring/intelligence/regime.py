"""Market regime detection utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

from stockai.data.sources.yahoo import YahooFinanceSource

_CACHE_TTL = timedelta(hours=4)
_CACHE: dict[str, object] = {"expires_at": None, "result": None}


@dataclass
class RegimeResult:
    """Market regime classification for IHSG."""

    regime: str
    close: float
    ema20: float
    ema50: float


def get_market_regime(yahoo: YahooFinanceSource | None = None) -> RegimeResult:
    """Return cached IHSG regime classification."""
    now = datetime.now(timezone.utc)
    expires_at = _CACHE.get("expires_at")
    cached = _CACHE.get("result")
    if isinstance(expires_at, datetime) and expires_at > now and isinstance(cached, RegimeResult):
        return cached

    yahoo = yahoo or YahooFinanceSource()
    history = yahoo.get_price_history("^JKSE", period="3mo")
    result = _classify_market_regime(history)
    _CACHE["expires_at"] = now + _CACHE_TTL
    _CACHE["result"] = result
    return result


def _classify_market_regime(history: pd.DataFrame) -> RegimeResult:
    if history is None or history.empty or len(history) < 50:
        return RegimeResult(regime="SIDEWAYS", close=0.0, ema20=0.0, ema50=0.0)

    closes = history["close"].astype(float)
    ema20 = closes.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = closes.ewm(span=50, adjust=False).mean().iloc[-1]
    close = float(closes.iloc[-1])

    if close > ema20 and ema20 > ema50:
        regime = "BULLISH"
    elif close < ema20 and ema20 < ema50:
        regime = "BEARISH"
    else:
        regime = "SIDEWAYS"

    return RegimeResult(
        regime=regime,
        close=close,
        ema20=float(ema20),
        ema50=float(ema50),
    )
