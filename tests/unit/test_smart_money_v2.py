"""Tests for Smart Money v2 scoring."""

import numpy as np
import pandas as pd

from stockai.scoring.smart_money import calculate_smart_money_score_v2


def _make_mock_ohlcv(days: int = 40, trend: str = "up", volume_spike: bool = False) -> pd.DataFrame:
    np.random.seed(0)
    rng = pd.date_range("2024-01-01", periods=days, freq="D")
    if trend == "up":
        close = np.linspace(100, 115, days)
    elif trend == "down":
        close = np.linspace(115, 95, days)
    else:
        close = np.full(days, 100.0)
    close = close + np.random.normal(0, 0.1, size=days)
    open_ = np.concatenate(([close[0]], close[:-1]))
    high = close * 1.01
    low = close * 0.99
    volume = 1_000_000 * (1 + 0.1 * np.sin(np.linspace(0, np.pi, days)))
    if trend == "up":
        volume *= np.linspace(1.0, 1.3, days)
    if volume_spike:
        volume[-1] = volume.max() * 5

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume.astype(int),
        },
        index=rng,
    )


def test_v2_score_range():
    df = _make_mock_ohlcv()
    result = calculate_smart_money_score_v2(df, lookback=20)
    assert -3.0 <= result.score <= 5.0


def test_v2_accumulation_bias():
    df = _make_mock_ohlcv(trend="up")
    result = calculate_smart_money_score_v2(df, lookback=20)
    assert result.score > 0
    assert result.interpretation != "DISTRIBUTION"


def test_v2_distribution_bias():
    df = _make_mock_ohlcv(trend="down")
    result = calculate_smart_money_score_v2(df, lookback=20)
    assert result.interpretation in {"NEUTRAL", "DISTRIBUTION"}


def test_v2_handles_volume_spike():
    df = _make_mock_ohlcv(trend="flat", volume_spike=True)
    result = calculate_smart_money_score_v2(df, lookback=20)
    assert result.unusual_volume in {"HIGH", "NORMAL", "LOW"}
    assert -3.0 <= result.score <= 5.0


def test_v2_handles_short_data():
    df = _make_mock_ohlcv(days=10)
    result = calculate_smart_money_score_v2(df, lookback=20)
    assert result is not None
    assert -3.0 <= result.score <= 5.0
