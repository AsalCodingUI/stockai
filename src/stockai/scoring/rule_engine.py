"""Rule-Based Confluence Engine for BEI Swing Trading.

Implements a 5-layer signal system where entry only occurs when
multiple independent layers confirm at the same time:

  Trend Layer    (25 pts) : EMA20/50 alignment, HH/HL structure
  Setup Layer    (20 pts) : Healthy pullback to EMA20 area
  Momentum Layer (20 pts) : RSI, MFI, MACD, confirmation candle — need ≥3/4
  Volume Layer   (20 pts) : Volume ratio or foreign/broker flow — need ≥1/2
  Fundamental    (15 pts) : Firewall against value traps, bad earnings

Grading:
  85–100 → A+  (full-size entry allowed)
  75–84  → A   (normal entry)
  65–74  → B   (small entry or wait for next candle)
  <65    → NO TRADE

References (BEI research):
  - EMA + RSI/MFI + MACD combo: Santoso & Sukamulja (SemanticScholar 2021)
  - Bandarmology as confirmation: Moduit.id, Stockbit Help
  - Swing entry rules: Scribd swing-trading-strategies doc
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# BEI transaction fee constants
# ─────────────────────────────────────────────
BEI_BUY_FEE_PCT: float = 0.0019   # 0.19%
BEI_SELL_FEE_PCT: float = 0.0029  # 0.29%
BEI_SLIPPAGE_PCT: float = 0.001   # 0.10% spread slippage estimate
SHARES_PER_LOT: int = 100


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

@dataclass
class RuleEngineConfig:
    """Tunable parameters for the rule engine.

    Default values are calibrated for BEI swing trading based on
    the combined EMA/RSI/MFI/MACD research cited in the spec.
    """

    # EMA periods
    ema_fast: int = 20
    ema_slow: int = 50
    ema_trail: int = 9     # Trailing stop reference after TP1

    # RSI
    rsi_period: int = 14
    rsi_min: float = 50.0          # RSI must be above this for bullish confirmation
    rsi_recovery_min: float = 40.0 # Alternatively: RSI rising 3 bars from this level

    # MFI
    mfi_period: int = 14
    mfi_rising_window: int = 3     # MFI must be rising or stable over this many bars

    # MACD (12/26/9)
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal_period: int = 9

    # ATR
    atr_period: int = 14
    atr_sl_multiplier: float = 2.0      # SL = entry - atr_sl_multiplier * ATR
    atr_trail_multiplier: float = 1.5   # Trailing = price - atr_trail * ATR

    # Volume
    volume_period: int = 20
    volume_ratio_min: float = 1.2       # Entry volume must be > 1.2x 20d average

    # Universe liquidity thresholds
    min_avg_volume_shares: float = 500_000   # Minimum 500K shares/day average
    max_spread_pct: float = 2.0              # Max bid-ask spread estimate

    # Pullback detection
    pullback_min_candles: int = 2        # At least 2 pullback candles before setup
    pullback_max_candles: int = 7        # Not more than 7 pullback candles
    pullback_max_distance_pct: float = 8.0  # EMA20 must be within 8% of current price

    # Entry extension guard
    max_extension_pct: float = 6.0      # Skip if price is >6% above setup area

    # No follow-through exit
    no_followthrough_bars: int = 5

    # Score thresholds
    grade_aplus_min: float = 85.0
    grade_a_min: float = 75.0
    grade_b_min: float = 65.0          # Below this: NO TRADE

    # R/R requirements
    min_risk_reward: float = 1.5


# ─────────────────────────────────────────────
# Output dataclasses
# ─────────────────────────────────────────────

@dataclass
class TradePlan:
    """Computed entry, SL, TP levels for a setup."""

    entry_price: float
    entry_type: str = "BREAK_HIGH"      # or "BUY_ON_CLOSE"

    stop_loss: float = 0.0              # Below swing low / 2*ATR
    invalidation_level: float = 0.0    # Hard exit if price re-enters this zone

    tp1: float = 0.0                   # Entry + 1R  → sell 30-50%
    tp2: float = 0.0                   # Entry + 2R  → sell remainder
    tp1_action: str = "SELL 40%"
    tp2_action: str = "SELL REMAINING / TRAIL"

    trailing_ref: str = "EMA9"          # Or "1.5*ATR"
    trailing_active_after_tp1: bool = True

    atr: float = 0.0
    risk_per_share: float = 0.0
    risk_reward: float = 0.0

    # Dynamic position guidance
    position_pct_of_risk: float = 1.0  # 1.0 = full, 0.75 = A, 0.5 = B setup


@dataclass
class LayerDetail:
    """Per-layer pass/fail and reason text."""
    passed: bool = False
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class LayerScore:
    """Full scoring result from the rule engine."""

    symbol: str = ""

    # Individual layer scores (max per layer shown)
    trend: LayerDetail = field(default_factory=LayerDetail)      # max 25
    setup: LayerDetail = field(default_factory=LayerDetail)      # max 20
    momentum: LayerDetail = field(default_factory=LayerDetail)   # max 20
    volume: LayerDetail = field(default_factory=LayerDetail)     # max 20
    fundamental: LayerDetail = field(default_factory=LayerDetail)# max 15

    # Aggregated
    total_score: float = 0.0       # 0–100
    grade: str = "NO TRADE"        # A+, A, B, NO TRADE
    entry_signal: str = "NO TRADE" # BUY or NO TRADE

    # Hard gate flags (any False → NO TRADE regardless of score)
    universe_ok: bool = False
    trend_ok: bool = False
    momentum_ok: bool = False   # >=3 of 4 subfilters
    volume_ok: bool = False     # >=1 of 2 subfilters
    fundamental_ok: bool = True # Firewall — default True, fail = override

    # Momentum sub-checks (for transparency)
    momentum_rsi_ok: bool = False
    momentum_mfi_ok: bool = False
    momentum_macd_ok: bool = False
    momentum_candle_ok: bool = False
    momentum_pass_count: int = 0    # Should be >=3

    # Volume sub-checks
    volume_ratio_ok: bool = False
    volume_flow_ok: bool = False
    volume_pass_count: int = 0      # Should be >=1

    # Trade plan (only populated when entry_signal == "BUY")
    trade_plan: TradePlan | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "symbol": self.symbol,
            "total_score": round(self.total_score, 1),
            "grade": self.grade,
            "entry_signal": self.entry_signal,
            "universe_ok": self.universe_ok,
            "trend_ok": self.trend_ok,
            "momentum_ok": self.momentum_ok,
            "volume_ok": self.volume_ok,
            "fundamental_ok": self.fundamental_ok,
            "momentum_pass_count": self.momentum_pass_count,
            "volume_pass_count": self.volume_pass_count,
            "layers": {
                "trend": {
                    "score": round(self.trend.score, 1),
                    "passed": self.trend.passed,
                    "reasons": self.trend.reasons,
                },
                "setup": {
                    "score": round(self.setup.score, 1),
                    "passed": self.setup.passed,
                    "reasons": self.setup.reasons,
                },
                "momentum": {
                    "score": round(self.momentum.score, 1),
                    "passed": self.momentum.passed,
                    "reasons": self.momentum.reasons,
                    "rsi_ok": self.momentum_rsi_ok,
                    "mfi_ok": self.momentum_mfi_ok,
                    "macd_ok": self.momentum_macd_ok,
                    "candle_ok": self.momentum_candle_ok,
                },
                "volume": {
                    "score": round(self.volume.score, 1),
                    "passed": self.volume.passed,
                    "reasons": self.volume.reasons,
                    "ratio_ok": self.volume_ratio_ok,
                    "flow_ok": self.volume_flow_ok,
                },
                "fundamental": {
                    "score": round(self.fundamental.score, 1),
                    "passed": self.fundamental.passed,
                    "reasons": self.fundamental.reasons,
                },
            },
        }
        if self.trade_plan:
            tp = self.trade_plan
            d["trade_plan"] = {
                "entry_price": tp.entry_price,
                "entry_type": tp.entry_type,
                "stop_loss": tp.stop_loss,
                "invalidation_level": tp.invalidation_level,
                "tp1": tp.tp1,
                "tp2": tp.tp2,
                "tp1_action": tp.tp1_action,
                "tp2_action": tp.tp2_action,
                "trailing_ref": tp.trailing_ref,
                "atr": round(tp.atr, 2),
                "risk_per_share": round(tp.risk_per_share, 2),
                "risk_reward": round(tp.risk_reward, 2),
            }
        return d


# ─────────────────────────────────────────────
# Technical helpers
# ─────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high = df["high"] if "high" in df.columns else df["High"]
    low = df["low"] if "low" in df.columns else df["Low"]
    close = df["close"] if "close" in df.columns else df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Money Flow Index (requires OHLCV)."""
    high = df["high"] if "high" in df.columns else df["High"]
    low = df["low"] if "low" in df.columns else df["Low"]
    close = df["close"] if "close" in df.columns else df["Close"]
    volume = df["volume"] if "volume" in df.columns else df["Volume"]

    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume

    positive_mf = money_flow.where(typical_price > typical_price.shift(1), 0)
    negative_mf = money_flow.where(typical_price < typical_price.shift(1), 0)

    pos_sum = positive_mf.rolling(period).sum()
    neg_sum = negative_mf.rolling(period).sum()

    mfr = pos_sum / neg_sum.replace(0, np.nan)
    return 100 - (100 / (1 + mfr))


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd_line, signal_line, histogram)."""
    ema_f = _ema(series, fast)
    ema_s = _ema(series, slow)
    macd_line = ema_f - ema_s
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _is_higher_high_higher_low(close: pd.Series, window: int = 20) -> bool:
    """Check if price structure shows HH/HL pattern over recent window."""
    if len(close) < window:
        return False
    recent = close.iloc[-window:]
    midpoint = len(recent) // 2
    first_half_max = recent.iloc[:midpoint].max()
    second_half_max = recent.iloc[midpoint:].max()
    first_half_min = recent.iloc[:midpoint].min()
    second_half_min = recent.iloc[midpoint:].min()
    return second_half_max > first_half_max and second_half_min > first_half_min


def _recent_swing_low(df: pd.DataFrame, lookback: int = 10) -> float | None:
    """Find the most recent swing low for SL placement."""
    low_col = "low" if "low" in df.columns else "Low"
    if len(df) < lookback + 2:
        return None
    recent_lows = df[low_col].iloc[-(lookback + 1):-1]
    return float(recent_lows.min())


# ─────────────────────────────────────────────
# Main Rule Engine
# ─────────────────────────────────────────────

class RuleEngine:
    """5-layer confluence rule engine for BEI swing trading signals.

    Usage::

        engine = RuleEngine()
        df = yahoo_source.get_price_history("BBCA", period="6mo")
        result = engine.evaluate(
            symbol="BBCA",
            df=df,
            fundamentals={"roe": 18.5, "debt_to_equity": 0.8},
            flow_signal=foreign_flow_monitor.get_flow_signal("BBCA"),
            sentiment=stockbit_sentiment.analyze("BBCA"),
        )
        print(result.grade, result.total_score)
    """

    def __init__(self, config: RuleEngineConfig | None = None) -> None:
        self.config = config or RuleEngineConfig()

    # ── Public entry point ──────────────────────────────────────────────

    def evaluate(
        self,
        symbol: str,
        df: pd.DataFrame,
        fundamentals: dict[str, Any] | None = None,
        flow_signal: dict[str, Any] | None = None,
        sentiment: dict[str, Any] | None = None,
    ) -> LayerScore:
        """Evaluate a stock against all 5 layers and return a scored result.

        Args:
            symbol:       Stock ticker (e.g. "BBCA")
            df:           OHLCV DataFrame with at least 60 rows.
                          Column names may be lower or title-case.
            fundamentals: Dict with keys: roe, debt_to_equity, profit_margin,
                          pe_ratio, pb_ratio, revenue_growth (all optional).
            flow_signal:  Output of ForeignFlowMonitor.get_flow_signal().
            sentiment:    Output of StockbitSentiment.analyze().

        Returns:
            LayerScore with grade, total_score, and trade_plan.
        """
        result = LayerScore(symbol=symbol)
        cfg = self.config

        # Normalize column names to lowercase
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        if len(df) < 50:
            logger.debug("%s: Insufficient data (%d rows)", symbol, len(df))
            result.fundamental_ok = False
            result.trend.reasons.append(f"Insufficient data: {len(df)} rows (need ≥50)")
            return result

        close = df["close"]
        volume = df["volume"] if "volume" in df.columns else pd.Series(dtype=float)

        # ── Layer 0: Universe filter ────────────────────────────────────
        result.universe_ok = self._check_universe(df, volume, result)
        if not result.universe_ok:
            return result  # Skip everything — not investable

        # ── Layer 1: Trend (25 pts) ─────────────────────────────────────
        result.trend = self._check_trend(df, close, result)
        result.trend_ok = result.trend.passed
        if not result.trend_ok:
            result.total_score = result.trend.score
            result.grade = "NO TRADE"
            return result

        # ── Layer 2: Pullback / Setup (20 pts) ──────────────────────────
        result.setup = self._check_pullback_setup(df, close, result)

        # ── Layer 3: Momentum (20 pts, need ≥3/4) ──────────────────────
        result.momentum = self._check_momentum(df, close, result)
        result.momentum_ok = result.momentum.passed

        # ── Layer 4: Volume / Flow (20 pts, need ≥1/2) ─────────────────
        result.volume = self._check_volume_flow(df, volume, flow_signal, result)
        result.volume_ok = result.volume.passed

        # ── Layer 5: Fundamental firewall (15 pts) ──────────────────────
        result.fundamental = self._check_fundamental_firewall(
            fundamentals or {}, sentiment or {}, result
        )
        result.fundamental_ok = result.fundamental.passed

        # ── Aggregate score ─────────────────────────────────────────────
        result.total_score = (
            result.trend.score
            + result.setup.score
            + result.momentum.score
            + result.volume.score
            + result.fundamental.score
        )

        # ── Hard gate check ─────────────────────────────────────────────
        hard_pass = (
            result.trend_ok
            and result.momentum_ok
            and result.volume_ok
            and result.fundamental_ok
        )

        if not hard_pass or result.total_score < cfg.grade_b_min:
            result.grade = "NO TRADE"
            result.entry_signal = "NO TRADE"
            return result

        # ── Grade assignment ────────────────────────────────────────────
        if result.total_score >= cfg.grade_aplus_min:
            result.grade = "A+"
        elif result.total_score >= cfg.grade_a_min:
            result.grade = "A"
        else:
            result.grade = "B"

        result.entry_signal = "BUY"

        # ── Build trade plan ────────────────────────────────────────────
        result.trade_plan = self._build_trade_plan(df, close, result)
        if result.trade_plan and result.trade_plan.risk_reward < cfg.min_risk_reward:
            logger.debug(
                "%s: R/R %.2f < %.1f — downgraded to NO TRADE",
                symbol,
                result.trade_plan.risk_reward,
                cfg.min_risk_reward,
            )
            result.grade = "NO TRADE"
            result.entry_signal = "NO TRADE"

        return result

    # ── Layer 0: Universe filter ────────────────────────────────────────

    def _check_universe(
        self, df: pd.DataFrame, volume: pd.Series, result: LayerScore
    ) -> bool:
        """Check if stock is liquid enough to trade on BEI."""
        cfg = self.config
        reasons: list[str] = []

        # Average 20-day volume
        if volume.empty or len(volume) < 20:
            reasons.append("Volume data unavailable")
            return False

        avg_vol_20d = float(volume.rolling(20).mean().iloc[-1])
        if avg_vol_20d < cfg.min_avg_volume_shares:
            reasons.append(
                f"Avg volume {avg_vol_20d/1e6:.1f}M < {cfg.min_avg_volume_shares/1e6:.1f}M minimum"
            )
            logger.debug("Universe FAIL %s: low volume", result.symbol)
            return False

        reasons.append(f"Avg volume {avg_vol_20d/1e6:.1f}M shares/day ✓")

        # Detect "dead" chart (zero volume days > 30% of last 20 bars)
        zero_days = int((volume.iloc[-20:] == 0).sum())
        if zero_days > 6:
            reasons.append(f"Too many zero-volume days ({zero_days}/20)")
            return False

        return True

    # ── Layer 1: Trend (25 pts) ─────────────────────────────────────────

    def _check_trend(
        self, df: pd.DataFrame, close: pd.Series, result: LayerScore
    ) -> LayerDetail:
        """Score: price > EMA20, EMA20 > EMA50, EMA50 rising, no aggressive LL."""
        cfg = self.config
        detail = LayerDetail()
        score = 0.0

        ema20 = _ema(close, cfg.ema_fast)
        ema50 = _ema(close, cfg.ema_slow)

        last_close = float(close.iloc[-1])
        last_ema20 = float(ema20.iloc[-1])
        last_ema50 = float(ema50.iloc[-1])

        # Sub-check 1: Price > EMA20 (10 pts)
        if last_close > last_ema20:
            score += 10
            detail.reasons.append(f"Price {last_close:,.0f} > EMA20 {last_ema20:,.0f} ✓")
        else:
            pct_below = (last_ema20 - last_close) / last_ema20 * 100
            detail.warnings.append(
                f"Price {pct_below:.1f}% below EMA20 — trend not confirmed"
            )

        # Sub-check 2: EMA20 > EMA50 (8 pts)
        if last_ema20 > last_ema50:
            score += 8
            detail.reasons.append(f"EMA20 {last_ema20:,.0f} > EMA50 {last_ema50:,.0f} ✓")
        else:
            detail.warnings.append("EMA20 below EMA50 — bearish alignment")

        # Sub-check 3: EMA50 flat-to-rising (7 pts)
        if len(ema50) >= 10:
            ema50_slope = float(ema50.iloc[-1] - ema50.iloc[-10])
            if ema50_slope >= 0:
                score += 7
                detail.reasons.append(f"EMA50 rising ({ema50_slope:+.0f} over 10 bars) ✓")
            else:
                detail.warnings.append(f"EMA50 declining ({ema50_slope:.0f}) — trend weakening")

        # Sub-check 4 (bonus): HH/HL structure
        if _is_higher_high_higher_low(close, window=min(20, len(close))):
            # No extra pts but boosts reasons
            detail.reasons.append("HH/HL structure confirmed ✓")

        detail.score = min(25.0, score)
        detail.passed = score >= 18.0  # At least first two sub-checks
        return detail

    # ── Layer 2: Pullback/Setup (20 pts) ───────────────────────────────

    def _check_pullback_setup(
        self, df: pd.DataFrame, close: pd.Series, result: LayerScore
    ) -> LayerDetail:
        """Score: healthy pullback to EMA20 area, volume declining on pullback."""
        cfg = self.config
        detail = LayerDetail()
        score = 0.0

        ema20 = _ema(close, cfg.ema_fast)
        volume = df["volume"] if "volume" in df.columns else pd.Series(dtype=float)

        last_close = float(close.iloc[-1])
        last_ema20 = float(ema20.iloc[-1])

        # Distance from EMA20
        dist_pct = abs(last_close - last_ema20) / last_ema20 * 100

        if dist_pct <= cfg.pullback_max_distance_pct:
            score += 10
            detail.reasons.append(
                f"Price {dist_pct:.1f}% from EMA20 (within {cfg.pullback_max_distance_pct}%) ✓"
            )

            # Bonus: price is AT or slightly below EMA20 (pullback zone)
            if last_close <= last_ema20 * 1.02:
                score += 5
                detail.reasons.append("Price near/at EMA20 pullback zone ✓")
        else:
            extended_pct = dist_pct - cfg.pullback_max_distance_pct
            detail.warnings.append(
                f"Price {dist_pct:.1f}% from EMA20 — extended, skip until pullback"
            )
            if extended_pct > cfg.max_extension_pct:
                detail.warnings.append(
                    f"EXTENDED >6% from setup area — risk/reward unfavourable"
                )

        # Volume declining on pullback (5 pts)
        if not volume.empty and len(volume) >= 5:
            recent_vol_avg = float(volume.iloc[-3:].mean())
            prior_vol_avg = float(volume.iloc[-8:-3].mean())
            if prior_vol_avg > 0 and recent_vol_avg < prior_vol_avg * 0.85:
                score += 5
                detail.reasons.append("Volume declining on pullback — healthy setup ✓")
            elif prior_vol_avg > 0 and recent_vol_avg > prior_vol_avg * 1.3:
                detail.warnings.append("Volume rising on pullback — potential distribution")

        detail.score = min(20.0, score)
        detail.passed = score >= 10.0
        return detail

    # ── Layer 3: Momentum (20 pts, need ≥3/4) ──────────────────────────

    def _check_momentum(
        self, df: pd.DataFrame, close: pd.Series, result: LayerScore
    ) -> LayerDetail:
        """Score: RSI, MFI, MACD, candle confirmation — need at least 3/4."""
        cfg = self.config
        detail = LayerDetail()
        pass_count = 0
        score = 0.0

        # ── RSI check ──────────────────────────────────────────────────
        rsi = _rsi(close, cfg.rsi_period)
        if len(rsi) >= 4:
            last_rsi = float(rsi.iloc[-1])
            rsi_prev = [float(rsi.iloc[-(i + 1)]) for i in range(1, 4)]

            rsi_ok = last_rsi >= cfg.rsi_min
            rsi_rising = all(rsi.iloc[-1] > rsi.iloc[-i - 1] for i in range(1, 4))
            rsi_recovering = (
                float(rsi.iloc[-3]) >= cfg.rsi_recovery_min and rsi_rising
            )

            if rsi_ok or rsi_recovering:
                pass_count += 1
                result.momentum_rsi_ok = True
                score += 5
                if rsi_ok:
                    detail.reasons.append(f"RSI {last_rsi:.1f} ≥ {cfg.rsi_min} ✓")
                else:
                    detail.reasons.append(
                        f"RSI rising from {cfg.rsi_recovery_min}+ zone ({last_rsi:.1f}) ✓"
                    )
            else:
                detail.warnings.append(f"RSI {last_rsi:.1f} — not in bullish zone")

        # ── MFI check ──────────────────────────────────────────────────
        try:
            mfi = _mfi(df, cfg.mfi_period)
            if len(mfi) >= cfg.mfi_rising_window + 1:
                last_mfi = float(mfi.iloc[-1])
                mfi_rising = float(mfi.iloc[-1]) >= float(mfi.iloc[-(cfg.mfi_rising_window + 1)])
                mfi_not_collapsing = last_mfi >= 30  # Not deep oversold with pressure

                if mfi_rising and mfi_not_collapsing:
                    pass_count += 1
                    result.momentum_mfi_ok = True
                    score += 5
                    detail.reasons.append(f"MFI {last_mfi:.1f} rising — money flowing in ✓")
                else:
                    detail.warnings.append(
                        f"MFI {last_mfi:.1f} not rising — weak money flow"
                    )
        except Exception as exc:
            logger.debug("MFI calc error for %s: %s", result.symbol, exc)

        # ── MACD check ─────────────────────────────────────────────────
        macd_line, signal_line, _ = _macd(
            close, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal_period
        )
        if len(macd_line) >= 2:
            macd_above = float(macd_line.iloc[-1]) > float(signal_line.iloc[-1])
            macd_cross_up = macd_above and not (
                float(macd_line.iloc[-2]) > float(signal_line.iloc[-2])
            )

            if macd_above or macd_cross_up:
                pass_count += 1
                result.momentum_macd_ok = True
                score += 5
                msg = "MACD crossed above signal ✓" if macd_cross_up else "MACD > signal line ✓"
                detail.reasons.append(msg)
            else:
                detail.warnings.append("MACD below signal line — bearish momentum")

        # ── Candle confirmation ────────────────────────────────────────
        if "open" in df.columns and "high" in df.columns:
            op = df["open"].iloc[-1]
            hi = df["high"].iloc[-1]
            lo = df["low"].iloc[-1]
            cl = close.iloc[-1]
            prev_hi = df["high"].iloc[-2] if len(df) >= 2 else cl

            body = cl - op
            candle_range = hi - lo

            engulfing = (cl > op) and (cl > float(prev_hi))   # Bullish engulfing
            hammer = (
                (cl > op)
                and candle_range > 0
                and (op - lo) > abs(body) * 2  # Long lower wick
                and (hi - cl) < abs(body) * 0.5
            )
            strong_close = cl > float(prev_hi)  # Close above prior high

            if engulfing or hammer or strong_close:
                pass_count += 1
                result.momentum_candle_ok = True
                score += 5
                candle_type = "engulfing" if engulfing else ("hammer" if hammer else "strong close")
                detail.reasons.append(f"Bullish {candle_type} candle ✓")
            else:
                detail.warnings.append("No clear bullish confirmation candle")

        result.momentum_pass_count = pass_count
        detail.score = min(20.0, score)
        # Need at least 3/4 sub-checks
        detail.passed = pass_count >= 3
        if not detail.passed:
            detail.warnings.append(
                f"Momentum: only {pass_count}/4 sub-checks passed (need ≥3)"
            )
        return detail

    # ── Layer 4: Volume / Flow (20 pts, need ≥1/2) ─────────────────────

    def _check_volume_flow(
        self,
        df: pd.DataFrame,
        volume: pd.Series,
        flow_signal: dict[str, Any] | None,
        result: LayerScore,
    ) -> LayerDetail:
        """Score: volume ratio >1.2x or bullish broker/foreign flow."""
        cfg = self.config
        detail = LayerDetail()
        pass_count = 0
        score = 0.0

        # ── Sub-check 1: Volume ratio ───────────────────────────────────
        if not volume.empty and len(volume) >= cfg.volume_period + 1:
            avg_vol = float(volume.rolling(cfg.volume_period).mean().iloc[-1])
            last_vol = float(volume.iloc[-1])
            ratio = last_vol / avg_vol if avg_vol > 0 else 0.0

            if ratio >= cfg.volume_ratio_min:
                pass_count += 1
                result.volume_ratio_ok = True
                score += 10
                detail.reasons.append(
                    f"Volume {ratio:.1f}x average (≥{cfg.volume_ratio_min}x) ✓"
                )
            else:
                detail.warnings.append(
                    f"Volume {ratio:.1f}x average — below {cfg.volume_ratio_min}x threshold"
                )

        # ── Sub-check 2: Foreign/broker flow ───────────────────────────
        if flow_signal:
            signal_label = str(flow_signal.get("signal", "NEUTRAL")).upper()
            strength = str(flow_signal.get("strength", "WEAK")).upper()

            if signal_label == "ACCUMULATION":
                pass_count += 1
                result.volume_flow_ok = True
                score += 10
                detail.reasons.append(
                    f"Foreign flow ACCUMULATION ({strength}) — smart money buying ✓"
                )
            elif signal_label == "DISTRIBUTION":
                score -= 5
                detail.warnings.append(
                    "Foreign flow DISTRIBUTION — smart money selling, caution"
                )
            else:
                detail.warnings.append("Foreign flow NEUTRAL — no directional confirmation")

        result.volume_pass_count = pass_count
        detail.score = max(0.0, min(20.0, score))
        detail.passed = pass_count >= 1
        if not detail.passed:
            detail.warnings.append(
                "Volume/Flow: neither sub-check passed (need ≥1/2)"
            )
        return detail

    # ── Layer 5: Fundamental Firewall (15 pts) ──────────────────────────

    def _check_fundamental_firewall(
        self,
        fundamentals: dict[str, Any],
        sentiment: dict[str, Any],
        result: LayerScore,
    ) -> LayerDetail:
        """Score: avoid value traps, heavy debt, negative earnings.
        A hard FAIL here overrides everything else (firewall).
        """
        detail = LayerDetail()
        score = 10.0  # Start at 10, penalties applied
        hard_fail = False

        # ── Earnings quality ────────────────────────────────────────────
        roe = fundamentals.get("roe")
        if roe is not None:
            if roe < 0:
                hard_fail = True
                detail.warnings.append(f"ROE negative ({roe:.1f}%) — potential value trap")
            elif roe >= 15:
                score += 3
                detail.reasons.append(f"ROE {roe:.1f}% — healthy ✓")
            elif roe >= 8:
                score += 1
                detail.reasons.append(f"ROE {roe:.1f}% — acceptable")

        # ── Debt ────────────────────────────────────────────────────────
        de = fundamentals.get("debt_to_equity")
        if de is not None:
            if de > 3.0:
                hard_fail = True
                detail.warnings.append(f"D/E {de:.1f} — excessive debt load")
            elif de <= 1.0:
                score += 2
                detail.reasons.append(f"D/E {de:.1f} — conservative debt ✓")

        # ── Revenue growth ───────────────────────────────────────────────
        rev_growth = fundamentals.get("revenue_growth")
        if rev_growth is not None and rev_growth < -0.15:
            score -= 3
            detail.warnings.append(f"Revenue declining {rev_growth:.0%}")

        # ── Sentiment event risk ─────────────────────────────────────────
        sentiment_label = str(sentiment.get("sentiment", "NEUTRAL")).upper()
        if sentiment_label == "BEARISH":
            score -= 3
            detail.warnings.append("Community sentiment BEARISH — event risk present")
        elif sentiment_label == "BULLISH":
            score += 2
            detail.reasons.append("Community sentiment BULLISH ✓")

        # ── P/E sanity check (value trap guard) ─────────────────────────
        pe = fundamentals.get("pe_ratio")
        if pe is not None and pe > 60:
            score -= 2
            detail.warnings.append(f"P/E {pe:.1f} — elevated, check growth justification")

        detail.score = max(0.0, min(15.0, score))
        detail.passed = not hard_fail
        if hard_fail:
            detail.warnings.append(
                "FUNDAMENTAL FIREWALL TRIGGERED — BUY signal blocked"
            )
        return detail

    # ── Trade plan builder ───────────────────────────────────────────────

    def _build_trade_plan(
        self, df: pd.DataFrame, close: pd.Series, result: LayerScore
    ) -> TradePlan | None:
        """Build entry/SL/TP levels from chart structure + ATR."""
        cfg = self.config

        try:
            last_close = float(close.iloc[-1])
            atr_series = _atr(df, cfg.atr_period)
            last_atr = float(atr_series.iloc[-1]) if not atr_series.empty else last_close * 0.02

            # Entry: break above prior bar's high (conservative)
            if "high" in df.columns:
                entry = float(df["high"].iloc[-1])
                if entry <= last_close:
                    entry = last_close * 1.002  # tiny buffer
            else:
                entry = last_close * 1.005

            # Stop loss: below recent swing low or 2*ATR — whichever is closer
            swing_low = _recent_swing_low(df, lookback=10)
            atr_sl = entry - cfg.atr_sl_multiplier * last_atr
            if swing_low is not None:
                sl = max(atr_sl, swing_low * 0.995)  # just below swing low
            else:
                sl = atr_sl

            # Ensure SL is below entry
            if sl >= entry:
                sl = entry * 0.95

            risk = entry - sl
            if risk <= 0:
                return None

            tp1 = entry + risk          # 1R
            tp2 = entry + 2 * risk      # 2R
            rr = (tp2 - entry) / risk   # = 2.0 by design

            # Grade-based sizing hint
            position_pct = {
                "A+": 1.0,
                "A": 0.75,
                "B": 0.50,
            }.get(result.grade, 1.0)

            return TradePlan(
                entry_price=round(entry, 0),
                entry_type="BREAK_HIGH",
                stop_loss=round(sl, 0),
                invalidation_level=round(sl * 0.99, 0),
                tp1=round(tp1, 0),
                tp2=round(tp2, 0),
                tp1_action="SELL 40% of position",
                tp2_action="SELL remaining / trail with EMA9",
                trailing_ref=f"EMA9 or {cfg.atr_trail_multiplier}×ATR",
                trailing_active_after_tp1=True,
                atr=last_atr,
                risk_per_share=risk,
                risk_reward=round(rr, 2),
                position_pct_of_risk=position_pct,
            )

        except Exception as exc:
            logger.warning("Trade plan build failed for %s: %s", result.symbol, exc)
            return None


# ─────────────────────────────────────────────
# Convenience: format for CLI / Telegram
# ─────────────────────────────────────────────

def format_rule_engine_result(result: LayerScore) -> str:
    """Format a LayerScore for rich CLI or Telegram display."""
    grade_emoji = {
        "A+": "🏆",
        "A": "✅",
        "B": "👀",
        "NO TRADE": "⛔",
    }.get(result.grade, "❓")

    lines = [
        f"{grade_emoji} {result.symbol} — Grade {result.grade}  ({result.total_score:.0f}/100)",
        f"   Trend: {result.trend.score:.0f}/25  |  Setup: {result.setup.score:.0f}/20  |  "
        f"Momentum: {result.momentum.score:.0f}/20 ({result.momentum_pass_count}/4)  |  "
        f"Volume: {result.volume.score:.0f}/20  |  Fund: {result.fundamental.score:.0f}/15",
    ]

    if result.trade_plan and result.entry_signal == "BUY":
        tp = result.trade_plan
        lines += [
            f"   Entry: Rp {tp.entry_price:,.0f}  |  SL: Rp {tp.stop_loss:,.0f}  |  "
            f"TP1: Rp {tp.tp1:,.0f}  |  TP2: Rp {tp.tp2:,.0f}  |  R/R: {tp.risk_reward:.1f}x",
        ]

    for reason in (result.trend.reasons + result.momentum.reasons + result.volume.reasons)[:4]:
        lines.append(f"   ✓ {reason}")

    all_warnings = (
        result.trend.warnings
        + result.setup.warnings
        + result.momentum.warnings
        + result.volume.warnings
        + result.fundamental.warnings
    )
    for warn in all_warnings[:3]:
        lines.append(f"   ⚠ {warn}")

    return "\n".join(lines)
