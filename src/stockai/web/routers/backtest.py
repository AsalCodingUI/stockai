"""Backtest router — all /backtest/* endpoints."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from stockai.core.backtest import BacktestEngine, STRATEGY_MAP
from stockai.data.sources.yahoo import YahooFinanceSource
from stockai.web.utils import _get_index_symbols, _to_native

router = APIRouter(tags=["backtest"])


@router.get("/backtest/{symbol}")
async def run_backtest(
    symbol: str,
    strategy: str = Query("ema_cross", description="ema_cross | macd_momentum | gate_system"),
    period: str = Query("1y", description="6mo | 1y | 2y | 3y | 5y"),
    sl_pct: float = Query(0.07, description="Stop loss % (default 7%)"),
    tp_pct: float = Query(0.15, description="Take profit % (default 15%)"),
) -> dict:
    """Run backtest for a single stock."""
    clean = symbol.upper().strip()
    if strategy not in STRATEGY_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy: {strategy}. Valid: {list(STRATEGY_MAP.keys())}",
        )

    yahoo = YahooFinanceSource()
    df = yahoo.get_price_history(clean, period=period)
    if df.empty or len(df) < 60:
        raise HTTPException(status_code=404, detail=f"Insufficient data for {clean}")

    df_engine = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    if "date" in df_engine.columns:
        df_engine = df_engine.set_index("date")

    try:
        engine = BacktestEngine(
            symbol=clean,
            df=df_engine,
            strategy=strategy,
            stop_loss_pct=sl_pct,
            take_profit_pct=tp_pct,
        )
        result = await asyncio.to_thread(engine.run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}") from exc

    return _to_native(result.__dict__)


@router.get("/backtest/scan/stream")
async def backtest_scan_stream(
    index: str = Query("IDX30", description="IDX30 | LQ45 | ALL"),
    strategy: str = Query("ema_cross", description="Strategy name"),
    period: str = Query("1y", description="Backtest period"),
    min_winrate: float = Query(50.0, description="Filter min win rate %"),
) -> StreamingResponse:
    """Stream bulk backtest results sorted by total return."""
    if strategy not in STRATEGY_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy: {strategy}. Valid: {list(STRATEGY_MAP.keys())}",
        )

    symbols = _get_index_symbols(index)
    yahoo = YahooFinanceSource()

    async def generate():
        results: list[dict[str, Any]] = []
        total = len(symbols)

        for i, symbol in enumerate(symbols, start=1):
            progress = {
                "scanned": i,
                "total": total,
                "percent": round(i / total * 100, 1) if total else 100.0,
                "current_symbol": symbol,
            }
            payload: dict[str, Any] = {"progress": progress, "result": None}

            try:
                df = yahoo.get_price_history(symbol, period=period)
                if df.empty or len(df) < 60:
                    raise ValueError("Insufficient data")

                df_engine = df.rename(
                    columns={
                        "open": "Open",
                        "high": "High",
                        "low": "Low",
                        "close": "Close",
                        "volume": "Volume",
                    }
                )
                if "date" in df_engine.columns:
                    df_engine = df_engine.set_index("date")

                engine = BacktestEngine(symbol=symbol, df=df_engine, strategy=strategy)
                result = await asyncio.to_thread(engine.run)

                if result.win_rate >= min_winrate:
                    summary = {
                        "symbol": result.symbol,
                        "total_return_pct": result.total_return_pct,
                        "benchmark_return_pct": result.benchmark_return_pct,
                        "alpha": result.alpha,
                        "win_rate": result.win_rate,
                        "total_trades": result.total_trades,
                        "sharpe_ratio": result.sharpe_ratio,
                        "max_drawdown_pct": result.max_drawdown_pct,
                        "profit_factor": result.profit_factor,
                    }
                    payload["result"] = summary
                    results.append(summary)
            except Exception as exc:
                payload["error"] = str(exc)

            yield f"data: {json.dumps(_to_native(payload))}\n\n"
            await asyncio.sleep(0)

        results.sort(key=lambda x: x["total_return_pct"], reverse=True)
        yield f"data: {json.dumps({'event': 'completed', 'results': results[:50]})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
