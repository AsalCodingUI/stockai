"""Smart Money Score Module.

Analyzes institutional accumulation/distribution patterns through
volume-price relationship analysis, OBV trends, and MFI signals.

Score range: -2.0 (heavy distribution) to 5.0 (strong accumulation)
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import ta
from ta.volatility import AverageTrueRange


@dataclass
class SmartMoneyResult:
    """Result of smart money analysis."""

    score: float  # -2.0 to 5.0
    accumulation_days: int
    distribution_days: int
    net_accumulation: int
    obv_trend: str  # BULLISH, NEUTRAL, BEARISH
    mfi: float
    mfi_signal: str  # OVERBOUGHT, NEUTRAL, OVERSOLD
    unusual_volume: str  # HIGH, NORMAL, LOW
    interpretation: str  # ACCUMULATION, NEUTRAL, DISTRIBUTION


def calculate_smart_money_score(
    df: pd.DataFrame,
    volume_threshold: float = 1.2,
    lookback: int = 20,
) -> SmartMoneyResult:
    """Calculate Smart Money Score from OHLCV data.

    Args:
        df: DataFrame with columns: open, high, low, close, volume
        volume_threshold: Multiplier for average volume to detect unusual activity
        lookback: Number of days for analysis

    Returns:
        SmartMoneyResult with score and component analysis
    """
    if len(df) < lookback:
        lookback = len(df)

    recent = df.tail(lookback).copy()

    # Calculate daily returns
    recent["return"] = recent["close"].pct_change()

    # Calculate average volume
    avg_volume = recent["volume"].mean()

    # Volume ratio (current vs average)
    recent["volume_ratio"] = recent["volume"] / avg_volume

    # Accumulation days: price up + volume > threshold
    accumulation_mask = (recent["return"] > 0) & (
        recent["volume_ratio"] > volume_threshold
    )
    accumulation_days = accumulation_mask.sum()

    # Distribution days: price down + volume > threshold
    distribution_mask = (recent["return"] < 0) & (
        recent["volume_ratio"] > volume_threshold
    )
    distribution_days = distribution_mask.sum()

    net_accumulation = accumulation_days - distribution_days

    # Calculate OBV using ta library
    obv_indicator = ta.volume.OnBalanceVolumeIndicator(recent["close"], recent["volume"])
    obv_values = obv_indicator.on_balance_volume()

    if obv_values is not None and len(obv_values) >= 5:
        obv_sma = obv_values.rolling(5).mean()
        obv_current = obv_values.iloc[-1]
        obv_sma_current = obv_sma.iloc[-1]

        if pd.notna(obv_current) and pd.notna(obv_sma_current):
            if obv_current > obv_sma_current * 1.05:
                obv_trend = "BULLISH"
            elif obv_current < obv_sma_current * 0.95:
                obv_trend = "BEARISH"
            else:
                obv_trend = "NEUTRAL"
        else:
            obv_trend = "NEUTRAL"
    else:
        obv_trend = "NEUTRAL"

    # Calculate MFI using ta library
    mfi_indicator = ta.volume.MFIIndicator(
        recent["high"], recent["low"], recent["close"], recent["volume"], window=14
    )
    mfi_series = mfi_indicator.money_flow_index()

    if mfi_series is not None and len(mfi_series) > 0:
        mfi_value = mfi_series.iloc[-1]
        if pd.isna(mfi_value):
            mfi_value = 50.0
    else:
        mfi_value = 50.0

    # MFI signal interpretation
    if mfi_value >= 80:
        mfi_signal = "OVERBOUGHT"
    elif mfi_value <= 20:
        mfi_signal = "OVERSOLD"
    else:
        mfi_signal = "NEUTRAL"

    # Detect unusual volume (latest bar)
    latest_volume_ratio = recent["volume_ratio"].iloc[-1] if len(recent) > 0 else 1.0
    if pd.isna(latest_volume_ratio):
        latest_volume_ratio = 1.0

    if latest_volume_ratio >= 2.0:
        unusual_volume = "HIGH"
    elif latest_volume_ratio <= 0.5:
        unusual_volume = "LOW"
    else:
        unusual_volume = "NORMAL"

    # Calculate composite score (-2.0 to 5.0)
    score = 0.0

    # Net accumulation contribution (-1 to 2)
    if net_accumulation > 3:
        score += 2.0
    elif net_accumulation > 0:
        score += 1.0
    elif net_accumulation < -3:
        score -= 1.0
    elif net_accumulation < 0:
        score -= 0.5

    # OBV trend contribution (-0.5 to 1.5)
    if obv_trend == "BULLISH":
        score += 1.5
    elif obv_trend == "BEARISH":
        score -= 0.5

    # MFI contribution (-0.5 to 1.0)
    if mfi_signal == "OVERSOLD":
        score += 1.0  # Buying opportunity
    elif mfi_signal == "OVERBOUGHT":
        score -= 0.5  # Caution

    # Unusual volume bonus (0 to 0.5)
    if unusual_volume == "HIGH" and net_accumulation > 0:
        score += 0.5

    # Clamp to valid range
    score = max(-2.0, min(5.0, score))

    # Determine interpretation
    if score >= 3.0:
        interpretation = "ACCUMULATION"
    elif score <= 0:
        interpretation = "DISTRIBUTION"
    else:
        interpretation = "NEUTRAL"

    return SmartMoneyResult(
        score=score,
        accumulation_days=int(accumulation_days),
        distribution_days=int(distribution_days),
        net_accumulation=int(net_accumulation),
        obv_trend=obv_trend,
        mfi=float(mfi_value),
        mfi_signal=mfi_signal,
        unusual_volume=unusual_volume,
        interpretation=interpretation,
    )


def calculate_smart_money_score_v2(
    df: pd.DataFrame,
    lookback: int = 20,
    mfi_window: int = 14,
    obv_window: int = 10,
    mfi_percentile_lookback: int = 60,
) -> SmartMoneyResult:
    """Robust Smart Money v2 using ATR-normalized flows and robust volume stats.

    Inputs: DataFrame with high, low, close, volume.
    Returns: SmartMoneyResult with interpretation aligned to v1.
    """
    if df is None or df.empty:
        return SmartMoneyResult(
            score=0.0,
            accumulation_days=0,
            distribution_days=0,
            net_accumulation=0,
            obv_trend="NEUTRAL",
            mfi=50.0,
            mfi_signal="NEUTRAL",
            unusual_volume="NORMAL",
            interpretation="NEUTRAL",
        )

    # Clip lookbacks to available data
    lookback = min(lookback, len(df))
    recent = df.tail(max(lookback, obv_window, mfi_percentile_lookback)).copy()

    # Robust volume stats (median / MAD)
    vol = recent["volume"].astype(float)
    med_vol = vol.median()
    mad = np.median(np.abs(vol - med_vol))
    mad = mad if mad > 0 else 1e-6
    vol_z = np.clip((vol - med_vol) / (1.4826 * mad), -4, 4)
    recent["vol_z"] = vol_z

    # ATR-normalized return
    atr_window = max(2, min(14, len(recent)))
    atr_indicator = AverageTrueRange(
        high=recent["high"], low=recent["low"], close=recent["close"], window=atr_window
    )
    atr = atr_indicator.average_true_range()
    atr = atr.replace(0, np.nan).bfill().ffill()
    price_change = recent["close"].diff()
    r_norm = (price_change / atr).clip(-4, 4)
    recent["r_norm"] = r_norm

    # Money-flow tilt (typical price * volume), emphasis on high vol_z
    typical = (recent["high"] + recent["low"] + recent["close"]) / 3
    mf = (typical - typical.shift(1)) * vol
    mf_up = mf.where((mf > 0) & (vol_z > 1), 0)
    mf_dn = (-mf).where((mf < 0) & (vol_z > 1), 0)
    mf_up_sum = mf_up.sum()
    mf_dn_sum = mf_dn.sum()
    mf_balance = (mf_up_sum - mf_dn_sum) / (mf_up_sum + mf_dn_sum + 1e-9)
    mf_balance = float(np.clip(mf_balance, -1, 1))

    # OBV slope over last obv_window bars
    obv_indicator = ta.volume.OnBalanceVolumeIndicator(recent["close"], vol)
    obv_values = obv_indicator.on_balance_volume()
    obv_score = 0.0
    obv_trend = "NEUTRAL"
    if obv_values is not None and len(obv_values) >= obv_window:
        tail = obv_values.tail(obv_window)
        x = np.arange(len(tail))
        try:
            slope, _ = np.polyfit(x, tail, 1)
        except np.linalg.LinAlgError:
            slope = 0.0
        mean_abs = np.abs(tail.mean()) + 1e-9
        obv_score = float(np.clip(slope / mean_abs, -1, 1))
        if obv_score > 0.05:
            obv_trend = "BULLISH"
        elif obv_score < -0.05:
            obv_trend = "BEARISH"
        else:
            obv_trend = "NEUTRAL"

    # MFI percentile-based signal
    mfi_window_eff = max(2, min(mfi_window, len(recent)))
    mfi_indicator = ta.volume.MFIIndicator(
        high=recent["high"], low=recent["low"], close=recent["close"], volume=vol, window=mfi_window_eff
    )
    mfi_series = mfi_indicator.money_flow_index()
    if mfi_series is not None and len(mfi_series) > 0:
        mfi_value = float(mfi_series.iloc[-1])
    else:
        mfi_value = 50.0
    mfi_slice = mfi_series.dropna().tail(mfi_percentile_lookback)
    if len(mfi_slice) > 0:
        rank = (mfi_slice <= mfi_value).sum()
        p = rank / len(mfi_slice)
    else:
        p = 0.5
    mfi_score = float(np.clip((p - 0.5) * 2, -1, 1))
    if p >= 0.8:
        mfi_signal = "OVERBOUGHT"
    elif p <= 0.2:
        mfi_signal = "OVERSOLD"
    else:
        mfi_signal = "NEUTRAL"

    # Volume shock latest
    latest_vol_z = float(vol_z.iloc[-1]) if len(vol_z) else 0.0
    unusual_volume = "NORMAL"
    if latest_vol_z >= 2.0:
        unusual_volume = "HIGH"
    elif latest_vol_z <= -1.5:
        unusual_volume = "LOW"

    shock = float(np.clip(latest_vol_z / 2, -1, 1))
    last_dir = float(np.sign(r_norm.iloc[-1] + 0.01)) if len(r_norm.dropna()) else 0.0

    # Accumulation/distribution days using robust vol_z
    accumulation_mask = (recent["r_norm"] > 0) & (recent["vol_z"] > 1)
    distribution_mask = (recent["r_norm"] < 0) & (recent["vol_z"] > 1)
    accumulation_days = int(accumulation_mask.sum())
    distribution_days = int(distribution_mask.sum())
    net_accumulation = accumulation_days - distribution_days

    # Short-term directional bias (tanh mean of last 5 normalized returns)
    short_bias = float(np.tanh(recent["r_norm"].tail(5).mean() if len(recent) else 0.0))

    # Composite score
    score = (
        2.0 * mf_balance
        + 1.2 * obv_score
        + 0.8 * mfi_score
        + 0.8 * shock * last_dir
        + 0.6 * short_bias
    )
    score = float(np.clip(score, -3.0, 5.0))

    if score >= 3.0:
        interpretation = "ACCUMULATION"
    elif score <= 0.0:
        interpretation = "DISTRIBUTION"
    else:
        interpretation = "NEUTRAL"

    return SmartMoneyResult(
        score=score,
        accumulation_days=accumulation_days,
        distribution_days=distribution_days,
        net_accumulation=net_accumulation,
        obv_trend=obv_trend,
        mfi=mfi_value,
        mfi_signal=mfi_signal,
        unusual_volume=unusual_volume,
        interpretation=interpretation,
    )
