"""Automatic chart pattern recognition using pandas/numpy heuristics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from stockai.data.cache import get_cache, memory_cache_get, memory_cache_set
from stockai.data.sources.yahoo import YahooFinanceSource
from stockai.core.ml.backtester import HistoricalBacktester


class PatternRecognizer:
    """Detect bullish and bearish chart patterns from recent OHLCV."""

    CACHE_TTL_SECONDS = 3600

    def __init__(self) -> None:
        self.cache = get_cache()
        self.yahoo = YahooFinanceSource()
        self.backtester = HistoricalBacktester()
        self._cache: dict[str, dict[str, Any]] = {}

    def detect(self, symbol: str) -> dict[str, Any]:
        clean_symbol = symbol.upper().replace(".JK", "").strip()
        if clean_symbol in self._cache:
            return self._cache[clean_symbol]

        cache_key = f"pattern_recognition:{clean_symbol}"
        memory_cached = memory_cache_get(cache_key)
        if isinstance(memory_cached, dict):
            self._cache[clean_symbol] = memory_cached
            return memory_cached

        persistent_cached = self.cache.get(cache_key)
        if isinstance(persistent_cached, dict):
            memory_cache_set(cache_key, persistent_cached, ttl=self.CACHE_TTL_SECONDS)
            self._cache[clean_symbol] = persistent_cached
            return persistent_cached

        df = self.yahoo.get_price_history(clean_symbol, period="1y")
        if df is None or df.empty or len(df) < 60:
            result = self._empty_result(clean_symbol)
            self._store(cache_key, clean_symbol, result)
            return result

        df = df.sort_values("date").reset_index(drop=True)
        close = df["close"].astype(float)
        low = df["low"].astype(float)
        high = df["high"].astype(float)
        open_ = df["open"].astype(float)
        volume = df["volume"].astype(float)

        patterns: list[dict[str, Any]] = []

        patterns.extend(self._detect_double_bottom(clean_symbol, close, low, high))
        patterns.extend(self._detect_double_top(clean_symbol, close, low, high))
        patterns.extend(self._detect_head_shoulders(clean_symbol, close, high, low))
        patterns.extend(self._detect_flag_patterns(clean_symbol, close, volume, bullish=True))
        patterns.extend(self._detect_flag_patterns(clean_symbol, close, volume, bullish=False))
        patterns.extend(self._detect_cup_handle(clean_symbol, close, volume))
        patterns.extend(self._detect_ma_cross(clean_symbol, close, bullish=True))
        patterns.extend(self._detect_ma_cross(clean_symbol, close, bullish=False))
        patterns.extend(self._detect_star_pattern(clean_symbol, open_, close, bullish=True))
        patterns.extend(self._detect_star_pattern(clean_symbol, open_, close, bullish=False))
        patterns.extend(self._detect_trend_structure(clean_symbol, low, high, bullish=True))
        patterns.extend(self._detect_trend_structure(clean_symbol, low, high, bullish=False))

        patterns = sorted(patterns, key=lambda x: x["confidence"], reverse=True)
        dominant = patterns[0]["name"] if patterns else None

        bullish_count = sum(1 for p in patterns if p["type"] == "BULLISH")
        bearish_count = sum(1 for p in patterns if p["type"] == "BEARISH")
        if bullish_count > bearish_count:
            bias = "BULLISH"
        elif bearish_count > bullish_count:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        result = {
            "symbol": clean_symbol,
            "patterns_detected": patterns,
            "dominant_pattern": dominant,
            "overall_bias": bias,
            "pattern_count": len(patterns),
        }
        self._store(cache_key, clean_symbol, result)
        return result

    def _store(self, cache_key: str, symbol: str, result: dict[str, Any]) -> None:
        self.cache.set(cache_key, result, ttl=self.CACHE_TTL_SECONDS)
        memory_cache_set(cache_key, result, ttl=self.CACHE_TTL_SECONDS)
        self._cache[symbol] = result

    def _empty_result(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "patterns_detected": [],
            "dominant_pattern": None,
            "overall_bias": "NEUTRAL",
            "pattern_count": 0,
        }

    def _base_stats(self, symbol: str, current: dict[str, Any]) -> tuple[float, float]:
        wr = self.backtester.calculate_win_rate(symbol, current)
        return float(wr.get("win_rate_5pct", 0.5)), float(wr.get("avg_return_14d", 0.0))

    def _pattern(
        self,
        symbol: str,
        name: str,
        pattern_type: str,
        strength: str,
        confidence: float,
        description: str,
        target_price: float,
        current_signals: dict[str, Any],
    ) -> dict[str, Any]:
        win_rate, avg_ret = self._base_stats(symbol, current_signals)
        return {
            "name": name,
            "type": pattern_type,
            "strength": strength,
            "confidence": round(float(confidence), 2),
            "description": description,
            "historical_win_rate": round(float(win_rate), 2),
            "avg_return": round(float(avg_ret), 3),
            "target_price": round(float(target_price), 0),
        }

    def _local_minima(self, series: pd.Series) -> np.ndarray:
        arr = series.values
        if len(arr) < 3:
            return np.array([], dtype=int)
        idx = np.where((arr[1:-1] <= arr[:-2]) & (arr[1:-1] <= arr[2:]))[0] + 1
        return idx

    def _local_maxima(self, series: pd.Series) -> np.ndarray:
        arr = series.values
        if len(arr) < 3:
            return np.array([], dtype=int)
        idx = np.where((arr[1:-1] >= arr[:-2]) & (arr[1:-1] >= arr[2:]))[0] + 1
        return idx

    def _detect_double_bottom(self, symbol: str, close: pd.Series, low: pd.Series, high: pd.Series) -> list[dict[str, Any]]:
        window = min(60, len(close))
        recent_low = low.tail(window).reset_index(drop=True)
        recent_close = close.tail(window).reset_index(drop=True)
        mins = self._local_minima(recent_low)
        if len(mins) < 2:
            return []
        i1, i2 = mins[-2], mins[-1]
        l1, l2 = float(recent_low.iloc[i1]), float(recent_low.iloc[i2])
        if l1 == 0:
            return []
        if abs(l2 - l1) / l1 > 0.03:
            return []
        neckline = float(recent_close.iloc[i1:i2 + 1].max()) if i2 > i1 else float(recent_close.iloc[-1])
        current_price = float(recent_close.iloc[-1])
        if current_price <= neckline:
            return []
        confidence = min(0.9, 0.72 + (current_price - neckline) / max(neckline, 1) * 2)
        return [
            self._pattern(
                symbol,
                "DOUBLE_BOTTOM",
                "BULLISH",
                "HIGH" if confidence >= 0.8 else "MEDIUM",
                confidence,
                f"Dua lembah di level {l1:,.0f} terbentuk dalam {window} hari",
                neckline + (neckline - min(l1, l2)),
                {"near_support": True},
            )
        ]

    def _detect_double_top(self, symbol: str, close: pd.Series, low: pd.Series, high: pd.Series) -> list[dict[str, Any]]:
        window = min(60, len(close))
        recent_high = high.tail(window).reset_index(drop=True)
        recent_close = close.tail(window).reset_index(drop=True)
        maxs = self._local_maxima(recent_high)
        if len(maxs) < 2:
            return []
        i1, i2 = maxs[-2], maxs[-1]
        h1, h2 = float(recent_high.iloc[i1]), float(recent_high.iloc[i2])
        if h1 == 0:
            return []
        if abs(h2 - h1) / h1 > 0.03:
            return []
        neckline = float(recent_close.iloc[i1:i2 + 1].min()) if i2 > i1 else float(recent_close.iloc[-1])
        current_price = float(recent_close.iloc[-1])
        if current_price >= neckline:
            return []
        confidence = min(0.88, 0.7 + (neckline - current_price) / max(neckline, 1) * 2)
        return [
            self._pattern(
                symbol,
                "DOUBLE_TOP",
                "BEARISH",
                "HIGH" if confidence >= 0.8 else "MEDIUM",
                confidence,
                f"Dua puncak di level {h1:,.0f} terbentuk dalam {window} hari",
                max(0.0, neckline - (max(h1, h2) - neckline)),
                {"near_support": False},
            )
        ]

    def _detect_head_shoulders(self, symbol: str, close: pd.Series, high: pd.Series, low: pd.Series) -> list[dict[str, Any]]:
        window = min(80, len(close))
        h = high.tail(window).reset_index(drop=True)
        c = close.tail(window).reset_index(drop=True)
        peaks = self._local_maxima(h)
        if len(peaks) < 3:
            return []
        p1, p2, p3 = peaks[-3], peaks[-2], peaks[-1]
        left, head, right = float(h.iloc[p1]), float(h.iloc[p2]), float(h.iloc[p3])
        if not (head > left and head > right):
            return []
        if left == 0 or abs(right - left) / left > 0.05:
            return []
        neckline = float(c.iloc[p1:p3 + 1].min())
        if float(c.iloc[-1]) >= neckline:
            return []
        confidence = 0.84
        return [
            self._pattern(
                symbol,
                "HEAD_AND_SHOULDERS",
                "BEARISH",
                "HIGH",
                confidence,
                "Head and Shoulders breakdown terkonfirmasi di bawah neckline",
                max(0.0, neckline - (head - neckline)),
                {"near_support": False},
            )
        ]

    def _detect_flag_patterns(self, symbol: str, close: pd.Series, volume: pd.Series, bullish: bool) -> list[dict[str, Any]]:
        if len(close) < 30:
            return []
        recent = close.tail(20).reset_index(drop=True)
        vol = volume.tail(20).reset_index(drop=True)
        flagpole_ret = (recent.iloc[9] / recent.iloc[0]) - 1 if recent.iloc[0] else 0
        consolidation = recent.iloc[10:18]
        if consolidation.empty:
            return []
        cons_ret = (consolidation.iloc[-1] / consolidation.iloc[0]) - 1 if consolidation.iloc[0] else 0
        vol_flagpole = float(vol.iloc[:10].mean())
        vol_consolidation = float(vol.iloc[10:18].mean())
        breakout_up = float(recent.iloc[-1]) > float(consolidation.max())
        breakout_down = float(recent.iloc[-1]) < float(consolidation.min())

        if bullish:
            if not (flagpole_ret > 0.08 and cons_ret > -0.03 and vol_consolidation < vol_flagpole and breakout_up):
                return []
            return [
                self._pattern(
                    symbol,
                    "BULL_FLAG",
                    "BULLISH",
                    "MEDIUM",
                    0.74,
                    "Flagpole naik diikuti konsolidasi sehat dan breakout ke atas",
                    float(recent.iloc[-1]) * 1.08,
                    {"volume_ratio": 2.0},
                )
            ]

        if not (flagpole_ret < -0.08 and cons_ret < 0.03 and vol_consolidation < vol_flagpole and breakout_down):
            return []
        return [
            self._pattern(
                symbol,
                "BEAR_FLAG",
                "BEARISH",
                "MEDIUM",
                0.74,
                "Penurunan tajam diikuti konsolidasi dan breakdown lanjutan",
                float(recent.iloc[-1]) * 0.92,
                {"volume_ratio": 2.0},
            )
        ]

    def _detect_cup_handle(self, symbol: str, close: pd.Series, volume: pd.Series) -> list[dict[str, Any]]:
        window = min(90, len(close))
        c = close.tail(window).reset_index(drop=True)
        v = volume.tail(window).reset_index(drop=True)
        if len(c) < 40:
            return []
        left = float(c.iloc[5:20].max())
        bottom = float(c.iloc[20:50].min())
        right = float(c.iloc[50:75].max())
        if left <= 0 or right <= 0:
            return []
        if bottom > min(left, right) * 0.93:
            return []
        handle = c.iloc[-15:-1]
        if handle.empty:
            return []
        handle_drawdown = (float(handle.min()) / float(handle.max())) - 1 if float(handle.max()) else 0
        breakout = float(c.iloc[-1]) > float(handle.max())
        vol_breakout = float(v.iloc[-1]) > float(v.iloc[-20:-1].mean())
        if handle_drawdown < -0.05 or not (breakout and vol_breakout):
            return []
        return [
            self._pattern(
                symbol,
                "CUP_AND_HANDLE",
                "BULLISH",
                "MEDIUM",
                0.76,
                "Pola cup and handle dengan breakout volume",
                float(c.iloc[-1]) * 1.10,
                {"volume_ratio": 2.0},
            )
        ]

    def _detect_ma_cross(self, symbol: str, close: pd.Series, bullish: bool) -> list[dict[str, Any]]:
        if len(close) < 220:
            return []
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        diff = ma50 - ma200
        recent = diff.tail(6).dropna()
        if len(recent) < 2:
            return []
        if bullish:
            crossed = (recent.iloc[-2] <= 0) and (recent.iloc[-1] > 0)
            trend_ok = ma50.diff().iloc[-1] > 0 and ma200.diff().iloc[-1] > 0
            if not (crossed and trend_ok):
                return []
            return [
                self._pattern(
                    symbol,
                    "GOLDEN_CROSS",
                    "BULLISH",
                    "HIGH",
                    0.82,
                    "MA50 menembus MA200 ke atas dalam 5 hari terakhir",
                    float(close.iloc[-1]) * 1.12,
                    {"adx": 25},
                )
            ]
        crossed = (recent.iloc[-2] >= 0) and (recent.iloc[-1] < 0)
        trend_ok = ma50.diff().iloc[-1] < 0 and ma200.diff().iloc[-1] < 0
        if not (crossed and trend_ok):
            return []
        return [
            self._pattern(
                symbol,
                "DEATH_CROSS",
                "BEARISH",
                "HIGH",
                0.82,
                "MA50 menembus MA200 ke bawah dalam 5 hari terakhir",
                float(close.iloc[-1]) * 0.9,
                {"adx": 25},
            )
        ]

    def _detect_star_pattern(self, symbol: str, open_: pd.Series, close: pd.Series, bullish: bool) -> list[dict[str, Any]]:
        if len(close) < 3:
            return []
        o1, o2, o3 = float(open_.iloc[-3]), float(open_.iloc[-2]), float(open_.iloc[-1])
        c1, c2, c3 = float(close.iloc[-3]), float(close.iloc[-2]), float(close.iloc[-1])
        body1 = abs(c1 - o1)
        body2 = abs(c2 - o2)
        body3 = abs(c3 - o3)
        midpoint1 = (o1 + c1) / 2
        if bullish:
            cond = (c1 < o1) and (body2 < body1 * 0.5) and (c3 > o3) and (c3 > midpoint1)
            if not cond:
                return []
            return [
                self._pattern(
                    symbol,
                    "MORNING_STAR",
                    "BULLISH",
                    "MEDIUM",
                    0.71,
                    "Morning Star 3-candle bullish reversal terdeteksi",
                    c3 * 1.07,
                    {"near_support": True},
                )
            ]
        cond = (c1 > o1) and (body2 < body1 * 0.5) and (c3 < o3) and (c3 < midpoint1)
        if not cond:
            return []
        return [
            self._pattern(
                symbol,
                "EVENING_STAR",
                "BEARISH",
                "MEDIUM",
                0.71,
                "Evening Star 3-candle bearish reversal terdeteksi",
                c3 * 0.93,
                {"near_support": False},
            )
        ]

    def _detect_trend_structure(self, symbol: str, low: pd.Series, high: pd.Series, bullish: bool) -> list[dict[str, Any]]:
        window = min(30, len(low))
        lows = low.tail(window).reset_index(drop=True)
        highs = high.tail(window).reset_index(drop=True)
        if bullish:
            mins = self._local_minima(lows)
            if len(mins) < 3:
                return []
            a, b, c = [float(lows.iloc[i]) for i in mins[-3:]]
            if not (a < b < c):
                return []
            return [
                self._pattern(
                    symbol,
                    "HIGHER_LOWS",
                    "BULLISH",
                    "MEDIUM",
                    0.69,
                    "Terdapat 3 higher lows beruntun dalam 30 hari",
                    float(highs.iloc[-1]) * 1.06,
                    {"near_support": True},
                )
            ]
        maxs = self._local_maxima(highs)
        if len(maxs) < 3:
            return []
        a, b, c = [float(highs.iloc[i]) for i in maxs[-3:]]
        if not (a > b > c):
            return []
        return [
            self._pattern(
                symbol,
                "LOWER_HIGHS",
                "BEARISH",
                "MEDIUM",
                0.69,
                "Terdapat 3 lower highs beruntun dalam 30 hari",
                float(low.iloc[-1]) * 0.94,
                {"near_support": False},
            )
        ]
