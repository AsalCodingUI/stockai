"""Market Regime Engine for IHSG (Jakarta Composite Index).

Detects current market conditions before autopilot runs, allowing the
signal engine to be more aggressive in bull markets and more selective
(or silent) during bear conditions.

Regimes:
  BULL     — IHSG above EMA20, trending up, low volatility → aggressive
  NEUTRAL  — IHSG flat near EMA20 → normal thresholds
  BEAR     — IHSG below EMA20, trending down → very selective
  VOLATILE — High realized volatility regardless of direction → reduce size

The RegimeEngine adjusts the minimum score threshold and position sizing
multiplier that the AutopilotEngine should use.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import numpy as np
import pandas as pd
import pytz

logger = logging.getLogger(__name__)

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
IHSG_TICKER = "^JKSE"


class MarketRegime(Enum):
    """Current IHSG market regime."""
    BULL = "BULL"
    NEUTRAL = "NEUTRAL"
    BEAR = "BEAR"
    VOLATILE = "VOLATILE"


@dataclass
class RegimeResult:
    """Output from the regime engine."""

    regime: MarketRegime
    timestamp: datetime

    # Raw metrics
    ihsg_last_price: float = 0.0
    ihsg_ema20: float = 0.0
    ihsg_pct_vs_ema20: float = 0.0        # % above/below EMA20
    ihsg_pct_change_5d: float = 0.0       # 5-day return
    ihsg_realized_vol_10d: float = 0.0    # Annualised 10d vol (%)

    # Regime guidance
    action_bias: str = "SELECTIVE"        # AGGRESSIVE, SELECTIVE, DEFENSIVE, HOLD
    min_score_override: float = 75.0      # Override AutopilotConfig buy_threshold
    position_size_multiplier: float = 1.0 # 1.0 = full, 0.75 = reduced, 0.5 = half

    # Human-readable
    regime_note: str = ""

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "timestamp": self.timestamp.isoformat(),
            "ihsg_last_price": round(self.ihsg_last_price, 0),
            "ihsg_ema20": round(self.ihsg_ema20, 0),
            "ihsg_pct_vs_ema20": round(self.ihsg_pct_vs_ema20, 2),
            "ihsg_pct_change_5d": round(self.ihsg_pct_change_5d, 2),
            "ihsg_realized_vol_10d": round(self.ihsg_realized_vol_10d, 2),
            "action_bias": self.action_bias,
            "min_score_override": self.min_score_override,
            "position_size_multiplier": self.position_size_multiplier,
            "regime_note": self.regime_note,
        }


class RegimeEngine:
    """Detect IHSG market regime for autopilot context.

    Usage::

        regime = RegimeEngine().get_current_regime()
        print(regime.regime.value, regime.action_bias)
        # Use regime.min_score_override to adjust buy threshold
        # Use regime.position_size_multiplier to scale lot sizes
    """

    EMA_PERIOD = 20
    VOL_PERIOD = 10          # 10-day rolling std for volatility
    HIGH_VOL_THRESHOLD = 25  # Annualised vol >25% → VOLATILE flag

    # Min score thresholds per regime
    REGIME_SCORE_MAP: dict[MarketRegime, float] = {
        MarketRegime.BULL: 70.0,       # Relax — more opportunities
        MarketRegime.NEUTRAL: 75.0,    # Default
        MarketRegime.BEAR: 85.0,       # Very selective
        MarketRegime.VOLATILE: 80.0,   # Cautious
    }

    # Position size multiplier per regime
    REGIME_SIZE_MAP: dict[MarketRegime, float] = {
        MarketRegime.BULL: 1.0,
        MarketRegime.NEUTRAL: 1.0,
        MarketRegime.BEAR: 0.5,
        MarketRegime.VOLATILE: 0.75,
    }

    # Action bias per regime
    REGIME_BIAS_MAP: dict[MarketRegime, str] = {
        MarketRegime.BULL: "AGGRESSIVE",
        MarketRegime.NEUTRAL: "SELECTIVE",
        MarketRegime.BEAR: "DEFENSIVE",
        MarketRegime.VOLATILE: "CAUTIOUS",
    }

    def get_current_regime(self) -> RegimeResult:
        """Fetch IHSG data and determine current market regime.

        Returns a RegimeResult with regime classification and
        guidance parameters for the autopilot engine.
        Falls back to NEUTRAL on data fetch failure.
        """
        now = datetime.now(JAKARTA_TZ)

        try:
            df = self._fetch_ihsg_data()
            return self._classify(df, now)
        except Exception as exc:
            logger.warning("Regime engine fallback to NEUTRAL: %s", exc)
            return RegimeResult(
                regime=MarketRegime.NEUTRAL,
                timestamp=now,
                action_bias="SELECTIVE",
                min_score_override=self.REGIME_SCORE_MAP[MarketRegime.NEUTRAL],
                position_size_multiplier=1.0,
                regime_note="Data unavailable — defaulting to NEUTRAL",
            )

    # ── Private helpers ──────────────────────────────────────────────────

    def _fetch_ihsg_data(self) -> pd.DataFrame:
        """Fetch IHSG price history (last 40 trading days)."""
        import yfinance as yf

        df = yf.Ticker(IHSG_TICKER).history(period="60d", interval="1d")
        if df is None or df.empty or len(df) < 15:
            raise ValueError("IHSG data too short or unavailable")
        df.columns = [c.lower() for c in df.columns]
        return df

    def _classify(self, df: pd.DataFrame, now: datetime) -> RegimeResult:
        """Classify regime from IHSG OHLCV data."""
        close = df["close"]

        # EMA20
        ema20 = close.ewm(span=self.EMA_PERIOD, adjust=False).mean()
        last_close = float(close.iloc[-1])
        last_ema20 = float(ema20.iloc[-1])
        pct_vs_ema20 = (last_close / last_ema20 - 1) * 100

        # 5-day return
        pct_5d = 0.0
        if len(close) >= 6:
            pct_5d = (float(close.iloc[-1]) / float(close.iloc[-6]) - 1) * 100

        # 10-day realized volatility (annualised)
        realized_vol = 0.0
        if len(close) >= self.VOL_PERIOD + 1:
            log_returns = np.log(close / close.shift(1)).dropna()
            vol_10d = float(log_returns.iloc[-self.VOL_PERIOD:].std())
            realized_vol = vol_10d * (252 ** 0.5) * 100

        # ── Regime classification logic ──────────────────────────────────
        if realized_vol > self.HIGH_VOL_THRESHOLD:
            regime = MarketRegime.VOLATILE
            note = (
                f"High volatility ({realized_vol:.1f}% annualised) — "
                "reduce position size and be selective"
            )
        elif pct_vs_ema20 > 1.0 and pct_5d > 0.5:
            regime = MarketRegime.BULL
            note = (
                f"IHSG {pct_vs_ema20:+.1f}% above EMA20, +{pct_5d:.1f}% in 5d — "
                "bullish market, scan more aggressively"
            )
        elif pct_vs_ema20 < -1.5 or pct_5d < -2.0:
            regime = MarketRegime.BEAR
            note = (
                f"IHSG {pct_vs_ema20:+.1f}% vs EMA20, {pct_5d:+.1f}% in 5d — "
                "bearish market, only A+ setups qualify"
            )
        else:
            regime = MarketRegime.NEUTRAL
            note = (
                f"IHSG {pct_vs_ema20:+.1f}% vs EMA20 — "
                "sideways, normal selectivity applies"
            )

        return RegimeResult(
            regime=regime,
            timestamp=now,
            ihsg_last_price=last_close,
            ihsg_ema20=last_ema20,
            ihsg_pct_vs_ema20=pct_vs_ema20,
            ihsg_pct_change_5d=pct_5d,
            ihsg_realized_vol_10d=realized_vol,
            action_bias=self.REGIME_BIAS_MAP[regime],
            min_score_override=self.REGIME_SCORE_MAP[regime],
            position_size_multiplier=self.REGIME_SIZE_MAP[regime],
            regime_note=note,
        )
