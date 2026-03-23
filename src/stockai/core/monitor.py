"""Background monitor - smart scan watchlist setiap 8 menit saat market buka."""

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
            logger.info("WatchlistMonitor started (interval: 8 menit)")

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

    def _get_source(self):
        """Pilih Twelve Data kalau ada key, fallback Yahoo."""
        from stockai.config import get_settings

        settings = get_settings()
        if settings.has_twelve_data_api:
            from stockai.data.sources.twelve import get_twelve_source

            logger.debug("Source: Twelve Data (~1 min delay)")
            return get_twelve_source()
        from stockai.data.sources.yahoo import YahooFinanceSource

        logger.debug("Source: Yahoo Finance (~15 min delay)")
        return YahooFinanceSource()

    async def _scan_all(self) -> None:
        from stockai.core.coach import analyze_entry
        from stockai.core.watchlist import get_watchlist
        from stockai.notifications.telegram import send_coach_alert

        watchlist = get_watchlist()
        stocks = watchlist.get_all()
        if not stocks:
            return

        source = self._get_source()
        symbols = [s["symbol"] for s in stocks]
        logger.info("Monitor: scanning %d stocks", len(symbols))

        try:
            loop = asyncio.get_running_loop()
            batch_prices = await loop.run_in_executor(None, lambda: source.get_multiple_prices(symbols))
        except Exception as exc:
            logger.warning("Batch price check failed, skip scan: %s", exc)
            return

        # Graceful fallback: jika Twelve tidak bisa ambil data (quota/plan restriction),
        # otomatis fallback ke Yahoo agar monitor tetap jalan.
        if not batch_prices:
            try:
                from stockai.data.sources.twelve import TwelveDataSource
                if isinstance(source, TwelveDataSource):
                    from stockai.data.sources.yahoo import YahooFinanceSource
                    logger.warning("Twelve returned empty batch, fallback to Yahoo source")
                    source = YahooFinanceSource()
                    batch_prices = await loop.run_in_executor(None, lambda: source.get_multiple_prices(symbols))
            except Exception as exc:
                logger.warning("Fallback to Yahoo failed: %s", exc)
                batch_prices = {}

        if not batch_prices:
            logger.warning("No batch prices available from all sources, skip scan")
            return

        ihsg_trend = await _get_ihsg_trend()

        for stock in stocks:
            symbol = stock["symbol"]
            modal = stock.get("modal", 5_000_000)
            tujuan = stock.get("tujuan", "swing")

            try:
                current = batch_prices.get(symbol)
                if not current:
                    logger.debug("No price data for %s, skip", symbol)
                    continue

                current_price = float(current.get("price", 0))
                if current_price <= 0:
                    continue

                last_price = self._last_prices.get(symbol, 0)
                if last_price > 0:
                    move_pct = abs(current_price / last_price - 1) * 100
                    if move_pct < 0.5:
                        logger.debug("%s move %.2f%% < 0.5%%, skip full analysis", symbol, move_pct)
                        continue

                self._last_prices[symbol] = current_price

                df = await loop.run_in_executor(None, lambda s=symbol: source.get_price_history(s, period="3mo"))
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
                    logger.info("🔔 Alert: %s ENTRY_NOW (confidence %d%%)", symbol, decision.confidence)
            except Exception as exc:
                logger.warning("Scan %s failed: %s", symbol, exc)

            await asyncio.sleep(1.5)


async def _get_ihsg_trend() -> str:
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
