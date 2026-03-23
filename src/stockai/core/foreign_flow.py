"""Smart-money proxy monitor based on Yahoo Finance volume-price action."""

from __future__ import annotations

import logging
from typing import Any

from stockai.data.cache import get_cache, memory_cache_get, memory_cache_set
from stockai.data.sources.yahoo import YahooFinanceSource

logger = logging.getLogger(__name__)


class ForeignFlowMonitor:
    """Volume-price proxy for foreign flow style accumulation detection."""

    CACHE_TTL_SECONDS = 3600
    LOOKBACK_DAYS = 20
    SIGNAL_WINDOW_DAYS = 5
    _proxy_notice_logged = False

    def __init__(self) -> None:
        self.cache = get_cache()
        self.yahoo = YahooFinanceSource()
        self._signal_cache: dict[tuple[str, int], dict[str, Any]] = {}

    def get_foreign_flow(self, date: str | None = None) -> dict[str, dict[str, float]]:
        """Return proxy-derived smart money data.

        The date argument is ignored and kept only for backward compatibility.
        """
        self._log_proxy_notice_once()
        return {}

    def get_flow_signal(self, symbol: str, days: int = 5) -> dict[str, Any]:
        """Analyze smart-money proxy from recent OHLCV volume-price action."""
        self._log_proxy_notice_once()

        clean_symbol = symbol.upper().replace(".JK", "").strip()
        window_days = max(1, min(days, self.SIGNAL_WINDOW_DAYS))
        cache_key = (clean_symbol, window_days)
        if cache_key in self._signal_cache:
            return self._signal_cache[cache_key]

        history = self._get_cached_history(clean_symbol)
        if history is None or history.empty or len(history) < self.LOOKBACK_DAYS:
            signal = self._neutral_signal(source="volume_proxy")
            self._signal_cache[cache_key] = signal
            return signal

        recent = history.tail(self.LOOKBACK_DAYS).copy()
        average_volume = float(recent["volume"].mean()) if "volume" in recent else 0.0
        if average_volume <= 0:
            signal = self._neutral_signal(source="volume_proxy")
            self._signal_cache[cache_key] = signal
            return signal

        recent["bullish_candle"] = recent["close"] > recent["open"]
        recent["bearish_candle"] = recent["close"] < recent["open"]
        recent["volume_spike"] = recent["volume"] > (average_volume * 2.0)
        recent["smart_day"] = recent["bullish_candle"] & recent["volume_spike"]
        recent["distribution_day"] = recent["bearish_candle"] & recent["volume_spike"]

        signal_window = recent.tail(window_days)
        smart_days = signal_window["smart_day"].tolist()[::-1]
        distribution_days = signal_window["distribution_day"].tolist()[::-1]

        consecutive_smart_days = 0
        for is_smart_day in smart_days:
            if is_smart_day:
                consecutive_smart_days += 1
            else:
                break

        distribution_spike_days = sum(1 for is_distribution_day in distribution_days if is_distribution_day)

        if consecutive_smart_days >= 3:
            signal = self._build_signal("ACCUMULATION", "STRONG", consecutive_smart_days)
        elif consecutive_smart_days == 2:
            signal = self._build_signal("ACCUMULATION", "MODERATE", consecutive_smart_days)
        elif consecutive_smart_days == 1:
            signal = self._build_signal("ACCUMULATION", "WEAK", consecutive_smart_days)
        elif distribution_spike_days >= 2:
            signal = self._build_signal("DISTRIBUTION", "MODERATE", 0)
        else:
            signal = self._neutral_signal(source="volume_proxy")

        self._signal_cache[cache_key] = signal
        return signal

    def get_top_accumulated(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return top stocks by proxy accumulation strength."""
        self._log_proxy_notice_once()

        try:
            from stockai.data.listings import ALL_IDX_STOCKS
            universe = [stock["symbol"] for stock in ALL_IDX_STOCKS]
        except ImportError:
            universe = []

        ranked: list[dict[str, Any]] = []
        for symbol in universe:
            signal = self.get_flow_signal(symbol, days=self.SIGNAL_WINDOW_DAYS)
            if signal["signal"] != "ACCUMULATION":
                continue

            strength_rank = {"STRONG": 3, "MODERATE": 2, "WEAK": 1}.get(
                signal["strength"],
                0,
            )
            ranked.append(
                {
                    "symbol": symbol,
                    "signal": signal["signal"],
                    "strength": signal["strength"],
                    "consecutive_buy_days": signal["consecutive_buy_days"],
                    "total_net_5d": 0.0,
                    "source": "volume_proxy",
                    "_strength_rank": strength_rank,
                }
            )

        ranked.sort(
            key=lambda item: (
                item["_strength_rank"],
                item["consecutive_buy_days"],
                item["symbol"],
            ),
            reverse=True,
        )

        return [
            {key: value for key, value in item.items() if key != "_strength_rank"}
            for item in ranked[:limit]
        ]

    def _get_cached_history(self, symbol: str):
        cache_key = f"foreign_flow_proxy_history:{symbol}"
        cached_history = memory_cache_get(cache_key)
        if cached_history is not None:
            return cached_history

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

        serializable_history = history.to_dict(orient="records")
        self.cache.set(cache_key, serializable_history, ttl=self.CACHE_TTL_SECONDS)
        memory_cache_set(cache_key, history, ttl=self.CACHE_TTL_SECONDS)
        return history

    def _build_signal(
        self,
        signal: str,
        strength: str,
        consecutive_buy_days: int,
    ) -> dict[str, Any]:
        return {
            "signal": signal,
            "strength": strength,
            "consecutive_buy_days": consecutive_buy_days,
            "total_net_5d": 0.0,
            "latest_net": 0.0,
            "source": "volume_proxy",
        }

    def _neutral_signal(self, source: str) -> dict[str, Any]:
        return {
            "signal": "NEUTRAL",
            "strength": "WEAK",
            "consecutive_buy_days": 0,
            "total_net_5d": 0.0,
            "latest_net": 0.0,
            "source": source,
        }

    def _log_proxy_notice_once(self) -> None:
        if self.__class__._proxy_notice_logged:
            return
        logger.warning("⚠️  Foreign flow: using volume-price proxy")
        self.__class__._proxy_notice_logged = True
