"""Backtest engine for StockAI strategies.

Includes real BEI (Bursa Efek Indonesia) transaction costs:
  - Buy fee:   0.19% (broker + levy)
  - Sell fee:  0.29% (broker + levy + PPh 0.1%)
  - Slippage:  0.10% (spread estimate)

Available strategies:
  ema_cross          — EMA8/21 crossover with volume
  macd_momentum      — MACD + RSI guardrails
  gate_system        — Multi-gate system (simplified)
  rule_engine_swing  — Full 5-layer rule engine (EMA20/50 + RSI/MFI/MACD + volume)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Real BEI transaction cost constants ──────────────────────────────────────
BEI_BUY_FEE_PCT: float = 0.0019    # 0.19% — broker fee + IDX levy (buy side)
BEI_SELL_FEE_PCT: float = 0.0029   # 0.29% — broker fee + levy + PPh 0.1% (sell)
BEI_SLIPPAGE_PCT: float = 0.001    # 0.10% — estimated bid/ask spread
BEI_ROUNDTRIP_COST: float = BEI_BUY_FEE_PCT + BEI_SELL_FEE_PCT + 2 * BEI_SLIPPAGE_PCT


@dataclass
class Trade:
    symbol: str
    entry_date: datetime
    entry_price: float
    exit_date: datetime | None = None
    exit_price: float | None = None
    shares: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    hold_days: int = 0
    exit_reason: str = ""
    strategy: str = ""


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    period: str
    start_date: str
    end_date: str
    total_return_pct: float = 0.0
    benchmark_return_pct: float = 0.0
    alpha: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    avg_hold_days: float = 0.0
    best_trade_pct: float = 0.0
    worst_trade_pct: float = 0.0
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    benchmark_curve: list[dict[str, Any]] = field(default_factory=list)

    # ── BEI-specific extra metrics ─────────────────────────────────────
    expectancy: float = 0.0            # avg_win*wr - avg_loss*(1-wr) in Rupiah per trade
    expectancy_pct: float = 0.0        # same in % of entry price
    total_fees_paid: float = 0.0       # Total BEI fees paid (buy + sell + slippage)
    calmar_ratio: float = 0.0          # Total return / |Max drawdown|
    monthly_returns: list[dict[str, Any]] = field(default_factory=list)  # [{month, return_pct}]


def _signals_ema_cross(df: pd.DataFrame) -> pd.Series:
    """EMA cross + volume confirmation."""
    close = df["Close"]
    volume = df["Volume"]

    ema8 = close.ewm(span=8, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    vol_ma20 = volume.rolling(20).mean()

    ema_above = ema8 > ema21
    cross_up = ema_above & ~ema_above.shift(1, fill_value=False)
    cross_down = ~ema_above & ema_above.shift(1, fill_value=True)
    vol_confirm = volume > vol_ma20

    signals = pd.Series("HOLD", index=df.index)
    signals[cross_up & vol_confirm] = "BUY"
    signals[cross_down] = "SELL"
    return signals


def _signals_macd_momentum(df: pd.DataFrame) -> pd.Series:
    """MACD momentum strategy with RSI guardrails."""
    close = df["Close"]

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    macd_above = macd > signal
    cross_up = macd_above & ~macd_above.shift(1, fill_value=False)
    cross_down = ~macd_above & macd_above.shift(1, fill_value=True)

    signals = pd.Series("HOLD", index=df.index)
    signals[cross_up & (rsi < 70)] = "BUY"
    signals[cross_down | (rsi > 80)] = "SELL"
    return signals


def _signals_gate_system(df: pd.DataFrame) -> pd.Series:
    """Simplified gate-system strategy for historical simulation."""
    close = df["Close"]
    volume = df["Volume"]

    ema8 = close.ewm(span=8, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ma50 = close.rolling(50).mean()
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    vol_ma20 = volume.rolling(20).mean()

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    g1_trend = ema8 > ema21
    g2_ma50 = close > ma50
    g3_macd = macd > signal_line
    g4_rsi = (rsi >= 40) & (rsi <= 65)
    g5_volume = volume > vol_ma20 * 1.2

    gates_open = g1_trend & g2_ma50 & g3_macd & g4_rsi & g5_volume
    sell_cond = (~g1_trend) | (~g2_ma50) | (rsi > 75)

    prev_open = gates_open.shift(1, fill_value=False)
    buy_signal = gates_open & ~prev_open
    sell_signal = sell_cond & ~sell_cond.shift(1, fill_value=False)

    signals = pd.Series("HOLD", index=df.index)
    signals[buy_signal] = "BUY"
    signals[sell_signal] = "SELL"
    return signals


def _signals_rule_engine_swing(df: pd.DataFrame, config: dict | None = None) -> pd.Series:
    """Full 5-layer rule engine swing strategy for historical simulation.

    Layers replicated in vectorised form:
      Trend:    EMA20 > EMA50, price > EMA20
      Momentum: RSI14 ≥ 50, MACD above signal, MFI rising
      Volume:   Volume > 1.2× 20-day average
      Exit:     Price closes below EMA20, or stop-loss/take-profit hit
    """
    cfg = config or {}
    close = df["Close"]
    volume = df["Volume"]
    high = df.get("High", close)
    low = df.get("Low", close)

    # EMAs
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    # RSI14
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # MACD 12/26/9
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_sig = macd.ewm(span=9, adjust=False).mean()

    # MFI14 (simplified: using typical price direction as proxy)
    typical_price = (high + low + close) / 3
    mf = typical_price * volume
    pos_mf = mf.where(typical_price > typical_price.shift(1), 0)
    neg_mf = mf.where(typical_price < typical_price.shift(1), 0)
    mfr = pos_mf.rolling(14).sum() / neg_mf.rolling(14).sum().replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfr))

    # Volume filter
    vol_avg20 = volume.rolling(20).mean()
    vol_ok = volume > vol_avg20 * 1.2

    # Trend conditions
    trend_ok = (close > ema20) & (ema20 > ema50)

    # Momentum: need ≥ 2 of 3 (RSI, MACD, MFI) — vectorised simplification
    rsi_ok = rsi >= 50
    macd_ok = macd > macd_sig
    mfi_ok = mfi > mfi.shift(2)          # Rising MFI
    mom_count = rsi_ok.astype(int) + macd_ok.astype(int) + mfi_ok.astype(int)
    momentum_ok = mom_count >= 2

    # Buy when: trend OK AND momentum OK AND volume OK AND not already in uptrend
    buy_conditions = trend_ok & momentum_ok & vol_ok & ~(trend_ok.shift(1, fill_value=False))

    # Sell when: trend breaks (price below EMA20) or momentum collapses (all 3 fail)
    sell_conditions = (~trend_ok) & (~trend_ok.shift(1, fill_value=True))

    signals = pd.Series("HOLD", index=df.index)
    signals[buy_conditions] = "BUY"
    signals[sell_conditions] = "SELL"
    return signals


STRATEGY_MAP = {
    "ema_cross": _signals_ema_cross,
    "macd_momentum": _signals_macd_momentum,
    "gate_system": _signals_gate_system,
    "rule_engine_swing": _signals_rule_engine_swing,
}


class BacktestEngine:
    """Vectorized backtest engine with SL/TP, BEI fees, and single open-position model.

    BEI Fee Model (applied per trade):
      Buy:  entry_price × (1 + BEI_BUY_FEE_PCT + BEI_SLIPPAGE_PCT)
      Sell: exit_price × (1 - BEI_SELL_FEE_PCT - BEI_SLIPPAGE_PCT)
    """

    STOP_LOSS_PCT = 0.07
    TAKE_PROFIT_PCT = 0.15
    INITIAL_CAPITAL = 100_000_000
    POSITION_SIZE_PCT = 0.95

    def __init__(
        self,
        symbol: str,
        df: pd.DataFrame,
        strategy: str = "ema_cross",
        initial_capital: float | None = None,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        apply_bei_fees: bool = True,
    ):
        self.symbol = symbol
        self.df = df.copy()
        self.strategy = strategy
        self.capital = initial_capital or self.INITIAL_CAPITAL
        self.sl_pct = stop_loss_pct or self.STOP_LOSS_PCT
        self.tp_pct = take_profit_pct or self.TAKE_PROFIT_PCT
        self.apply_bei_fees = apply_bei_fees
        self._signal_fn = STRATEGY_MAP.get(strategy, _signals_ema_cross)

    def run(self) -> BacktestResult:
        df = self.df.copy()
        df.columns = [c.lower() for c in df.columns]
        if "date" in df.columns:
            df = df.set_index("date")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        df_sig = df.rename(
            columns={
                "close": "Close",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "volume": "Volume",
            }
        )
        signals = self._signal_fn(df_sig)

        trades: list[Trade] = []
        capital = self.capital
        position: Trade | None = None
        equity_series: list[dict[str, Any]] = []

        for date, row in df.iterrows():
            price = float(row["close"])
            signal = signals.get(date, "HOLD")

            if position is not None:
                sl_price = position.entry_price * (1 - self.sl_pct)
                tp_price = position.entry_price * (1 + self.tp_pct)
                hit_sl = price <= sl_price
                hit_tp = price >= tp_price

                if hit_sl or hit_tp or signal == "SELL":
                    # Apply BEI sell fee + slippage to net exit price
                    effective_exit = price * (1 - BEI_SELL_FEE_PCT - BEI_SLIPPAGE_PCT) if self.apply_bei_fees else price
                    pnl = (effective_exit - position.entry_price) * position.shares
                    pnl_pct = (effective_exit / position.entry_price - 1) * 100
                    hold_days = (date - position.entry_date).days

                    position.exit_date = date
                    position.exit_price = effective_exit
                    position.pnl = round(pnl, 2)
                    position.pnl_pct = round(pnl_pct, 2)
                    position.hold_days = hold_days
                    position.exit_reason = (
                        "stop_loss" if hit_sl else "take_profit" if hit_tp else "signal"
                    )

                    capital += position.shares * effective_exit
                    trades.append(position)
                    position = None

            if position is None and signal == "BUY" and capital > 0:
                invest = capital * self.POSITION_SIZE_PCT
                shares = int(invest / price / 100) * 100
                if shares > 0:
                    # Apply BEI buy fee + slippage to effective entry price
                    effective_buy = price * (1 + BEI_BUY_FEE_PCT + BEI_SLIPPAGE_PCT) if self.apply_bei_fees else price
                    cost = shares * effective_buy
                    capital -= cost
                    position = Trade(
                        symbol=self.symbol,
                        entry_date=date,
                        entry_price=effective_buy,
                        shares=shares,
                        strategy=self.strategy,
                    )

            portfolio_value = capital
            if position is not None:
                portfolio_value += position.shares * price

            equity_series.append(
                {
                    "time": date.strftime("%Y-%m-%d"),
                    "value": round(portfolio_value, 2),
                    "in_position": position is not None,
                }
            )

        if position is not None and len(df) > 0:
            last_date = df.index[-1]
            last_price = float(df["close"].iloc[-1])
            pnl = (last_price - position.entry_price) * position.shares
            pnl_pct = (last_price / position.entry_price - 1) * 100

            position.exit_date = last_date
            position.exit_price = last_price
            position.pnl = round(pnl, 2)
            position.pnl_pct = round(pnl_pct, 2)
            position.hold_days = (last_date - position.entry_date).days
            position.exit_reason = "end_of_data"
            trades.append(position)

        return self._compile_result(trades, equity_series, df)

    def _compile_result(
        self,
        trades: list[Trade],
        equity_series: list[dict[str, Any]],
        df: pd.DataFrame,
    ) -> BacktestResult:
        initial = self.capital
        final = equity_series[-1]["value"] if equity_series else initial
        total_return_pct = (final / initial - 1) * 100 if initial > 0 else 0.0

        benchmark_return_pct = 0.0
        benchmark_curve: list[dict[str, Any]] = []
        try:
            import yfinance as yf

            ihsg = yf.Ticker("^JKSE").history(start=df.index[0], end=df.index[-1], interval="1d")
            if not ihsg.empty:
                bm_start = float(ihsg["Close"].iloc[0])
                bm_end = float(ihsg["Close"].iloc[-1])
                benchmark_return_pct = (bm_end / bm_start - 1) * 100 if bm_start > 0 else 0.0
                for ts, row in ihsg.iterrows():
                    normalized = (float(row["Close"]) / bm_start) * initial if bm_start > 0 else initial
                    benchmark_curve.append({"time": ts.strftime("%Y-%m-%d"), "value": round(normalized, 2)})
        except Exception:
            pass

        vals = [float(e["value"]) for e in equity_series]
        returns: list[float] = []
        for i in range(1, len(vals)):
            if vals[i - 1] > 0:
                returns.append((vals[i] / vals[i - 1]) - 1)

        sharpe = 0.0
        if len(returns) > 1:
            avg_r = float(np.mean(returns))
            std_r = float(np.std(returns))
            sharpe = (avg_r / std_r) * (252**0.5) if std_r > 0 else 0.0

        max_dd = 0.0
        if vals:
            peak = vals[0]
            for v in vals:
                peak = max(peak, v)
                dd = (v - peak) / peak * 100 if peak > 0 else 0
                max_dd = min(max_dd, dd)

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0.0
        win_rate_frac = win_rate / 100

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        avg_win = float(np.mean([t.pnl_pct for t in wins])) if wins else 0.0
        avg_loss = float(np.mean([t.pnl_pct for t in losses])) if losses else 0.0
        avg_hold = float(np.mean([t.hold_days for t in trades])) if trades else 0.0
        best = max((t.pnl_pct for t in trades), default=0.0)
        worst = min((t.pnl_pct for t in trades), default=0.0)

        # ── BEI fee total ──────────────────────────────────────────────
        total_fees = 0.0
        if self.apply_bei_fees:
            for t in trades:
                buy_val = t.entry_price * t.shares
                sell_val = (t.exit_price or t.entry_price) * t.shares
                buy_fee = buy_val * (BEI_BUY_FEE_PCT + BEI_SLIPPAGE_PCT)
                sell_fee = sell_val * (BEI_SELL_FEE_PCT + BEI_SLIPPAGE_PCT)
                total_fees += buy_fee + sell_fee

        # ── Expectancy ─────────────────────────────────────────────────
        # Expected $ profit per trade = avg_win*P(win) - avg_loss*P(loss)
        avg_win_abs = float(np.mean([t.pnl for t in wins])) if wins else 0.0
        avg_loss_abs = float(np.mean([abs(t.pnl) for t in losses])) if losses else 0.0
        expectancy = avg_win_abs * win_rate_frac - avg_loss_abs * (1 - win_rate_frac)
        expectancy_pct = avg_win * win_rate_frac - abs(avg_loss) * (1 - win_rate_frac)

        # ── Calmar ratio ───────────────────────────────────────────────
        calmar = abs(total_return_pct / max_dd) if max_dd != 0 else 0.0

        # ── Monthly returns ───────────────────────────────────────────
        monthly_returns: list[dict[str, Any]] = []
        if equity_series:
            eq_df = pd.DataFrame(equity_series)
            eq_df["time"] = pd.to_datetime(eq_df["time"])
            eq_df = eq_df.set_index("time")["value"]
            monthly = eq_df.resample("ME").last()
            monthly_pct = monthly.pct_change() * 100
            for ts, ret in monthly_pct.dropna().items():
                monthly_returns.append({"month": ts.strftime("%Y-%m"), "return_pct": round(float(ret), 2)})

        return BacktestResult(
            symbol=self.symbol,
            strategy=self.strategy,
            period=f"{df.index[0].strftime('%Y-%m-%d')} \u2192 {df.index[-1].strftime('%Y-%m-%d')}",
            start_date=df.index[0].strftime("%Y-%m-%d"),
            end_date=df.index[-1].strftime("%Y-%m-%d"),
            total_return_pct=round(total_return_pct, 2),
            benchmark_return_pct=round(benchmark_return_pct, 2),
            alpha=round(total_return_pct - benchmark_return_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown_pct=round(max_dd, 2),
            profit_factor=round(profit_factor, 2),
            total_trades=len(trades),
            win_trades=len(wins),
            loss_trades=len(losses),
            win_rate=round(win_rate, 2),
            avg_win_pct=round(avg_win, 2),
            avg_loss_pct=round(avg_loss, 2),
            avg_hold_days=round(avg_hold, 1),
            best_trade_pct=round(best, 2),
            worst_trade_pct=round(worst, 2),
            equity_curve=equity_series,
            benchmark_curve=benchmark_curve,
            expectancy=round(expectancy, 0),
            expectancy_pct=round(expectancy_pct, 2),
            total_fees_paid=round(total_fees, 0),
            calmar_ratio=round(calmar, 2),
            monthly_returns=monthly_returns,
            trades=[
                {
                    "entry_date": t.entry_date.strftime("%Y-%m-%d"),
                    "exit_date": t.exit_date.strftime("%Y-%m-%d") if t.exit_date else None,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "shares": t.shares,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "hold_days": t.hold_days,
                    "exit_reason": t.exit_reason,
                }
                for t in trades
            ],
        )
