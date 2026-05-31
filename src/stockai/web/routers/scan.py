"""Scan router — /scan/last and /scan/stream."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from stockai.web.utils import (
    _WEB_RUNTIME,
    _build_signal_event,
    _get_index_symbols,
    _is_scan_cache_fresh,
    _now_iso,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scan"])


@router.get("/scan/last")
async def get_last_scan() -> dict:
    if not _is_scan_cache_fresh():
        return {"available": False, "message": "No recent scan"}
    last_scan = _WEB_RUNTIME.get("last_scan") or {}
    return {"available": True, **last_scan}


@router.get("/scan/stream")
async def scan_stream(index: str = Query("ALL", description="Index name")) -> StreamingResponse:
    symbols = _get_index_symbols(index)

    async def generate():
        results: list[dict[str, Any]] = []
        total = len(symbols)
        for i, symbol in enumerate(symbols, start=1):
            progress = {
                "scanned": i,
                "total": total,
                "percent": round(i / total * 100, 2) if total else 100,
                "current_symbol": symbol,
            }
            payload: dict[str, Any] = {
                "progress": progress,
                "result": None,
                "timestamp": _now_iso(),
            }
            try:
                event_result = await asyncio.to_thread(_build_signal_event, symbol)
                payload["result"] = event_result
                results.append(event_result)
            except Exception as exc:
                payload["error"] = str(exc)
                logger.debug("scan stream skip %s: %s", symbol, exc)
            yield f"data: {json.dumps(payload, default=str)}\n\n"
            await asyncio.sleep(0)

        summary = {
            "index": index.upper(),
            "scanned": total,
            "timestamp": _now_iso(),
            "results": results,
        }
        _WEB_RUNTIME["last_scan"] = summary
        _WEB_RUNTIME["last_scan_at"] = datetime.utcnow()
        yield f"data: {json.dumps({'event': 'completed', 'summary': summary}, default=str)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
