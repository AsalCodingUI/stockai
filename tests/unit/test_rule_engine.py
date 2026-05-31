"""Unit Tests for Rule-Based Confluence Engine.

Tests for:
- RuleEngineConfig default parameters
- RuleEngine evaluation logic with mock data
- Dynamic position sizing logic
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from stockai.scoring.rule_engine import RuleEngine, RuleEngineConfig, LayerScore
from stockai.core.regime import MarketRegime
from stockai.risk.position_sizing import calculate_dynamic_position_size


def create_mock_stock_data(days: int = 60) -> pd.DataFrame:
    """Helper to generate trending upward mock data for testing."""
    dates = [datetime.now() - timedelta(days=days - i) for i in range(days)]

    # Rising price to ensure bullish EMA alignment (EMA20 > EMA50)
    prices = [1000.0 * (1.005 ** i) for i in range(days)]

    # Elevated volumes towards the end
    volumes = [500_000] * (days - 5) + [1_500_000] * 5  # spikes at the end to trigger volume ratio

    df = pd.DataFrame({
        "Date": dates,
        "Open": [p * 0.99 for p in prices],
        "High": [p * 1.01 for p in prices],
        "Low": [p * 0.98 for p in prices],
        "Close": prices,
        "Volume": volumes,
    })
    return df


class TestRuleEngine:
    def test_default_config(self):
        cfg = RuleEngineConfig()
        assert cfg.ema_fast == 20
        assert cfg.ema_slow == 50
        assert cfg.min_avg_volume_shares == 500_000

    def test_evaluate_bullish_case(self):
        df = create_mock_stock_data(60)
        engine = RuleEngine()

        fundamentals = {
            "pe_ratio": 15.0,
            "pb_ratio": 1.5,
            "roe": 18.0,
            "debt_to_equity": 0.5,
            "profit_margin": 15.0,
            "revenue_growth": 0.10,
        }

        flow_signal = {"signal": "ACCUMULATION", "strength": "STRONG"}
        sentiment = {"sentiment": "BULLISH"}

        result = engine.evaluate(
            symbol="TLKM",
            df=df,
            fundamentals=fundamentals,
            flow_signal=flow_signal,
            sentiment=sentiment,
        )

        # Bullish trending data with accumulation and good fundamentals should pass universe & trend gates
        assert result.universe_ok is True
        assert result.trend_ok is True
        assert result.total_score > 0
        assert result.grade in ["A+", "A", "B", "NO TRADE"]


class TestDynamicPositionSizing:
    def test_grade_and_regime_scaling(self):
        # A+ under BULL regime -> 100% of risk limit (2.0%)
        size_bull_aplus = calculate_dynamic_position_size(
            capital=10_000_000,
            entry_price=1000.0,
            stop_loss_price=950.0,
            symbol="TLKM",
            grade="A+",
            regime=MarketRegime.BULL,
            max_risk_percent=2.0,
            max_position_percent=20.0,
        )

        # B under BEAR regime -> size scaled down: 50% (Grade B) * 50% (Regime BEAR) = 25% of risk limit (0.5%)
        size_bear_b = calculate_dynamic_position_size(
            capital=10_000_000,
            entry_price=1000.0,
            stop_loss_price=950.0,
            symbol="TLKM",
            grade="B",
            regime=MarketRegime.BEAR,
            max_risk_percent=2.0,
            max_position_percent=20.0,
        )

        assert size_bull_aplus.risk_percent > size_bear_b.risk_percent
        assert size_bull_aplus.lots > size_bear_b.lots
