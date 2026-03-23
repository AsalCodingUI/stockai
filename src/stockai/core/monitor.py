"""Background monitor - smart scan watchlist setiap 8 menit saat market buka.

Data source: Yahoo Finance interval 2m (delay ~2-3 menit, gratis, support IDX).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time

logger = logging.getLogger(__name__)

MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(16, 15)
INTERVAL_SEC = 8 * 60


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

    async def _scan_all(self) -> None:
        from stockai.core.coach import analyze_entry
        from stockai.core.watchlist import get_watchlist
        from stockai.data.sources.yahoo import YahooFinanceSource
        from stockai.notifications.telegram import send_coach_alert

        watchlist = get_watchlist()
        stocks = watchlist.get_all()
        if not stocks:
            return

        yahoo = YahooFinanceSource()
        symbols = [s["symbol"] for s in stocks]
        loop = asyncio.get_running_loop()

        logger.info("Monitor: scanning %d stocks (Yahoo 2m)", len(symbols))

        try:
            batch = await loop.run_in_executor(None, lambda: yahoo.get_multiple_prices(symbols))
        except Exception as exc:
            logger.warning("Batch price check gagal: %s", exc)
            return

        ihsg_trend = await _get_ihsg_trend()

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

                if current_price > 0 and not df_daily.empty:
                    df_daily = df_daily.copy()
                    df_daily.loc[df_daily.index[-1], "close"] = current_price

                decision = await analyze_entry(
                    symbol=symbol,
                    df=df_daily,
                    modal=modal,
                    tujuan=tujuan,
                    ihsg_trend=ihsg_trend,
                )

                watchlist.update_last_signal(symbol, decision.action)
                logger.info(
                    "%s -> %s (confidence %d%%, IHSG: %s)",
                    symbol, decision.action, decision.confidence, ihsg_trend
                )

                if decision.action == "ENTRY_NOW" and decision.confidence >= 60:
                    await send_coach_alert(decision)
                    logger.info("🔔 Alert sent: %s", symbol)

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
