"""Background monitor - smart scan watchlist setiap 8 menit saat market buka.

Data source: Yahoo Finance.
Flow:
1) Batch current price
2) Multi-timeframe confirmation (2m, 15m, 1d)
3) Coach analysis with market breadth + sentiment context
4) Telegram alert for high-confidence entry signals
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from typing import Any

logger = logging.getLogger(__name__)

MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(16, 15)
INTERVAL_SEC = 8 * 60
MAX_LOG_ITEMS = 500


def _market_is_open() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


class WatchlistMonitor:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_prices: dict[str, float] = {}
        self._decision_log: list[dict[str, Any]] = []
        self._alert_log: list[dict[str, Any]] = []
        self._last_market_context: dict[str, Any] | None = None
        self._last_market_context_at: datetime | None = None

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            logger.info("WatchlistMonitor started - Yahoo 2m interval, scan tiap 8 menit")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("WatchlistMonitor stopped")

    def get_recent_decisions(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._decision_log[-limit:]

    def get_recent_alerts(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._alert_log[-limit:]

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "interval_sec": INTERVAL_SEC,
            "last_market_context_at": (
                self._last_market_context_at.isoformat() if self._last_market_context_at else None
            ),
            "last_market_context": self._last_market_context,
            "decisions_logged": len(self._decision_log),
            "alerts_logged": len(self._alert_log),
        }

    async def _loop(self) -> None:
        while self._running:
            try:
                if _market_is_open():
                    await self._scan_all()
                else:
                    logger.debug("Market tutup, skip scan")
            except Exception as exc:
                logger.error("Monitor loop error: %s", exc)
            await asyncio.sleep(INTERVAL_SEC)

    def _append_decision_log(self, item: dict[str, Any]) -> None:
        self._decision_log.append(item)
        if len(self._decision_log) > MAX_LOG_ITEMS:
            self._decision_log = self._decision_log[-MAX_LOG_ITEMS:]

    def _append_alert_log(self, item: dict[str, Any]) -> None:
        self._alert_log.append(item)
        if len(self._alert_log) > MAX_LOG_ITEMS:
            self._alert_log = self._alert_log[-MAX_LOG_ITEMS:]

    def _trend_bias(self, df: Any) -> str:
        """Return BULLISH/BEARISH/NEUTRAL using EMA8 vs EMA21 and RSI."""
        import numpy as np
        import pandas as pd

        if df is None or getattr(df, "empty", True):
            return "NEUTRAL"
        data = df.copy()
        data.columns = [str(c).lower() for c in data.columns]
        if "close" not in data.columns:
            return "NEUTRAL"
        close = data["close"]
        if len(close) < 30:
            return "NEUTRAL"

        ema8 = close.ewm(span=8, adjust=False).mean().iloc[-1]
        ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = float((100 - 100 / (1 + rs)).iloc[-1])

        if ema8 > ema21 and rsi < 70:
            return "BULLISH"
        if ema8 < ema21 or rsi > 75:
            return "BEARISH"
        return "NEUTRAL"

    async def _get_market_context(self, yahoo: Any) -> dict[str, Any]:
        """Compute breadth + sector rotation from IDX30 (cached for 10 minutes)."""
        from stockai.data.listings import get_stock_database

        now = datetime.now()
        if (
            self._last_market_context
            and self._last_market_context_at
            and (now - self._last_market_context_at).total_seconds() < 600
        ):
            return self._last_market_context

        db = get_stock_database()
        idx30 = db.get_idx30_stocks()
        symbols = [row["symbol"] for row in idx30]
        loop = asyncio.get_running_loop()

        prices = await loop.run_in_executor(None, lambda: yahoo.get_multiple_prices(symbols))
        adv = 0
        dec = 0
        sector_moves: dict[str, list[float]] = {}
        for row in idx30:
            symbol = row["symbol"]
            sector = row.get("sector", "Unknown")
            current = prices.get(symbol, {})
            try:
                pct = float(current.get("change_percent") or 0.0)
            except Exception:
                pct = 0.0
            if pct > 0:
                adv += 1
            elif pct < 0:
                dec += 1
            sector_moves.setdefault(sector, []).append(pct)

        total = max(1, adv + dec)
        advance_ratio = adv / total
        if advance_ratio >= 0.6:
            breadth = "RISK_ON"
        elif advance_ratio <= 0.4:
            breadth = "RISK_OFF"
        else:
            breadth = "MIXED"

        sector_avg = {
            sector: (sum(changes) / len(changes))
            for sector, changes in sector_moves.items()
            if changes
        }
        leading_sector = max(sector_avg, key=sector_avg.get) if sector_avg else "UNKNOWN"
        lagging_sector = min(sector_avg, key=sector_avg.get) if sector_avg else "UNKNOWN"

        ctx = {
            "ihsg_trend": await _get_ihsg_trend(),
            "market_breadth": breadth,
            "advance_ratio": round(advance_ratio, 2),
            "leading_sector": leading_sector,
            "lagging_sector": lagging_sector,
            "advancers": adv,
            "decliners": dec,
        }
        self._last_market_context = ctx
        self._last_market_context_at = now
        return ctx

    async def _scan_all(self) -> None:
        from stockai.core.decision_engine import generate_unified_decision
        from stockai.core.realtime import get_realtime_pipeline
        from stockai.core.sentiment.stockbit import StockbitSentiment
        from stockai.core.watchlist import get_watchlist
        from stockai.data.sources.yahoo import YahooFinanceSource
        from stockai.notifications.telegram import send_coach_alert

        watchlist = get_watchlist()
        stocks = watchlist.get_all()
        if not stocks:
            return

        yahoo = YahooFinanceSource()
        realtime = get_realtime_pipeline()
        sentiment_engine = StockbitSentiment()
        symbols = [s["symbol"] for s in stocks]
        loop = asyncio.get_running_loop()

        logger.info("Monitor: scanning %d stocks (Yahoo MTF)", len(symbols))

        try:
            batch = await loop.run_in_executor(None, lambda: yahoo.get_multiple_prices(symbols))
        except Exception as exc:
            logger.warning("Batch price check gagal: %s", exc)
            return

        market_ctx = await self._get_market_context(yahoo)
        ihsg_trend = market_ctx.get("ihsg_trend", "UNKNOWN")

        for stock in stocks:
            symbol = stock["symbol"]
            modal = stock.get("modal", 5_000_000)
            tujuan = stock.get("tujuan", "swing")

            try:
                current = batch.get(symbol, {})
                current_price = float(current.get("price") or 0)
                if current_price <= 0:
                    logger.debug("%s: no price, skip", symbol)
                    continue

                last = self._last_prices.get(symbol, 0)
                if last > 0:
                    move = abs(current_price / last - 1) * 100
                    if move < 0.5:
                        logger.debug("%s: move %.2f%% < 0.5%%, skip", symbol, move)
                        continue

                self._last_prices[symbol] = current_price

                df_daily = await loop.run_in_executor(
                    None,
                    lambda s=symbol: yahoo.get_price_history(s, period="3mo", interval="1d"),
                )
                if df_daily.empty or len(df_daily) < 30:
                    logger.debug("%s: data tidak cukup", symbol)
                    continue

                df_15m = await loop.run_in_executor(
                    None,
                    lambda s=symbol: yahoo.get_price_history(s, period="1mo", interval="15m"),
                )
                df_2m = await loop.run_in_executor(
                    None,
                    lambda s=symbol: yahoo.get_price_history(s, period="5d", interval="2m"),
                )

                if current_price > 0 and not df_daily.empty:
                    df_daily = df_daily.copy()
                    df_daily.loc[df_daily.index[-1], "close"] = current_price
                if current_price > 0 and not df_15m.empty:
                    df_15m = df_15m.copy()
                    df_15m.loc[df_15m.index[-1], "close"] = current_price
                if current_price > 0 and not df_2m.empty:
                    df_2m = df_2m.copy()
                    df_2m.loc[df_2m.index[-1], "close"] = current_price

                trend_1d = self._trend_bias(df_daily)
                trend_15m = self._trend_bias(df_15m)
                trend_2m = self._trend_bias(df_2m)
                score_map = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}
                mtf_score = score_map[trend_1d] + score_map[trend_15m] + score_map[trend_2m]

                sentiment_signal = await loop.run_in_executor(None, lambda s=symbol: sentiment_engine.analyze(s))
                sentiment_label = str(sentiment_signal.get("sentiment", "NEUTRAL")).upper()
                sentiment_raw = float(sentiment_signal.get("score", 0))
                sentiment_score = max(0.0, min(100.0, 50.0 + sentiment_raw * 5.0))
                news_bias = (
                    "POSITIVE" if sentiment_label == "BULLISH"
                    else "NEGATIVE" if sentiment_label == "BEARISH"
                    else "NEUTRAL"
                )

                decision = await generate_unified_decision(
                    symbol=symbol,
                    df=df_daily,
                    modal=modal,
                    tujuan=tujuan,
                    ihsg_trend=ihsg_trend,
                    sentiment_label=sentiment_label,
                    sentiment_score=sentiment_score,
                    news_bias=news_bias,
                    market_breadth=str(market_ctx.get("market_breadth", "MIXED")),
                    advance_ratio=float(market_ctx.get("advance_ratio", 0.5)),
                    leading_sector=str(market_ctx.get("leading_sector", "UNKNOWN")),
                    lagging_sector=str(market_ctx.get("lagging_sector", "UNKNOWN")),
                    mtf_score=mtf_score,
                )

                watchlist.update_last_signal(symbol, decision.action)
                logger.info(
                    "%s -> %s (confidence %d%%, MTF %s/%s/%s, IHSG: %s)",
                    symbol, decision.action, decision.confidence, trend_2m, trend_15m, trend_1d, ihsg_trend
                )

                self._append_decision_log(
                    {
                        "time": datetime.now().isoformat(),
                        "symbol": symbol,
                        "action": decision.action,
                        "confidence": decision.confidence,
                        "modal": modal,
                        "tujuan": tujuan,
                        "price": current_price,
                        "ihsg_trend": ihsg_trend,
                        "market_breadth": market_ctx.get("market_breadth"),
                        "advance_ratio": market_ctx.get("advance_ratio"),
                        "leading_sector": market_ctx.get("leading_sector"),
                        "lagging_sector": market_ctx.get("lagging_sector"),
                        "trend_2m": trend_2m,
                        "trend_15m": trend_15m,
                        "trend_1d": trend_1d,
                        "mtf_score": mtf_score,
                        "sentiment_label": sentiment_label,
                        "sentiment_score": round(sentiment_score, 1),
                        "reason_entry": decision.reason_entry[:3],
                        "warning": decision.warning[:2],
                    }
                )
                realtime.publish(
                    {
                        "type": "monitor_decision",
                        "symbol": symbol,
                        "action": decision.action,
                        "confidence": decision.confidence,
                        "price": current_price,
                        "mtf_score": mtf_score,
                        "market_breadth": market_ctx.get("market_breadth"),
                        "sentiment_label": sentiment_label,
                    }
                )

                if decision.action == "ENTRY_NOW" and decision.confidence >= 60:
                    await send_coach_alert(decision)
                    logger.info("🔔 Alert sent: %s", symbol)
                    self._append_alert_log(
                        {
                            "time": datetime.now().isoformat(),
                            "symbol": symbol,
                            "action": decision.action,
                            "confidence": decision.confidence,
                            "entry_low": decision.entry_low,
                            "entry_high": decision.entry_high,
                            "stop_loss": decision.stop_loss,
                            "target1": decision.target1,
                            "risk_reward": decision.risk_reward,
                        }
                    )
                    realtime.publish(
                        {
                            "type": "telegram_alert",
                            "symbol": symbol,
                            "action": decision.action,
                            "confidence": decision.confidence,
                            "entry_low": decision.entry_low,
                            "entry_high": decision.entry_high,
                            "stop_loss": decision.stop_loss,
                            "target1": decision.target1,
                        }
                    )

            except Exception as exc:
                logger.warning("Scan %s error: %s", symbol, exc)

            await asyncio.sleep(1.5)


async def _get_ihsg_trend() -> str:
    """Ambil trend IHSG hari ini via Yahoo."""
    try:
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor

        def _fetch():
            hist = yf.Ticker("^JKSE").history(period="5d", interval="1d")
            if len(hist) < 2:
                return "UNKNOWN"
            last = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            pct = (last / prev - 1) * 100
            return "UP" if pct > 0.3 else "DOWN" if pct < -0.3 else "SIDEWAYS"

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, _fetch)
    except Exception:
        return "UNKNOWN"


_monitor: WatchlistMonitor | None = None


def get_monitor() -> WatchlistMonitor:
    global _monitor
    if _monitor is None:
        _monitor = WatchlistMonitor()
    return _monitor
