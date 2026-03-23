"""Background monitor - cek watchlist setiap 15 menit saat market buka."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from typing import Any

logger = logging.getLogger(__name__)

MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(16, 15)
INTERVAL_SEC = 15 * 60


def _market_is_open() -> bool:
    """Cek apakah market IDX sedang buka (Senin-Jumat, 09:00-16:15)."""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


class WatchlistMonitor:
    """Background monitor watchlist and send alerts."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            logger.info("WatchlistMonitor started")

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
        """Scan semua saham di watchlist."""
        from stockai.core.coach import analyze_entry
        from stockai.core.watchlist import get_watchlist
        from stockai.data.sources.yahoo import YahooFinanceSource
        from stockai.notifications.telegram import send_coach_alert

        watchlist = get_watchlist()
        stocks = watchlist.get_all()
        if not stocks:
            return

        yahoo = YahooFinanceSource()
        logger.info("Monitor: scanning %d stocks", len(stocks))
        ihsg_trend = await _get_ihsg_trend(yahoo)

        for stock in stocks:
            symbol = stock["symbol"]
            modal = int(stock.get("modal", 5_000_000))
            tujuan = str(stock.get("tujuan", "swing"))
            try:
                df = yahoo.get_price_history(symbol, period="3mo")
                if df.empty or len(df) < 30:
                    continue
                decision = await analyze_entry(
                    symbol=symbol,
                    df=df,
                    modal=modal,
                    tujuan=tujuan,
                    ihsg_trend=ihsg_trend,
                )
                watchlist.update_last_signal(symbol, decision.action)
                if decision.action == "ENTRY_NOW" and decision.confidence >= 60:
                    await send_coach_alert(decision)
                    logger.info(
                        "Alert sent: %s - %s (confidence %d%%)",
                        symbol, decision.action, decision.confidence,
                    )
            except Exception as exc:
                logger.warning("Scan %s failed: %s", symbol, exc)
            await asyncio.sleep(2)


async def _get_ihsg_trend(yahoo: Any) -> str:
    """Ambil trend IHSG hari ini."""
    _ = yahoo
    try:
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor

        def _fetch() -> str:
            ticker = yf.Ticker("^JKSE")
            hist = ticker.history(period="5d", interval="1d")
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
