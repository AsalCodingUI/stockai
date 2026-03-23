"""Backtest engine for StockAI strategies."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


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


STRATEGY_MAP = {
    "ema_cross": _signals_ema_cross,
    "macd_momentum": _signals_macd_momentum,
    "gate_system": _signals_gate_system,
}


class BacktestEngine:
    """Vectorized backtest engine with SL/TP and single open-position model."""

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
    ):
        self.symbol = symbol
        self.df = df.copy()
        self.strategy = strategy
        self.capital = initial_capital or self.INITIAL_CAPITAL
        self.sl_pct = stop_loss_pct or self.STOP_LOSS_PCT
        self.tp_pct = take_profit_pct or self.TAKE_PROFIT_PCT
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
                    exit_price = price
                    pnl = (exit_price - position.entry_price) * position.shares
                    pnl_pct = (exit_price / position.entry_price - 1) * 100
                    hold_days = (date - position.entry_date).days

                    position.exit_date = date
                    position.exit_price = exit_price
                    position.pnl = round(pnl, 2)
                    position.pnl_pct = round(pnl_pct, 2)
                    position.hold_days = hold_days
                    position.exit_reason = (
                        "stop_loss" if hit_sl else "take_profit" if hit_tp else "signal"
                    )

                    capital += position.shares * exit_price
                    trades.append(position)
                    position = None

            if position is None and signal == "BUY" and capital > 0:
                invest = capital * self.POSITION_SIZE_PCT
                shares = int(invest / price / 100) * 100
                if shares > 0:
                    cost = shares * price
                    capital -= cost
                    position = Trade(
                        symbol=self.symbol,
                        entry_date=date,
                        entry_price=price,
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
        try:
            import yfinance as yf

            ihsg = yf.Ticker("^JKSE").history(start=df.index[0], end=df.index[-1], interval="1d")
            if not ihsg.empty:
                bm_start = float(ihsg["Close"].iloc[0])
                bm_end = float(ihsg["Close"].iloc[-1])
                benchmark_return_pct = (bm_end / bm_start - 1) * 100 if bm_start > 0 else 0.0
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

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        avg_win = float(np.mean([t.pnl_pct for t in wins])) if wins else 0.0
        avg_loss = float(np.mean([t.pnl_pct for t in losses])) if losses else 0.0
        avg_hold = float(np.mean([t.hold_days for t in trades])) if trades else 0.0
        best = max((t.pnl_pct for t in trades), default=0.0)
        worst = min((t.pnl_pct for t in trades), default=0.0)

        benchmark_curve: list[dict[str, Any]] = []
        try:
            import yfinance as yf

            ihsg = yf.Ticker("^JKSE").history(start=df.index[0], end=df.index[-1], interval="1d")
            if not ihsg.empty:
                bm_start = float(ihsg["Close"].iloc[0])
                for ts, row in ihsg.iterrows():
                    normalized = (float(row["Close"]) / bm_start) * initial if bm_start > 0 else initial
                    benchmark_curve.append({"time": ts.strftime("%Y-%m-%d"), "value": round(normalized, 2)})
        except Exception:
            pass

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
