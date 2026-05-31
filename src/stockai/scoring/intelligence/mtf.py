"""Multi-timeframe confirmation checks."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stockai.data.sources.yahoo import YahooFinanceSource


@dataclass
class MTFResult:
    """Alignment result across weekly, daily, and 4h charts."""

    aligned_count: int
    weekly_bullish: bool
    daily_bullish: bool
    intraday_bullish: bool
    score: float
    passed: bool


def evaluate_mtf_confirmation(
    symbol: str,
    yahoo: YahooFinanceSource | None = None,
) -> MTFResult:
    yahoo = yahoo or YahooFinanceSource()

    weekly = yahoo.get_price_history(symbol, period="6mo", interval="1wk")
    daily = yahoo.get_price_history(symbol, period="3mo", interval="1d")
    hourly = yahoo.get_price_history(symbol, period="60d", interval="1h")

    weekly_bullish = _is_weekly_bullish(weekly)
    daily_bullish = _is_daily_bullish(daily)
    intraday_bullish = _is_4h_bullish(hourly)
    aligned = sum([weekly_bullish, daily_bullish, intraday_bullish])

    if aligned >= 3:
        score = 25.0
    elif aligned == 2:
        score = 10.0
    else:
        score = 0.0

    return MTFResult(
        aligned_count=aligned,
        weekly_bullish=weekly_bullish,
        daily_bullish=daily_bullish,
        intraday_bullish=intraday_bullish,
        score=score,
        passed=aligned >= 2,
    )


def _is_weekly_bullish(df: pd.DataFrame) -> bool:
    if df is None or df.empty or len(df) < 20:
        return False
    closes = df["close"].astype(float)
    ema20 = closes.ewm(span=20, adjust=False).mean().iloc[-1]
    return float(closes.iloc[-1]) > float(ema20)


def _is_daily_bullish(df: pd.DataFrame) -> bool:
    if df is None or df.empty or len(df) < 35:
        return False
    closes = df["close"].astype(float)
    ema20 = closes.ewm(span=20, adjust=False).mean().iloc[-1]
    macd_hist = _macd_histogram(closes)
    return float(closes.iloc[-1]) > float(ema20) and macd_hist > 0


def _is_4h_bullish(df: pd.DataFrame) -> bool:
    if df is None or df.empty or len(df) < 40:
        return False
    frame = df.copy()
    time_col = "date" if "date" in frame.columns else "datetime"
    if time_col not in frame.columns:
        return False
    frame[time_col] = pd.to_datetime(frame[time_col])
    frame = frame.set_index(time_col).sort_index()
    resampled = frame.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    if len(resampled) < 20:
        return False
    closes = resampled["close"].astype(float)
    ema20 = closes.ewm(span=20, adjust=False).mean().iloc[-1]
    rsi = _rsi(closes)
    return 30 <= rsi <= 65 and float(closes.iloc[-1]) > float(ema20)


def _macd_histogram(closes: pd.Series) -> float:
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return float(hist.iloc[-1])


def _rsi(closes: pd.Series, period: int = 14) -> float:
    delta = closes.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    value = rsi.iloc[-1]
    if pd.isna(value):
        return 50.0
    return float(value)
