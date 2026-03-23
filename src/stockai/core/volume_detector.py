"""Unusual volume detector for smart-money accumulation proxy."""

from __future__ import annotations

from typing import Any

from stockai.data.cache import get_cache, memory_cache_get, memory_cache_set
from stockai.data.sources.yahoo import YahooFinanceSource


class UnusualVolumeDetector:
    """Detect abnormal volume spikes from recent OHLCV data."""

    CACHE_TTL_SECONDS = 3600
    LOOKBACK_DAYS = 21  # 20 days avg (exclude today) + current day

    def __init__(self) -> None:
        self.cache = get_cache()
        self.yahoo = YahooFinanceSource()
        self._result_cache: dict[str, dict[str, Any]] = {}

    def detect(self, symbol: str, history=None) -> dict[str, Any]:
        clean_symbol = symbol.upper().replace(".JK", "").strip()
        if clean_symbol in self._result_cache:
            return self._result_cache[clean_symbol]

        if history is None or history.empty:
            history = self._get_cached_history(clean_symbol)

        result = self._normal_result(clean_symbol)
        if history is None or history.empty or len(history) < 2:
            self._result_cache[clean_symbol] = result
            return result

        recent = history.tail(self.LOOKBACK_DAYS).copy()
        if len(recent) < 2:
            self._result_cache[clean_symbol] = result
            return result

        today = recent.iloc[-1]
        previous_days = recent.iloc[:-1]
        avg_volume_20d = float(previous_days["volume"].mean()) if len(previous_days) > 0 else 0.0
        volume_today = float(today.get("volume", 0.0) or 0.0)
        volume_ratio = (volume_today / avg_volume_20d) if avg_volume_20d > 0 else 0.0

        classification = self._classify(volume_ratio)
        price_action = self._price_action(today)
        bonus = self._bonus_from_classification(classification)

        result = {
            "symbol": clean_symbol,
            "volume_ratio": round(volume_ratio, 2),
            "classification": classification,
            "volume_today": volume_today,
            "avg_volume_20d": round(avg_volume_20d, 2),
            "price_action": price_action,
            "bonus": bonus,
            "show": classification != "NORMAL",
        }
        self._result_cache[clean_symbol] = result
        return result

    def _get_cached_history(self, symbol: str):
        cache_key = f"unusual_volume_history:{symbol}"
        memory_cached = memory_cache_get(cache_key)
        if memory_cached is not None:
            return memory_cached

        persistent_cached = self.cache.get(cache_key)
        if isinstance(persistent_cached, list) and persistent_cached:
            import pandas as pd

            history = pd.DataFrame(persistent_cached)
            memory_cache_set(cache_key, history, ttl=self.CACHE_TTL_SECONDS)
            return history

        history = self.yahoo.get_price_history(symbol, period="1mo")
        if history is None or history.empty:
            memory_cache_set(cache_key, None, ttl=300)
            return history

        self.cache.set(cache_key, history.to_dict(orient="records"), ttl=self.CACHE_TTL_SECONDS)
        memory_cache_set(cache_key, history, ttl=self.CACHE_TTL_SECONDS)
        return history

    def _classify(self, volume_ratio: float) -> str:
        if volume_ratio >= 5.0:
            return "EXTREME"
        if volume_ratio >= 3.0:
            return "HIGH"
        if volume_ratio >= 2.0:
            return "MODERATE"
        return "NORMAL"

    def _bonus_from_classification(self, classification: str) -> float:
        if classification == "EXTREME":
            return 15.0
        if classification == "HIGH":
            return 10.0
        if classification == "MODERATE":
            return 5.0
        return 0.0

    def _price_action(self, today_row: Any) -> str:
        close_price = float(today_row.get("close", 0.0) or 0.0)
        open_price = float(today_row.get("open", 0.0) or 0.0)
        if close_price > open_price:
            return "BULLISH"
        if close_price < open_price:
            return "BEARISH"
        return "NEUTRAL"

    def _normal_result(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "volume_ratio": 0.0,
            "classification": "NORMAL",
            "volume_today": 0.0,
            "avg_volume_20d": 0.0,
            "price_action": "NEUTRAL",
            "bonus": 0.0,
            "show": False,
        }
