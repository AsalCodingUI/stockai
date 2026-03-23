"""Historical signal backtesting engine for probabilistic forecasts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import pytz
import yfinance as yf

from stockai.data.cache import get_cache, memory_cache_get, memory_cache_set
from stockai.data.sources.yahoo import YahooFinanceSource

TIMEZONE = pytz.timezone("Asia/Jakarta")


class HistoricalBacktester:
    """Build historical signal dataset and compute conditional win rates."""

    CACHE_TTL_SECONDS = 3600

    def __init__(self) -> None:
        self.cache = get_cache()
        self.yahoo = YahooFinanceSource()

    def build_signal_history(self, symbol: str, years: int = 3) -> pd.DataFrame:
        clean_symbol = symbol.upper().replace(".JK", "").strip()
        cache_key = f"ml_backtest_history:{clean_symbol}:{years}"

        memory_cached = memory_cache_get(cache_key)
        if isinstance(memory_cached, pd.DataFrame):
            return memory_cached

        persistent_cached = self.cache.get(cache_key)
        if isinstance(persistent_cached, list) and persistent_cached:
            history_df = pd.DataFrame(persistent_cached)
            memory_cache_set(cache_key, history_df, ttl=self.CACHE_TTL_SECONDS)
            return history_df

        period = f"{max(1, years)}y"
        df = self.yahoo.get_price_history(clean_symbol, period=period)
        if df is None or df.empty or len(df) < 60:
            return pd.DataFrame()

        signal_df = df[["date", "open", "high", "low", "close", "volume"]].copy()
        signal_df = signal_df.sort_values("date").reset_index(drop=True)

        signal_df["rsi"] = self._calculate_rsi(signal_df["close"], period=14)
        macd_line, macd_signal = self._calculate_macd(signal_df["close"])
        signal_df["macd_line"] = macd_line
        signal_df["macd_signal"] = macd_signal
        signal_df["volume_ratio"] = signal_df["volume"] / signal_df["volume"].rolling(20).mean()
        signal_df["adx"] = self._calculate_adx(signal_df, period=14)

        support_20d = signal_df["low"].rolling(20).min()
        signal_df["near_support"] = (signal_df["close"] <= (support_20d * 1.10)).astype(int)

        signal_df["signal_score"] = (
            (signal_df["rsi"].fillna(50) / 100.0) * 40
            + (signal_df["macd_line"] > signal_df["macd_signal"]).astype(int) * 30
            + np.clip(signal_df["volume_ratio"].fillna(1.0), 0, 3) / 3 * 30
        )

        signal_df["gate_approx"] = (
            (signal_df["rsi"].between(40, 70)).astype(int)
            + (signal_df["macd_line"] > signal_df["macd_signal"]).astype(int)
            + (signal_df["volume_ratio"] >= 1.2).astype(int)
            + (signal_df["adx"] >= 20).astype(int)
            + (signal_df["near_support"] == 1).astype(int)
        )

        forward_close_14d = signal_df["close"].shift(-14)
        signal_df["return_14d"] = (forward_close_14d / signal_df["close"]) - 1.0
        signal_df["outcome_5pct_14d"] = (forward_close_14d >= signal_df["close"] * 1.05).astype(int)
        signal_df["outcome_10pct_14d"] = (forward_close_14d >= signal_df["close"] * 1.10).astype(int)

        result = signal_df[
            [
                "date",
                "close",
                "signal_score",
                "gate_approx",
                "volume_ratio",
                "adx",
                "near_support",
                "return_14d",
                "outcome_5pct_14d",
                "outcome_10pct_14d",
            ]
        ].dropna().reset_index(drop=True)

        if not result.empty:
            self.cache.set(cache_key, result.to_dict(orient="records"), ttl=self.CACHE_TTL_SECONDS)
            memory_cache_set(cache_key, result, ttl=self.CACHE_TTL_SECONDS)

        return result

    def calculate_win_rate(self, symbol: str, current_signals: dict[str, Any]) -> dict[str, Any]:
        history = self.build_signal_history(symbol)
        clean_symbol = symbol.upper().replace(".JK", "").strip()
        if history.empty:
            return self._empty_result(clean_symbol)

        latest = history.iloc[-1]
        volume_ratio_now = float(current_signals.get("volume_ratio", latest["volume_ratio"]) or 1.0)
        adx_now = float(current_signals.get("adx", latest["adx"]) or 20.0)
        near_support_now = bool(current_signals.get("near_support", bool(latest["near_support"])))

        similar = history[
            (history["volume_ratio"].between(volume_ratio_now - 1.0, volume_ratio_now + 1.0))
            & (history["adx"].between(adx_now - 10.0, adx_now + 10.0))
            & (history["near_support"].astype(bool) == near_support_now)
        ]

        if similar.empty:
            return self._empty_result(clean_symbol)

        similar_cases = len(similar)
        win_rate_5pct = float(similar["outcome_5pct_14d"].mean())
        win_rate_10pct = float(similar["outcome_10pct_14d"].mean())
        avg_return_14d = float(similar["return_14d"].mean())
        best_case = float(similar["return_14d"].max())
        worst_case = float(similar["return_14d"].min())

        if similar_cases >= 20:
            confidence = "HIGH"
        elif similar_cases >= 10:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        if win_rate_5pct >= 0.60:
            recommendation = "FAVORABLE"
        elif win_rate_5pct >= 0.40:
            recommendation = "NEUTRAL"
        else:
            recommendation = "UNFAVORABLE"

        return {
            "symbol": clean_symbol,
            "similar_cases": similar_cases,
            "win_rate_5pct": round(win_rate_5pct, 4),
            "win_rate_10pct": round(win_rate_10pct, 4),
            "avg_return_14d": round(avg_return_14d, 4),
            "best_case": round(best_case, 4),
            "worst_case": round(worst_case, 4),
            "confidence": confidence,
            "recommendation": recommendation,
        }

    def get_market_context(self) -> dict[str, Any]:
        cache_key = "ml_market_context:^JKSE"
        memory_cached = memory_cache_get(cache_key)
        if isinstance(memory_cached, dict):
            return memory_cached

        persistent_cached = self.cache.get(cache_key)
        if isinstance(persistent_cached, dict):
            memory_cache_set(cache_key, persistent_cached, ttl=self.CACHE_TTL_SECONDS)
            return persistent_cached

        try:
            df = yf.Ticker("^JKSE").history(period="1y", interval="1d")
            if df is None or df.empty:
                raise ValueError("No IHSG data")
            df = df.reset_index()
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]
            close = df["close"]
            rsi = float(self._calculate_rsi(close, 14).iloc[-1])
            adx = float(self._calculate_adx(df[["high", "low", "close"]], 14).iloc[-1])
            ma20 = float(close.rolling(20).mean().iloc[-1])
            ma50 = float(close.rolling(50).mean().iloc[-1])

            if ma20 > ma50 and rsi >= 55:
                trend = "BULLISH"
                regime = "RISK_ON"
                note = "Market uptrend, historical win rate cenderung meningkat."
            elif ma20 < ma50 and rsi <= 45:
                trend = "BEARISH"
                regime = "RISK_OFF"
                note = "Market sedang downtrend, win rate historis turun ~15%."
            else:
                trend = "SIDEWAYS"
                regime = "NEUTRAL"
                note = "Market cenderung sideways, seleksi sinyal lebih ketat."
        except Exception:
            trend = "SIDEWAYS"
            regime = "NEUTRAL"
            adx = 20.0
            rsi = 50.0
            note = "Market context fallback: data IHSG tidak lengkap."

        result = {
            "ihsg_trend": trend,
            "ihsg_adx": round(adx, 2),
            "ihsg_rsi": round(rsi, 2),
            "market_regime": regime,
            "note": note,
            "as_of": datetime.now(TIMEZONE).isoformat(),
        }
        self.cache.set(cache_key, result, ttl=self.CACHE_TTL_SECONDS)
        memory_cache_set(cache_key, result, ttl=self.CACHE_TTL_SECONDS)
        return result

    def _empty_result(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "similar_cases": 0,
            "win_rate_5pct": 0.0,
            "win_rate_10pct": 0.0,
            "avg_return_14d": 0.0,
            "best_case": 0.0,
            "worst_case": 0.0,
            "confidence": "LOW",
            "recommendation": "NEUTRAL",
        }

    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _calculate_macd(self, close: pd.Series) -> tuple[pd.Series, pd.Series]:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd, signal

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()

        plus_di = 100 * (plus_dm.rolling(period).mean() / atr.replace(0, np.nan))
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr.replace(0, np.nan))
        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
        adx = dx.rolling(period).mean()
        return adx.fillna(20)
