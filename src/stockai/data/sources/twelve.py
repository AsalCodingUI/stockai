"""Twelve Data source for Indonesian stocks - ~1 min delay, free tier 800 req/day."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "https://api.twelvedata.com"

PERIOD_MAP = {
    "1d": ("1min", "390"),
    "5d": ("5min", "390"),
    "1mo": ("1day", "30"),
    "3mo": ("1day", "90"),
    "6mo": ("1day", "180"),
    "1y": ("1day", "365"),
    "2y": ("1day", "730"),
    "3y": ("1day", "1095"),
    "5y": ("1day", "1825"),
}


class TwelveDataSource:
    """Twelve Data source with interface mirroring YahooFinanceSource."""

    EXCHANGE = "IDX"

    def __init__(self, api_key: str | None = None):
        if api_key is None:
            from stockai.config import get_settings

            api_key = get_settings().twelve_data_api_key
        if not api_key:
            raise ValueError("TWELVE_DATA_API_KEY tidak ditemukan di .env / .env.local")
        self._api_key = api_key
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = 60

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        params = dict(params)
        params["apikey"] = self._api_key
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(f"{BASE_URL}/{endpoint}", params=params)
                resp.raise_for_status()
                data = resp.json()
            if isinstance(data, dict) and data.get("status") == "error":
                raise ValueError(f"Twelve Data error: {data.get('message', 'unknown')}")
            if not isinstance(data, dict):
                raise ValueError("Unexpected Twelve Data response format")
            return data
        except httpx.HTTPStatusError as exc:
            logger.error("Twelve Data HTTP error %s: %s", exc.response.status_code, exc)
            raise
        except Exception as exc:
            logger.error("Twelve Data request failed: %s", exc)
            raise

    def _cached_get(self, cache_key: str, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        now = time.monotonic()
        if cache_key in self._cache:
            ts, data = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return data
        data = self._get(endpoint, params)
        self._cache[cache_key] = (now, data)
        return data

    def get_price_history(
        self,
        symbol: str,
        period: str = "3mo",
        interval: str = "1d",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Get OHLCV history in Yahoo-like dataframe schema."""
        symbol = symbol.upper().strip().replace(".JK", "")

        if interval == "1d":
            td_interval = "1day"
        elif interval in ("1h", "60m"):
            td_interval = "1h"
        elif interval == "15m":
            td_interval = "15min"
        elif interval == "5m":
            td_interval = "5min"
        elif interval == "1m":
            td_interval = "1min"
        else:
            td_interval = "1day"

        if start is not None:
            output_size = "5000"
        else:
            _, output_size = PERIOD_MAP.get(period, ("1day", "90"))

        params: dict[str, str] = {
            "symbol": symbol,
            "exchange": self.EXCHANGE,
            "interval": td_interval,
            "outputsize": output_size,
            "format": "JSON",
            "order": "ASC",
        }

        if start is not None:
            params["start_date"] = start.strftime("%Y-%m-%d %H:%M:%S")
        if end is not None:
            params["end_date"] = end.strftime("%Y-%m-%d %H:%M:%S")

        cache_key = f"history:{symbol}:{td_interval}:{output_size}"
        try:
            data = self._cached_get(cache_key, "time_series", params)
        except Exception as exc:
            logger.warning("Twelve Data history failed for %s: %s", symbol, exc)
            return pd.DataFrame()

        values = data.get("values", [])
        if not values:
            logger.warning("Twelve Data: no values for %s", symbol)
            return pd.DataFrame()

        df = pd.DataFrame(values)
        df = df.rename(
            columns={
                "datetime": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
        )
        df["date"] = pd.to_datetime(df["date"])
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        df["symbol"] = symbol

        df = df.sort_values("date").reset_index(drop=True)
        if start is not None:
            df = df[df["date"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["date"] <= pd.Timestamp(end)]

        cols = ["symbol", "date", "open", "high", "low", "close", "volume"]
        return df[[c for c in cols if c in df.columns]]

    def get_current_price(self, symbol: str) -> dict[str, Any] | None:
        """Get latest price snapshot."""
        symbol = symbol.upper().strip().replace(".JK", "")
        cache_key = f"price:{symbol}"
        try:
            data = self._cached_get(
                cache_key,
                "price",
                {"symbol": symbol, "exchange": self.EXCHANGE},
            )
            price = float(data.get("price", 0))
            if price <= 0:
                return None

            quote = self._get("quote", {"symbol": symbol, "exchange": self.EXCHANGE})
            change = float(quote.get("change", 0))
            change_pct = float(quote.get("percent_change", 0))
            volume = int(float(quote.get("volume", 0) or 0))

            return {
                "symbol": symbol,
                "price": price,
                "change": change,
                "change_percent": change_pct,
                "volume": volume,
                "market_time": datetime.now(),
            }
        except Exception as exc:
            logger.warning("Twelve Data current price failed for %s: %s", symbol, exc)
            return None

    def get_multiple_prices(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Batch price fetch for multiple symbols."""
        if not symbols:
            return {}

        clean = [s.upper().strip().replace(".JK", "") for s in symbols]
        symbol_str = ",".join(clean)

        try:
            data = self._get("price", {"symbol": symbol_str, "exchange": self.EXCHANGE})
            results: dict[str, dict[str, Any]] = {}
            if len(clean) == 1:
                price = float(data.get("price", 0))
                if price > 0:
                    results[clean[0]] = {
                        "symbol": clean[0],
                        "price": price,
                        "change": 0.0,
                        "change_percent": 0.0,
                        "volume": 0,
                        "market_time": datetime.now(),
                    }
            else:
                for sym in clean:
                    sym_data = data.get(sym, {})
                    if not isinstance(sym_data, dict):
                        continue
                    price = float(sym_data.get("price", 0))
                    if price > 0:
                        results[sym] = {
                            "symbol": sym,
                            "price": price,
                            "change": 0.0,
                            "change_percent": 0.0,
                            "volume": 0,
                            "market_time": datetime.now(),
                        }
            return results
        except Exception as exc:
            logger.warning("Twelve Data batch price failed: %s", exc)
            return {}

    def get_stock_info(self, symbol: str) -> dict[str, Any] | None:
        """Get company profile."""
        symbol = symbol.upper().strip().replace(".JK", "")
        try:
            data = self._get("profile", {"symbol": symbol, "exchange": self.EXCHANGE})
            if not data or data.get("status") == "error":
                return None
            return {
                "symbol": symbol,
                "name": data.get("name", ""),
                "sector": data.get("sector", ""),
                "industry": data.get("industry", ""),
                "description": data.get("description", ""),
                "exchange": data.get("exchange", "IDX"),
                "currency": data.get("currency", "IDR"),
                "market_cap": None,
            }
        except Exception as exc:
            logger.warning("Twelve Data profile failed for %s: %s", symbol, exc)
            return None

    def validate_symbol(self, symbol: str) -> bool:
        return self.get_current_price(symbol) is not None


_instance: TwelveDataSource | None = None


def get_twelve_source() -> TwelveDataSource:
    global _instance
    if _instance is None:
        _instance = TwelveDataSource()
    return _instance
