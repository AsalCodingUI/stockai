from __future__ import annotations

import math

import pandas as pd

from stockai.autopilot.engine import AutopilotConfig, AutopilotEngine, IndexType, TradeSignal
from stockai.scoring.analyzer import AnalysisResult
from stockai.scoring.gates import GateResult
from stockai.scoring.intelligence import run_intelligence_pipeline
from stockai.scoring.intelligence import pipeline as intelligence_pipeline
from stockai.scoring.intelligence.regime import _CACHE
from stockai.scoring.smart_money import SmartMoneyResult
from stockai.scoring.support_resistance import SupportResistanceResult


def _make_ohlcv(periods: int, start: float = 100.0, step: float = 1.0) -> pd.DataFrame:
    rows = []
    for i in range(periods):
        close = start + (i * step)
        rows.append(
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=i),
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1_000_000 + (i * 10_000),
            }
        )
    return pd.DataFrame(rows)


class _FakeYahoo:
    def __init__(self, stock_df: pd.DataFrame, index_df: pd.DataFrame, hourly_df: pd.DataFrame):
        self.stock_df = stock_df
        self.index_df = index_df
        self.hourly_df = hourly_df

    def get_price_history(self, symbol: str, period: str = "1mo", interval: str = "1d"):
        symbol = symbol.upper()
        if symbol == "^JKSE":
            return self.index_df.copy()
        if interval == "1wk":
            weekly = self.stock_df.copy()
            weekly["date"] = pd.to_datetime(weekly["date"])
            return (
                weekly.set_index("date")
                .resample("W")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
                .reset_index()
            )
        if interval == "1h":
            return self.hourly_df.copy()
        return self.stock_df.copy()


def _analysis_result() -> AnalysisResult:
    return AnalysisResult(
        ticker="BBCA",
        current_price=150.0,
        composite_score=88.0,
        base_composite_score=80.0,
        value_score=80.0,
        quality_score=85.0,
        momentum_score=90.0,
        volatility_score=30.0,
        foreign_flow_bonus=0.0,
        foreign_flow_signal="NEUTRAL",
        foreign_flow_strength="WEAK",
        foreign_flow_source="",
        foreign_consecutive_buy_days=0,
        foreign_total_net_5d=0.0,
        foreign_latest_net=0.0,
        volume_bonus=0.0,
        volume_ratio=1.0,
        volume_classification="NORMAL",
        volume_today=0.0,
        avg_volume_20d=0.0,
        volume_price_action="NEUTRAL",
        sentiment_bonus=0.0,
        sentiment_label="NEUTRAL",
        sentiment_score_raw=0,
        sentiment_post_count=0,
        sentiment_bullish_count=0,
        sentiment_bearish_count=0,
        sentiment_source="",
        smart_money=SmartMoneyResult(
            score=75.0,
            accumulation_days=5,
            distribution_days=0,
            net_accumulation=1.0,
            obv_trend="UP",
            mfi=60.0,
            mfi_signal="BULLISH",
            unusual_volume="NORMAL",
            interpretation="BULLISH",
        ),
        support_resistance=SupportResistanceResult(
            current_price=150.0,
            supports=[140.0],
            resistances=[160.0, 170.0, 180.0],
            nearest_support=140.0,
            nearest_resistance=160.0,
            distance_to_support_pct=6.6,
            is_near_support=False,
            suggested_stop_loss=135.0,
        ),
        adx={"adx": 30.0, "trend_strength": "STRONG", "trend_direction": "UP", "is_tradeable": True},
        gates=GateResult(
            all_passed=True,
            gates_passed=6,
            total_gates=6,
            passed_gates=["g1", "g2", "g3", "g4", "g5", "g6"],
            rejection_reasons=[],
            confidence="HIGH",
        ),
        trade_plan=None,
        decision="BUY",
        confidence="HIGH",
    )


def test_intelligence_pipeline_returns_execute_for_strong_setup(monkeypatch):
    _CACHE["expires_at"] = None
    _CACHE["result"] = None
    monkeypatch.setattr(
        intelligence_pipeline,
        "_scan_news_risk",
        lambda symbol: ("CLEAR", "Tidak ada berita negatif material", 10.0),
    )
    stock_df = _make_ohlcv(140, start=100, step=1.2)
    stock_df.loc[len(stock_df) - 1, "volume"] = stock_df["volume"].tail(20).mean() * 2.5
    stock_df.loc[len(stock_df) - 2, ["open", "close"]] = [260.0, 250.0]
    stock_df.loc[len(stock_df) - 1, ["open", "close", "high", "low"]] = [248.0, 265.0, 267.0, 246.0]
    index_df = _make_ohlcv(80, start=100, step=0.2)

    hourly_rows = []
    base = pd.Timestamp("2026-02-01")
    for i in range(240):
        close = 100 + (i * 0.05) + math.sin(i / 5) * 1.5
        hourly_rows.append(
            {
                "date": base + pd.Timedelta(hours=i),
                "open": close - 0.2,
                "high": close + 0.9,
                "low": close - 0.9,
                "close": close,
                "volume": 50_000,
            }
        )
    hourly_df = pd.DataFrame(hourly_rows)

    fake_yahoo = _FakeYahoo(stock_df=stock_df, index_df=index_df, hourly_df=hourly_df)
    result = run_intelligence_pipeline(
        "BBCA",
        analysis_result=_analysis_result(),
        existing_score=100.0,
        yahoo=fake_yahoo,
    )

    assert result.recommendation == "EXECUTE"
    assert result.confidence_level == "HIGH"
    assert result.mtf_aligned >= 2
    assert result.breakout_score >= 12.0


def test_intelligence_pipeline_skips_when_market_is_sideways_and_rs_is_weak():
    _CACHE["expires_at"] = None
    _CACHE["result"] = None
    stock_df = _make_ohlcv(60, start=100, step=0.1)
    index_df = _make_ohlcv(60, start=100, step=0.0)
    index_df["close"] = 100.0
    index_df["open"] = 100.0
    index_df["high"] = 101.0
    index_df["low"] = 99.0
    hourly_df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-02-01") + pd.Timedelta(hours=i),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 10_000,
            }
            for i in range(240)
        ]
    )
    fake_yahoo = _FakeYahoo(stock_df=stock_df, index_df=index_df, hourly_df=hourly_df)

    result = run_intelligence_pipeline(
        "BBCA",
        analysis_result=_analysis_result(),
        existing_score=70.0,
        yahoo=fake_yahoo,
    )

    assert result.regime == "SIDEWAYS"
    assert result.recommendation == "SKIP"


def test_size_positions_keeps_analysis_stop_loss_and_target():
    engine = AutopilotEngine(
        AutopilotConfig(index=IndexType.JII70, capital=10_000_000, dry_run=True)
    )
    engine.cash = 10_000_000

    signal = TradeSignal(
        symbol="BBCA",
        action="BUY",
        score=85.0,
        current_price=100.0,
        lots=0,
        shares=0,
        position_value=0.0,
        stop_loss=95.0,
        target=115.0,
        reason="test",
    )

    sized = engine._size_positions([signal])

    assert sized
    assert sized[0].stop_loss == 95.0
    assert sized[0].target == 115.0
