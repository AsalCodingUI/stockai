"""Watchlist storage - JSON file based, no auth required."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WATCHLIST_FILE = Path.home() / ".stockai" / "watchlist.json"
MAX_WATCHLIST = 10


class WatchlistManager:
    """Manage watchlist stored locally as JSON."""

    def __init__(self, path: Path = WATCHLIST_FILE):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"stocks": [], "updated_at": None}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"stocks": [], "updated_at": None}

    def _save(self, data: dict[str, Any]) -> None:
        data["updated_at"] = datetime.now().isoformat()
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_all(self) -> list[dict[str, Any]]:
        return self._load().get("stocks", [])

    def get_symbols(self) -> list[str]:
        return [s["symbol"] for s in self.get_all()]

    def add(self, symbol: str, modal: int = 5_000_000, tujuan: str = "swing") -> dict[str, Any]:
        """Add stock to watchlist with modal and tujuan context."""
        data = self._load()
        stocks = data.get("stocks", [])

        symbol = symbol.upper().strip()
        if any(s["symbol"] == symbol for s in stocks):
            return {"success": False, "reason": f"{symbol} sudah ada di watchlist"}

        if len(stocks) >= MAX_WATCHLIST:
            return {
                "success": False,
                "reason": f"Watchlist penuh (max {MAX_WATCHLIST} saham)",
            }

        stocks.append(
            {
                "symbol": symbol,
                "modal": int(modal),
                "tujuan": tujuan,
                "added_at": datetime.now().isoformat(),
                "last_alert": None,
                "last_signal": None,
            }
        )
        data["stocks"] = stocks
        self._save(data)
        return {"success": True, "symbol": symbol, "total": len(stocks)}

    def remove(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper().strip()
        data = self._load()
        stocks = data.get("stocks", [])
        before = len(stocks)
        stocks = [s for s in stocks if s["symbol"] != symbol]
        if len(stocks) == before:
            return {"success": False, "reason": f"{symbol} tidak ada di watchlist"}
        data["stocks"] = stocks
        self._save(data)
        return {"success": True, "symbol": symbol}

    def update_last_signal(self, symbol: str, signal: str) -> None:
        symbol = symbol.upper().strip()
        data = self._load()
        for stock in data.get("stocks", []):
            if stock["symbol"] == symbol:
                stock["last_signal"] = signal
                stock["last_alert"] = datetime.now().isoformat()
                break
        self._save(data)

    def get_stock(self, symbol: str) -> dict[str, Any] | None:
        symbol = symbol.upper().strip()
        return next((s for s in self.get_all() if s["symbol"] == symbol), None)


_manager: WatchlistManager | None = None


def get_watchlist() -> WatchlistManager:
    global _manager
    if _manager is None:
        _manager = WatchlistManager()
    return _manager
