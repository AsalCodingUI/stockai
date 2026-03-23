"""Web Routes for StockAI Dashboard.

API and page routes for the web interface.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
import statistics
from typing import Any

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import numpy as np
import pandas as pd

from stockai import __version__
from stockai.config import get_settings
from stockai.core.predictor import EnsemblePredictor, PredictionAccuracyTracker
from stockai.data.cache import async_cached
from stockai.data.cache import memory_cache_get, memory_cache_set
from stockai.data.database import init_database
from stockai.data.listings import ALL_IDX_STOCKS
from stockai.data.sources.yahoo import YahooFinanceSource
from stockai.data.sources.idx import IDXIndexSource
from stockai.scoring.analyzer import analyze_stock, GateConfig
from stockai.core.foreign_flow import ForeignFlowMonitor
from stockai.core.volume_detector import UnusualVolumeDetector
from stockai.core.sentiment.stockbit import StockbitSentiment
from stockai.core.ml.probability import ProbabilityEngine
from stockai.web.schemas import (
    WatchlistDeleteResponse,
    WatchlistItemCreate,
    WatchlistItemListResponse,
    WatchlistItemResponse,
    WatchlistItemUpdate,
)
from stockai.web.services.watchlist import (
    add_to_watchlist,
    get_watchlist_items,
    get_watchlist_item_by_id,
    remove_from_watchlist,
    remove_from_watchlist_by_symbol,
    update_watchlist_item,
    WatchlistItemExistsError,
    WatchlistItemNotFoundError,
)

logger = logging.getLogger(__name__)


SCAN_LAST_TTL_SECONDS = 15 * 60
ALERT_DISMISS_TTL_SECONDS = 6 * 60 * 60
PORTFOLIO_META_TTL_SECONDS = 24 * 60 * 60

_WEB_RUNTIME: dict[str, Any] = {
    "last_scan": None,
    "last_scan_at": None,
    "alerts_dismissed_until": None,
    "portfolio_meta": {},
}

# API Router
api_router = APIRouter(tags=["api"])

# Pages Router
pages_router = APIRouter(tags=["pages"])


class PortfolioPositionCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    shares: int = Field(gt=0)
    price: float = Field(gt=0)
    notes: str | None = None


class PortfolioPositionUpdate(BaseModel):
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    notes: str | None = None


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _time_key(dt_value: datetime) -> str:
    return dt_value.strftime("%Y-%m-%d")


def _price_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_native(value: Any) -> Any:
    """Recursively convert numpy/pandas scalar types into native Python types."""
    if isinstance(value, dict):
        return {str(k): _to_native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_native(v) for v in value]
    if isinstance(value, tuple):
        return [_to_native(v) for v in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return [_to_native(v) for v in value.tolist()]
    return value


def _get_index_symbols(index_name: str) -> list[str]:
    idx = IDXIndexSource()
    upper = index_name.upper()
    if upper == "IDX30":
        return idx.get_idx30_symbols()
    if upper == "LQ45":
        return idx.get_lq45_symbols()
    if upper == "JII70":
        return idx.get_jii70_symbols()
    if upper == "IDX80":
        return idx.get_idx80_symbols()
    if upper == "ALL":
        symbols = []
        seen = set()
        for row in ALL_IDX_STOCKS:
            symbol = str(row.get("symbol", "")).upper().strip()
            if not symbol or symbol in seen:
                continue
            symbols.append(symbol)
            seen.add(symbol)
        return symbols
    return idx.get_idx30_symbols()


def _resolve_timeframe(timeframe: str) -> str:
    mapping = {"1w": "5d", "1m": "1mo", "3m": "3mo", "6m": "6mo"}
    return mapping.get(timeframe.lower(), "3mo")


def _resolve_period(period: str | None, timeframe: str | None) -> str:
    if period:
        return period
    if timeframe:
        return _resolve_timeframe(timeframe)
    return "3mo"


def _symbol_to_yf(symbol: str) -> str:
    clean = symbol.strip().upper()
    if clean.startswith("^"):
        return clean
    if clean.endswith(".JK"):
        return clean
    return f"{clean}.JK"


def _normalize_indicator_period(period: str) -> str:
    mapping = {
        "1wk": "5d",
        "1w": "5d",
        "5d": "5d",
        "1mo": "1mo",
        "3mo": "3mo",
        "6mo": "6mo",
        "1y": "1y",
    }
    return mapping.get((period or "3mo").lower(), "3mo")


def _calc_rr(entry: float | None, sl: float | None, tp: float | None) -> float | None:
    if entry is None or sl is None or tp is None:
        return None
    risk = entry - sl
    reward = tp - entry
    if risk <= 0:
        return None
    return reward / risk


def _scan_status(gates_passed: int) -> str:
    if gates_passed >= 5:
        return "READY"
    if gates_passed >= 4:
        return "WATCH"
    return "REJECTED"


def _is_scan_cache_fresh() -> bool:
    last_scan_at = _WEB_RUNTIME.get("last_scan_at")
    if not isinstance(last_scan_at, datetime):
        return False
    return (datetime.utcnow() - last_scan_at).total_seconds() < SCAN_LAST_TTL_SECONDS


def _build_signal_event(symbol: str) -> dict[str, Any]:
    yahoo = YahooFinanceSource()
    foreign = ForeignFlowMonitor()
    volume = UnusualVolumeDetector()
    sentiment = StockbitSentiment()
    probability = ProbabilityEngine()

    info = yahoo.get_stock_info(symbol)
    history = yahoo.get_price_history(symbol, period="6mo")
    if history.empty:
        raise ValueError(f"No history for {symbol}")

    fundamentals = {
        "pe_ratio": info.get("pe_ratio") if info else None,
        "pb_ratio": info.get("pb_ratio") if info else None,
        "roe": None,
        "debt_to_equity": None,
        "profit_margin": None,
        "current_ratio": None,
    }

    flow_signal = foreign.get_flow_signal(symbol, days=5)
    volume_signal = volume.detect(symbol, history=history)
    sentiment_signal = sentiment.analyze(symbol)
    analysis = analyze_stock(
        ticker=symbol,
        df=history,
        fundamentals=fundamentals,
        config=GateConfig(),
        foreign_flow_signal=flow_signal,
        unusual_volume_signal=volume_signal,
        sentiment_signal=sentiment_signal,
    )
    forecast = probability.forecast(
        symbol,
        {
            "volume_ratio": volume_signal.get("volume_ratio", 0),
            "adx": analysis.adx.get("adx", 0),
            "near_support": (
                analysis.support_resistance.distance_to_support_pct <= 10
                if analysis.support_resistance else False
            ),
            "sentiment_label": sentiment_signal.get("sentiment", "NEUTRAL"),
            "volume_classification": volume_signal.get("classification", "NORMAL"),
            "smart_money_signal": flow_signal.get("signal", "NEUTRAL"),
        },
    )

    trade_plan = analysis.trade_plan
    rr_value = _calc_rr(
        _price_or_none(analysis.current_price),
        _price_or_none(getattr(trade_plan, "stop_loss", None) if trade_plan else None),
        _price_or_none(getattr(trade_plan, "take_profit_1", None) if trade_plan else None),
    )

    gates_passed = int(getattr(analysis.gates, "gates_passed", 0))
    result = {
        "symbol": symbol,
        "score": round(float(analysis.composite_score), 1),
        "gate_passed": gates_passed,
        "gate_total": int(getattr(analysis.gates, "total_gates", 6)),
        "status": _scan_status(gates_passed),
        "current_price": _price_or_none(analysis.current_price),
        "sl": _price_or_none(getattr(trade_plan, "stop_loss", None) if trade_plan else None),
        "tp1": _price_or_none(getattr(trade_plan, "take_profit_1", None) if trade_plan else None),
        "tp2": _price_or_none(getattr(trade_plan, "take_profit_2", None) if trade_plan else None),
        "rr": round(rr_value, 2) if rr_value is not None else None,
        "smart_money": {
            "signal": flow_signal.get("signal", "NEUTRAL"),
            "strength": flow_signal.get("strength", "WEAK"),
            "source": flow_signal.get("source", "volume_proxy"),
        },
        "volume": {
            "classification": volume_signal.get("classification", "NORMAL"),
            "ratio": round(float(volume_signal.get("volume_ratio", 0.0) or 0.0), 2),
            "price_action": volume_signal.get("price_action", "NEUTRAL"),
        },
        "sentiment": {
            "label": sentiment_signal.get("sentiment", "NEUTRAL"),
            "score": int(sentiment_signal.get("score", 0) or 0),
            "source": sentiment_signal.get("source", "stockbit"),
        },
        "probability": {
            "p5": float(forecast.get("probability_5pct", 0.0)),
            "expected": float(forecast.get("expected_return", 0.0)),
            "confidence": forecast.get("confidence", "LOW"),
        },
        "pattern": {
            "dominant": forecast.get("dominant_pattern"),
            "bias": forecast.get("overall_pattern_bias", "NEUTRAL"),
            "count": int(forecast.get("pattern_count", 0) or 0),
        },
    }
    return result


def _portfolio_history(days: int = 30) -> list[dict[str, Any]]:
    from stockai.core.portfolio import PortfolioManager

    yahoo = YahooFinanceSource()
    manager = PortfolioManager()
    positions = manager.get_positions()
    if not positions:
        return []

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=max(days * 2, 40))

    series_map: dict[str, dict[str, float]] = {}
    for pos in positions:
        symbol = str(pos.get("symbol", "")).upper().strip()
        shares = float(pos.get("shares", 0) or 0)
        if not symbol or shares <= 0:
            continue
        df = yahoo.get_price_history(
            symbol,
            start=datetime.combine(start_date, datetime.min.time()),
            end=datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        )
        if df.empty:
            continue
        points: dict[str, float] = {}
        for _, row in df.iterrows():
            date_key = _time_key(row["date"])
            close_price = _price_or_none(row.get("close"))
            if close_price is None:
                continue
            points[date_key] = close_price * shares
        series_map[symbol] = points

    if not series_map:
        return []

    all_dates = sorted(set().union(*[set(v.keys()) for v in series_map.values()]))
    total_cost = sum(float(p.get("cost_basis", 0) or 0) for p in positions)
    history: list[dict[str, Any]] = []
    last_value = total_cost
    for date_key in all_dates:
        day_value = 0.0
        for symbol, symbol_points in series_map.items():
            if date_key in symbol_points:
                day_value += symbol_points[date_key]
            else:
                day_value += 0.0
        if day_value <= 0:
            day_value = last_value
        pnl = day_value - total_cost
        pnl_pct = (pnl / total_cost * 100) if total_cost > 0 else 0
        history.append({
            "date": date_key,
            "value": round(day_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })
        last_value = day_value

    return history[-days:]


def _risk_metrics_from_history(
    history: list[dict[str, Any]],
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    values = [float(point.get("value", 0) or 0) for point in history if point.get("value") is not None]
    if len(values) < 3:
        return {
            "var_95": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate": 0.0,
            "win_trades": 0,
            "total_trades": 0,
        }

    returns = []
    for prev, curr in zip(values[:-1], values[1:]):
        if prev > 0:
            returns.append((curr / prev) - 1)

    if returns:
        sorted_returns = sorted(returns)
        var95 = sorted_returns[max(int(len(sorted_returns) * 0.05) - 1, 0)] * values[-1]
        avg_ret = statistics.mean(returns)
        std_ret = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        sharpe = (avg_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0.0
    else:
        var95 = 0.0
        sharpe = 0.0

    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (value - peak) / peak
            max_dd = min(max_dd, drawdown)

    pnl_points = [float(point.get("pnl", 0) or 0) for point in history]
    wins = len([p for p in pnl_points if p > 0])
    total = len(pnl_points)
    win_rate = (wins / total * 100) if total > 0 else 0.0

    return {
        "var_95": round(var95, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate": round(win_rate, 2),
        "win_trades": wins,
        "total_trades": total,
    }


def _compose_alerts() -> list[dict[str, Any]]:
    now = datetime.utcnow()
    dismissed_until = _WEB_RUNTIME.get("alerts_dismissed_until")
    if isinstance(dismissed_until, datetime) and now <= dismissed_until:
        return []

    alerts: list[dict[str, Any]] = []
    from stockai.core.portfolio import PnLCalculator

    try:
        portfolio = PnLCalculator().get_portfolio_summary()
        for pos in portfolio.get("positions", []):
            pnl_pct = float(pos.get("pnl_percent", 0) or 0)
            if pnl_pct <= -4.5:
                alerts.append({
                    "level": "CRITICAL",
                    "title": f"{pos.get('symbol')} mendekati stop-loss ({pnl_pct:.1f}%)",
                    "timestamp": _now_iso(),
                })
    except Exception:
        pass

    last_scan = _WEB_RUNTIME.get("last_scan") or {}
    for item in (last_scan.get("results", [])[:5] if isinstance(last_scan, dict) else []):
        status = str(item.get("status", "REJECTED")).upper()
        if status in {"WATCH", "READY"}:
            alerts.append({
                "level": "WATCH",
                "title": f"{item.get('symbol')} masuk {status}",
                "timestamp": _now_iso(),
            })

    if isinstance(last_scan, dict) and last_scan.get("index"):
        alerts.append({
            "level": "INFO",
            "title": f"Scan {last_scan.get('index')} selesai ({last_scan.get('scanned', 0)} saham)",
            "timestamp": last_scan.get("timestamp", _now_iso()),
        })

    return alerts[:50]


# ============ API ROUTES ============

@api_router.get("/status")
async def api_status() -> dict:
    """Get API status and version."""
    return {
        "status": "ok",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat(),
    }


@api_router.get("/dashboard")
async def get_dashboard() -> dict:
    """Dashboard aggregate data."""
    yahoo = YahooFinanceSource()
    ihsg_history = []
    ihsg_quote = {"price": None, "change_pct": None}

    try:
        import yfinance as yf

        df = yf.Ticker("^JKSE").history(period="7d", interval="1d")
        if not df.empty:
            for idx, row in df.iterrows():
                ihsg_history.append({
                    "time": idx.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                })
            if len(df) >= 2:
                last_close = float(df["Close"].iloc[-1])
                prev_close = float(df["Close"].iloc[-2])
                change_pct = ((last_close / prev_close) - 1) * 100 if prev_close else 0
                ihsg_quote = {"price": round(last_close, 2), "change_pct": round(change_pct, 2)}
    except Exception:
        pass

    init_database()
    from stockai.core.portfolio import PnLCalculator

    portfolio = PnLCalculator().get_portfolio_summary()
    last_scan = _WEB_RUNTIME.get("last_scan") if _is_scan_cache_fresh() else None
    results = (last_scan or {}).get("results", [])
    ready_count = len([r for r in results if r.get("status") == "READY"])
    watch_count = len([r for r in results if r.get("status") == "WATCH"])

    scheduler_info = {"running": False, "next_scan": None}
    try:
        from stockai.scheduler.runner import scheduler_status

        status = scheduler_status()
        next_scan = None
        for row in status.get("jobs", []):
            if row.get("id") == "morning_scan":
                next_scan = row.get("next_run")
                break
        scheduler_info = {"running": status.get("running", False), "next_scan": next_scan}
    except Exception:
        pass

    return {
        "server_time": _now_iso(),
        "live_status": "LIVE",
        "scheduler": scheduler_info,
        "ihsg": {"quote": ihsg_quote, "history_7d": ihsg_history},
        "last_scan": {
            "index": (last_scan or {}).get("index", "ALL"),
            "scanned": int((last_scan or {}).get("scanned", 0)),
            "ready": ready_count,
            "watch": watch_count,
            "timestamp": (last_scan or {}).get("timestamp"),
            "results": results[:20],
        },
        "portfolio_summary": portfolio.get("summary", {}),
    }


@api_router.get("/scheduler/status")
async def get_scheduler_status() -> dict:
    try:
        from stockai.scheduler.runner import scheduler_status

        return scheduler_status()
    except Exception as exc:
        return {"running": False, "jobs": [], "error": str(exc)}


@api_router.get("/scan/last")
async def get_last_scan() -> dict:
    if not _is_scan_cache_fresh():
        return {"available": False, "message": "No recent scan"}
    last_scan = _WEB_RUNTIME.get("last_scan") or {}
    return {"available": True, **last_scan}


@api_router.get("/scan/stream")
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


@api_router.get("/stock/{symbol}/full")
async def get_stock_full(symbol: str) -> dict:
    clean_symbol = symbol.upper().strip()
    idx_source = IDXIndexSource()
    yahoo = YahooFinanceSource()

    info = idx_source.get_stock_details(clean_symbol)
    history = yahoo.get_price_history(clean_symbol, period="6mo")
    if history.empty:
        raise HTTPException(status_code=404, detail=f"No data for {clean_symbol}")

    foreign = ForeignFlowMonitor()
    volume = UnusualVolumeDetector()
    sentiment = StockbitSentiment()
    probability = ProbabilityEngine()

    flow_signal = foreign.get_flow_signal(clean_symbol, days=5)
    volume_signal = volume.detect(clean_symbol, history=history)
    sentiment_signal = sentiment.analyze(clean_symbol)

    analysis = analyze_stock(
        ticker=clean_symbol,
        df=history,
        fundamentals={
            "pe_ratio": info.get("pe_ratio") if info else None,
            "pb_ratio": info.get("pb_ratio") if info else None,
            "roe": None,
            "debt_to_equity": None,
            "profit_margin": None,
            "current_ratio": None,
        },
        config=GateConfig(),
        foreign_flow_signal=flow_signal,
        unusual_volume_signal=volume_signal,
        sentiment_signal=sentiment_signal,
    )

    forecast = probability.forecast(
        clean_symbol,
        {
            "volume_ratio": volume_signal.get("volume_ratio", 0),
            "adx": analysis.adx.get("adx", 0),
            "near_support": (
                analysis.support_resistance.distance_to_support_pct <= 10
                if analysis.support_resistance else False
            ),
            "sentiment_label": sentiment_signal.get("sentiment", "NEUTRAL"),
            "volume_classification": volume_signal.get("classification", "NORMAL"),
            "smart_money_signal": flow_signal.get("signal", "NEUTRAL"),
        },
    )

    news_items: list[dict[str, Any]] = []
    try:
        from stockai.core.sentiment.news import NewsAggregator

        news = NewsAggregator().fetch_google_news(clean_symbol, max_articles=10)
        for row in news:
            news_items.append({
                "title": row.title,
                "url": row.url,
                "source": row.source,
                "published_at": str(row.published_at) if row.published_at else None,
            })
    except Exception:
        news_items = []

    gate_status = [
        {"name": "Overall", "passed": analysis.composite_score >= 55, "value": round(analysis.composite_score, 1), "threshold": 55},
        {"name": "Technical", "passed": ((analysis.momentum_score + (100 - analysis.volatility_score)) / 2) >= 45, "value": round((analysis.momentum_score + (100 - analysis.volatility_score)) / 2, 1), "threshold": 45},
        {"name": "SmartMoney", "passed": analysis.smart_money.score >= 1.5, "value": round(analysis.smart_money.score, 2), "threshold": 1.5},
        {"name": "Support", "passed": analysis.support_resistance.distance_to_support_pct <= 10 if analysis.support_resistance.distance_to_support_pct is not None else False, "value": round(float(analysis.support_resistance.distance_to_support_pct or 0), 2), "threshold": 10},
        {"name": "ADX", "passed": float(analysis.adx.get("adx", 0)) >= 20, "value": round(float(analysis.adx.get("adx", 0)), 2), "threshold": 20},
        {"name": "Fundamental", "passed": ((analysis.value_score + analysis.quality_score) / 2) >= 45, "value": round((analysis.value_score + analysis.quality_score) / 2, 1), "threshold": 45},
    ]

    payload = {
        "symbol": clean_symbol,
        "stock_info": info or {"symbol": clean_symbol},
        "latest": {
            "price": _price_or_none(analysis.current_price),
            "volume": float(history["volume"].iloc[-1]) if len(history) else None,
            "avg_volume_20d": float(history["volume"].tail(20).mean()) if len(history) else None,
        },
        "analysis": {
            "composite_score": round(float(analysis.composite_score), 1),
            "value_score": round(float(analysis.value_score), 1),
            "quality_score": round(float(analysis.quality_score), 1),
            "momentum_score": round(float(analysis.momentum_score), 1),
            "volatility_score": round(float(analysis.volatility_score), 1),
            "gate_status": gate_status,
            "trade_plan": {
                "entry_low": _price_or_none(analysis.trade_plan.entry_low) if analysis.trade_plan else None,
                "entry_high": _price_or_none(analysis.trade_plan.entry_high) if analysis.trade_plan else None,
                "stop_loss": _price_or_none(analysis.trade_plan.stop_loss) if analysis.trade_plan else None,
                "tp1": _price_or_none(analysis.trade_plan.take_profit_1) if analysis.trade_plan else None,
                "tp2": _price_or_none(analysis.trade_plan.take_profit_2) if analysis.trade_plan else None,
                "tp3": _price_or_none(analysis.trade_plan.take_profit_3) if analysis.trade_plan else None,
                "rr": _price_or_none(analysis.trade_plan.risk_reward_ratio) if analysis.trade_plan else None,
            },
        },
        "smart_money": flow_signal,
        "volume": volume_signal,
        "sentiment": sentiment_signal,
        "forecast": forecast,
        "patterns": forecast.get("patterns_detected", []),
        "news": news_items,
        "updated_at": _now_iso(),
    }
    return _to_native(payload)


@api_router.get("/stock/{symbol}/scoring")
async def get_stock_scoring(symbol: str) -> dict:
    """Fast stock scoring endpoint without heavy ML/news aggregation."""
    clean_symbol = symbol.upper().strip()
    idx_source = IDXIndexSource()
    yahoo = YahooFinanceSource()

    info = idx_source.get_stock_details(clean_symbol) or {"symbol": clean_symbol}
    history = yahoo.get_price_history(clean_symbol, period="6mo")
    if history.empty:
        raise HTTPException(status_code=404, detail=f"No data for {clean_symbol}")

    analysis = analyze_stock(
        ticker=clean_symbol,
        df=history,
        fundamentals={
            "pe_ratio": info.get("pe_ratio"),
            "pb_ratio": info.get("pb_ratio"),
            "roe": None,
            "debt_to_equity": None,
            "profit_margin": None,
            "current_ratio": None,
        },
        config=GateConfig(),
        foreign_flow_signal={"signal": "NEUTRAL", "strength": "WEAK", "source": "volume_proxy"},
        unusual_volume_signal={"classification": "NORMAL", "volume_ratio": 1.0, "price_action": "NEUTRAL"},
        sentiment_signal={"sentiment": "NEUTRAL", "score": 0, "source": "stockbit"},
    )

    payload = {
        "symbol": clean_symbol,
        "scores": {
            "composite_score": round(float(analysis.composite_score), 1),
            "value_score": round(float(analysis.value_score), 1),
            "quality_score": round(float(analysis.quality_score), 1),
            "momentum_score": round(float(analysis.momentum_score), 1),
            "volatility_score": round(float(analysis.volatility_score), 1),
        },
        "gates": {
            "passed": int(getattr(analysis.gates, "gates_passed", 0)),
            "total": int(getattr(analysis.gates, "total_gates", 6)),
            "confidence": getattr(analysis.gates, "confidence", "REJECTED"),
            "reasons": list(getattr(analysis.gates, "rejection_reasons", [])),
        },
        "trade_plan": {
            "entry_low": _price_or_none(analysis.trade_plan.entry_low) if analysis.trade_plan else None,
            "entry_high": _price_or_none(analysis.trade_plan.entry_high) if analysis.trade_plan else None,
            "stop_loss": _price_or_none(analysis.trade_plan.stop_loss) if analysis.trade_plan else None,
            "tp1": _price_or_none(analysis.trade_plan.take_profit_1) if analysis.trade_plan else None,
            "tp2": _price_or_none(analysis.trade_plan.take_profit_2) if analysis.trade_plan else None,
            "rr": _price_or_none(analysis.trade_plan.risk_reward_ratio) if analysis.trade_plan else None,
        },
        "support_resistance": {
            "support": _price_or_none(analysis.support_resistance.nearest_support),
            "resistance": _price_or_none((analysis.support_resistance.resistances or [None])[0]),
            "distance_to_support_pct": _price_or_none(analysis.support_resistance.distance_to_support_pct),
        },
    }
    return _to_native(payload)


@api_router.get("/stock/{symbol}/indicators")
async def get_stock_indicators(
    symbol: str,
    period: str = Query("3mo", description="1wk,1mo,3mo,6mo,1y"),
) -> dict:
    """Return full technical indicators for advanced multi-pane chart."""
    import yfinance as yf

    normalized_period = _normalize_indicator_period(period)
    cache_key = f"stock_indicators:{symbol.upper()}:{normalized_period}"
    cached = memory_cache_get(cache_key)
    if isinstance(cached, dict):
        return cached

    yf_symbol = _symbol_to_yf(symbol)
    try:
        df = yf.Ticker(yf_symbol).history(period=normalized_period, interval="1d")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch indicators: {exc}")

    if df.empty:
        raise HTTPException(status_code=404, detail="No data")

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    open_ = df["Open"]
    volume = df["Volume"]

    ema8 = close.ewm(span=8, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + (bb_std * 2)
    bb_lower = bb_mid - (bb_std * 2)

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    vol_ma20 = volume.rolling(20).mean()
    avg_vol = float(vol_ma20.iloc[-1]) if not vol_ma20.empty and pd.notna(vol_ma20.iloc[-1]) else 0.0

    recent = df.tail(20)
    support = float(recent["Low"].min()) if not recent.empty else float(df["Low"].min())
    resistance = float(recent["High"].max()) if not recent.empty else float(df["High"].max())

    def ts(dt_value: pd.Timestamp) -> int:
        return int(pd.Timestamp(dt_value).timestamp())

    def line_series(series_data: pd.Series) -> list[dict[str, Any]]:
        output = []
        for idx, value in series_data.items():
            if pd.isna(value):
                continue
            output.append({"time": ts(idx), "value": round(float(value), 4)})
        return output

    candle_rows = []
    vol_rows = []
    for idx, row in df.iterrows():
        o = float(row["Open"])
        c = float(row["Close"])
        vma = vol_ma20.get(idx, np.nan)
        is_spike = bool(pd.notna(vma) and float(row["Volume"]) > float(vma) * 2.0)
        candle_rows.append({
            "time": ts(idx),
            "open": round(o, 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(c, 2),
        })
        vol_rows.append({
            "time": ts(idx),
            "value": float(row["Volume"]),
            "color": "#00ff8866" if c >= o else "#ff3b5c66",
            "spike": is_spike,
        })

    macd_hist_rows = []
    for idx, value in macd_hist.items():
        if pd.isna(value):
            continue
        val = float(value)
        macd_hist_rows.append({
            "time": ts(idx),
            "value": round(val, 4),
            "color": "#00ff8899" if val >= 0 else "#ff3b5c99",
        })

    current_rsi = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0
    current_macd = float(macd_line.iloc[-1]) if pd.notna(macd_line.iloc[-1]) else 0.0
    current_signal = float(signal_line.iloc[-1]) if pd.notna(signal_line.iloc[-1]) else 0.0
    ema8_now = float(ema8.iloc[-1]) if pd.notna(ema8.iloc[-1]) else 0.0
    ema21_now = float(ema21.iloc[-1]) if pd.notna(ema21.iloc[-1]) else 0.0
    ma50_now = float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else None
    ma200_now = float(ma200.iloc[-1]) if pd.notna(ma200.iloc[-1]) else None
    close_now = float(close.iloc[-1]) if pd.notna(close.iloc[-1]) else 0.0
    bb_upper_now = float(bb_upper.iloc[-1]) if pd.notna(bb_upper.iloc[-1]) else None
    bb_lower_now = float(bb_lower.iloc[-1]) if pd.notna(bb_lower.iloc[-1]) else None

    summary = {
        "rsi": round(current_rsi, 1),
        "rsi_signal": "OVERBOUGHT" if current_rsi > 70 else "OVERSOLD" if current_rsi < 30 else "NEUTRAL",
        "macd_signal": "BULLISH" if current_macd > current_signal else "BEARISH",
        "macd_cross": "GOLDEN" if current_macd > current_signal else "DEATH",
        "ema_signal": "BULLISH" if ema8_now > ema21_now else "BEARISH",
        "ma_signal": (
            "ABOVE MA50"
            if ma50_now is not None and close_now > ma50_now
            else "BELOW MA50"
        ),
        "bb_position": (
            "UPPER"
            if bb_upper_now is not None and close_now > bb_upper_now
            else "LOWER"
            if bb_lower_now is not None and close_now < bb_lower_now
            else "MIDDLE"
        ),
        "avg_volume": round(avg_vol),
        "trend": (
            "BULLISH"
            if ema8_now > ema21_now and (ma50_now is None or close_now > ma50_now)
            else "BEARISH"
        ),
        "ma200_signal": (
            "ABOVE MA200"
            if ma200_now is not None and close_now > ma200_now
            else "BELOW MA200"
            if ma200_now is not None
            else "N/A"
        ),
    }

    payload = {
        "symbol": symbol.upper(),
        "period": normalized_period,
        "candles": candle_rows,
        "indicators": {
            "ema8": line_series(ema8),
            "ema21": line_series(ema21),
            "ma50": line_series(ma50),
            "ma200": line_series(ma200),
            "bb_upper": line_series(bb_upper),
            "bb_mid": line_series(bb_mid),
            "bb_lower": line_series(bb_lower),
            "macd_line": line_series(macd_line),
            "signal_line": line_series(signal_line),
            "macd_hist": macd_hist_rows,
            "rsi": line_series(rsi),
            "volume": vol_rows,
            "vol_ma20": line_series(vol_ma20),
        },
        "levels": {
            "support": round(support, 2),
            "resistance": round(resistance, 2),
        },
        "summary": summary,
    }
    native = _to_native(payload)
    memory_cache_set(cache_key, native, ttl=900)
    return native


@api_router.get("/stock/{symbol}/chart")
async def get_stock_lw_chart(
    symbol: str,
    timeframe: str = Query("3m", description="1w,1m,3m,6m"),
    period: str | None = Query(None, description="Raw period override like 7d,1mo,3mo"),
) -> dict:
    raw_symbol = symbol.strip()
    clean_symbol = raw_symbol.upper()
    resolved_period = _resolve_period(period, timeframe)
    if clean_symbol.startswith("^"):
        try:
            import yfinance as yf
            df = yf.Ticker(clean_symbol).history(period=resolved_period, interval="1d")
            if df.empty:
                raise HTTPException(status_code=404, detail=f"No chart data for {clean_symbol}")
            df = df.reset_index()
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]
            if "date" not in df.columns and "datetime" in df.columns:
                df = df.rename(columns={"datetime": "date"})
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"No chart data for {clean_symbol}: {exc}")
    else:
        yahoo = YahooFinanceSource()
        df = yahoo.get_price_history(clean_symbol, period=resolved_period)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No chart data for {clean_symbol}")

    candles = []
    volumes = []
    for _, row in df.iterrows():
        time_value = row["date"].strftime("%Y-%m-%d")
        open_val = float(row["open"])
        close_val = float(row["close"])
        candles.append({
            "time": time_value,
            "open": round(open_val, 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(close_val, 2),
        })
        volumes.append({
            "time": time_value,
            "value": int(row["volume"]),
            "color": "rgba(0,255,136,0.55)" if close_val >= open_val else "rgba(255,59,92,0.55)",
        })

    ma50 = (df["close"].rolling(window=50).mean()).tolist()
    ma200 = (df["close"].rolling(window=200).mean()).tolist()
    ma50_series = [{"time": candles[i]["time"], "value": round(float(v), 2)} for i, v in enumerate(ma50) if v == v]
    ma200_series = [{"time": candles[i]["time"], "value": round(float(v), 2)} for i, v in enumerate(ma200) if v == v]

    support = float(df["low"].tail(20).min()) if len(df) >= 20 else float(df["low"].min())
    resistance = float(df["high"].tail(20).max()) if len(df) >= 20 else float(df["high"].max())
    return {
        "symbol": clean_symbol,
        "timeframe": timeframe.lower(),
        "period": resolved_period,
        "candles": candles,
        "volume": volumes,
        "ma50": ma50_series,
        "ma200": ma200_series,
        "support": round(support, 2),
        "resistance": round(resistance, 2),
    }


@api_router.get("/portfolio/summary")
async def get_portfolio_summary_v2() -> dict:
    init_database()
    from stockai.core.portfolio import PnLCalculator

    summary = PnLCalculator().get_portfolio_summary()
    history = _portfolio_history(days=30)
    metrics = _risk_metrics_from_history(history, summary.get("positions", []))
    return {
        "summary": summary.get("summary", {}),
        "positions": summary.get("positions", []),
        "risk_metrics": metrics,
    }


@api_router.get("/portfolio/history")
async def get_portfolio_history(days: int = Query(30, ge=7, le=365)) -> dict:
    init_database()
    history = _portfolio_history(days=days)
    return {"days": days, "history": history}


@api_router.post("/portfolio/position")
async def add_portfolio_position(payload: PortfolioPositionCreate) -> dict:
    init_database()
    from stockai.core.portfolio import PortfolioManager

    manager = PortfolioManager()
    try:
        result = manager.add_position(
            symbol=payload.symbol.upper(),
            shares=payload.shares,
            price=payload.price,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "position": result}


@api_router.put("/portfolio/position/{symbol}")
async def update_portfolio_position(symbol: str, payload: PortfolioPositionUpdate) -> dict:
    clean_symbol = symbol.upper().strip()
    meta = _WEB_RUNTIME.setdefault("portfolio_meta", {})
    current = dict(meta.get(clean_symbol, {}))
    if payload.stop_loss is not None:
        current["stop_loss"] = payload.stop_loss
    if payload.take_profit is not None:
        current["take_profit"] = payload.take_profit
    if payload.notes is not None:
        current["notes"] = payload.notes
    current["updated_at"] = _now_iso()
    meta[clean_symbol] = current
    return {"ok": True, "symbol": clean_symbol, "meta": current}


@api_router.delete("/portfolio/position/{symbol}")
async def delete_portfolio_position(symbol: str) -> dict:
    init_database()
    from stockai.core.portfolio import PortfolioManager

    manager = PortfolioManager()
    try:
        result = manager.remove_position(symbol.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "result": result}


@api_router.get("/alerts")
async def list_alerts() -> dict:
    return {"alerts": _compose_alerts(), "generated_at": _now_iso()}


@api_router.delete("/alerts")
async def clear_alerts() -> dict:
    _WEB_RUNTIME["alerts_dismissed_until"] = datetime.utcnow() + timedelta(seconds=ALERT_DISMISS_TTL_SECONDS)
    return {"ok": True, "dismissed_until": _WEB_RUNTIME["alerts_dismissed_until"].isoformat()}


@api_router.get("/stocks")
async def list_stocks(
    index: str = Query("IDX30", description="Index to list (IDX30, LQ45)"),
    include_prices: bool = Query(False, description="Include current prices"),
) -> dict:
    """List stocks in an index."""
    idx_source = IDXIndexSource()

    if index.upper() == "IDX30":
        stocks = idx_source.get_idx30_stocks(include_prices=include_prices)
    elif index.upper() == "LQ45":
        stocks = idx_source.get_lq45_stocks(include_prices=include_prices)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown index: {index}")

    return {
        "index": index.upper(),
        "count": len(stocks),
        "stocks": stocks,
    }


@api_router.get("/stocks/{symbol}")
async def get_stock_info(symbol: str) -> dict:
    """Get detailed stock information."""
    idx_source = IDXIndexSource()
    info = idx_source.get_stock_details(symbol.upper())

    if not info:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    return info


@api_router.get("/stocks/{symbol}/history")
async def get_stock_history(
    symbol: str,
    period: str = Query("1mo", description="Time period (1d,5d,1mo,3mo,6mo,1y,2y)"),
) -> dict:
    """Get stock price history."""
    yahoo = YahooFinanceSource()
    df = yahoo.get_price_history(symbol.upper(), period=period)

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No history for {symbol}")

    # Convert to dict
    history = []
    for _, row in df.iterrows():
        history.append({
            "date": row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"]),
            "open": round(row["open"], 2),
            "high": round(row["high"], 2),
            "low": round(row["low"], 2),
            "close": round(row["close"], 2),
            "volume": int(row["volume"]),
        })

    return {
        "symbol": symbol.upper(),
        "period": period,
        "count": len(history),
        "history": history,
    }


@api_router.get("/stocks/{symbol}/chart")
async def get_stock_chart_data(
    symbol: str,
    period: str = Query("3mo", description="Time period"),
) -> dict:
    """Get stock chart data formatted for Plotly."""
    yahoo = YahooFinanceSource()
    df = yahoo.get_price_history(symbol.upper(), period=period)

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    # Format for candlestick chart
    return {
        "symbol": symbol.upper(),
        "dates": [d.isoformat() if hasattr(d, "isoformat") else str(d) for d in df["date"]],
        "open": df["open"].round(2).tolist(),
        "high": df["high"].round(2).tolist(),
        "low": df["low"].round(2).tolist(),
        "close": df["close"].round(2).tolist(),
        "volume": df["volume"].astype(int).tolist(),
    }


@api_router.get("/portfolio")
async def get_portfolio() -> dict:
    """Get portfolio positions with P&L."""
    init_database()

    from stockai.core.portfolio import PnLCalculator

    pnl_calc = PnLCalculator()
    summary = pnl_calc.get_portfolio_summary()

    return summary


@api_router.get("/portfolio/analytics")
async def get_portfolio_analytics() -> dict:
    """Get portfolio analytics."""
    init_database()

    from stockai.core.portfolio import PortfolioAnalytics

    analytics = PortfolioAnalytics()
    analysis = analytics.get_full_analysis()
    insights = analytics.generate_ai_insights(analysis)

    analysis["insights"] = insights
    return analysis


@api_router.get("/sentiment/{symbol}")
@async_cached("sentiment")
async def get_sentiment(
    symbol: str,
    days: int = Query(7, description="Days of news to analyze"),
) -> dict:
    """Get sentiment analysis for a stock."""
    # Normalize symbol for consistent cache keys
    symbol = symbol.upper()

    from stockai.core.sentiment import SentimentAnalyzer, NewsAggregator

    news_agg = NewsAggregator()
    articles = news_agg.fetch_all(symbol, max_articles=15, days_back=days)

    if not articles:
        return {
            "symbol": symbol,
            "article_count": 0,
            "sentiment": None,
            "message": "No recent news found",
        }

    analyzer = SentimentAnalyzer()
    aggregated = analyzer.aggregate_sentiment(articles, symbol)

    return aggregated.to_dict()


@api_router.get("/predict/{symbol}")
@async_cached("prediction")
async def get_prediction(symbol: str) -> dict:
    """Get stock prediction with historical accuracy.

    Returns a prediction for the stock along with historical accuracy
    metrics if available.
    """
    # Normalize symbol for consistent cache keys
    symbol = symbol.upper()
    settings = get_settings()
    yahoo = YahooFinanceSource()

    df = yahoo.get_price_history(symbol, period="6mo")
    if df.empty or len(df) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient data for {symbol}",
        )

    model_dir = settings.project_root / "data" / "models"
    ensemble = EnsemblePredictor(
        xgboost_path=model_dir / "xgboost_v1.json",
    )

    loaded = ensemble.load_models()
    if not any(loaded.values()):
        return {
            "symbol": symbol,
            "prediction": None,
            "message": "No trained models available",
            "historical_accuracy": None,
        }

    # Get prediction with sentiment
    result = ensemble.predict_with_sentiment(df, symbol)

    # Get historical accuracy for this stock
    init_database()
    tracker = PredictionAccuracyTracker()
    accuracy_data = tracker.get_stock_accuracy(symbol.upper())

    # Format historical accuracy for response
    # Stocks with no predictions or not found will have a "message" key
    if "message" in accuracy_data:
        historical_accuracy = None
    else:
        historical_accuracy = {
            "total_predictions": accuracy_data.get("total_predictions", 0),
            "correct_predictions": accuracy_data.get("correct_predictions", 0),
            "accuracy_rate": accuracy_data.get("accuracy_rate", 0.0),
            "by_direction": accuracy_data.get("by_direction"),
            "by_confidence": accuracy_data.get("by_confidence"),
        }

    return {
        "symbol": symbol,
        "prediction": result,
        "historical_accuracy": historical_accuracy,
    }


# ============ WATCHLIST API ROUTES ============


@api_router.get("/watchlist", response_model=WatchlistItemListResponse)
async def list_watchlist() -> dict:
    """Get all watchlist items with associated stock information.

    Returns array of watchlist items with stock details (symbol, name, sector).
    """
    init_database()

    items = get_watchlist_items()

    # Convert to response format
    response_items = [
        WatchlistItemResponse.model_validate(item)
        for item in items
    ]

    return {
        "count": len(response_items),
        "items": response_items,
    }


@api_router.post("/watchlist", response_model=WatchlistItemResponse, status_code=201)
async def create_watchlist_item(item: WatchlistItemCreate) -> WatchlistItemResponse:
    """Add a stock to the watchlist.

    Accepts stock symbol (or stock_id), optional alert prices, and notes.
    If the stock doesn't exist in the database, it will be created.

    Returns 409 Conflict if the stock is already in the watchlist.
    """
    init_database()

    try:
        watchlist_item = add_to_watchlist(
            stock_id=item.stock_id,
            symbol=item.symbol,
            alert_price_above=item.alert_price_above,
            alert_price_below=item.alert_price_below,
            notes=item.notes,
        )
    except WatchlistItemExistsError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Stock {e.symbol} is already in the watchlist",
        )

    return WatchlistItemResponse.model_validate(watchlist_item)


@api_router.get("/watchlist/{item_id}", response_model=WatchlistItemResponse)
async def get_watchlist_item(item_id: int) -> WatchlistItemResponse:
    """Get a single watchlist item by its ID.

    Returns the watchlist item with associated stock information (symbol, name, sector).
    Returns 404 if the watchlist item is not found.
    """
    init_database()

    item = get_watchlist_item_by_id(item_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"Watchlist item with id={item_id} not found",
        )

    return WatchlistItemResponse.model_validate(item)


@api_router.put("/watchlist/{item_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item_endpoint(
    item_id: int,
    update_data: WatchlistItemUpdate,
) -> WatchlistItemResponse:
    """Update a watchlist item's alerts and notes.

    Supports partial updates - only provided fields are updated.
    Set alert prices to 0 to clear them. Set notes to empty string to clear.
    Returns 404 if the watchlist item is not found.
    """
    init_database()

    # Determine what to update vs clear
    # A value of 0 means clear the field, None means don't change
    clear_alert_above = update_data.alert_price_above == 0
    clear_alert_below = update_data.alert_price_below == 0
    clear_notes = update_data.notes == ""

    # Only pass non-zero values for actual updates
    alert_above = (
        update_data.alert_price_above
        if update_data.alert_price_above is not None and update_data.alert_price_above > 0
        else None
    )
    alert_below = (
        update_data.alert_price_below
        if update_data.alert_price_below is not None and update_data.alert_price_below > 0
        else None
    )
    notes = (
        update_data.notes
        if update_data.notes is not None and update_data.notes != ""
        else None
    )

    try:
        item = update_watchlist_item(
            item_id=item_id,
            alert_price_above=alert_above,
            alert_price_below=alert_below,
            notes=notes,
            clear_alert_above=clear_alert_above,
            clear_alert_below=clear_alert_below,
            clear_notes=clear_notes,
        )
    except WatchlistItemNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Watchlist item with id={item_id} not found",
        )

    return WatchlistItemResponse.model_validate(item)


@api_router.delete("/watchlist/{item_id}", response_model=WatchlistDeleteResponse)
async def delete_watchlist_item(item_id: int) -> WatchlistDeleteResponse:
    """Remove a stock from the watchlist by watchlist item ID.

    Returns the deleted watchlist item information for confirmation.
    Returns 404 if the watchlist item is not found.
    """
    init_database()

    try:
        deleted_item = remove_from_watchlist(item_id)
    except WatchlistItemNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Watchlist item with id={item_id} not found",
        )

    return WatchlistDeleteResponse(
        message=f"Successfully removed {deleted_item.stock.symbol} from watchlist",
        deleted_item=WatchlistItemResponse.model_validate(deleted_item),
    )


@api_router.delete("/watchlist/symbol/{symbol}", response_model=WatchlistDeleteResponse)
async def delete_watchlist_item_by_symbol(symbol: str) -> WatchlistDeleteResponse:
    """Remove a stock from the watchlist by stock symbol.

    Convenience endpoint that allows removing a stock from the watchlist
    using the stock symbol instead of the watchlist item ID.
    Returns 404 if the stock is not in the watchlist.
    """
    init_database()

    try:
        deleted_item = remove_from_watchlist_by_symbol(symbol)
    except WatchlistItemNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Stock {symbol.upper()} is not in the watchlist",
        )

    return WatchlistDeleteResponse(
        message=f"Successfully removed {deleted_item.stock.symbol} from watchlist",
        deleted_item=WatchlistItemResponse.model_validate(deleted_item),
    )


# ============ PAGE ROUTES ============

@pages_router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Dashboard home page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "StockAI Dashboard",
            "version": __version__,
        },
    )


@pages_router.get("/stocks", response_class=HTMLResponse)
async def stocks_page(request: Request):
    """Legacy stocks page (kept for compatibility)."""
    templates = request.app.state.templates

    return templates.TemplateResponse(
        "scan.html",
        {
            "request": request,
            "title": "Live Scan",
            "legacy_mode": True,
        },
    )


@pages_router.get("/analyze/{symbol}", response_class=HTMLResponse)
async def analyze_page(request: Request, symbol: str):
    """Legacy analyze page (kept for compatibility)."""
    return await stock_page(request, symbol)


@pages_router.get("/scan", response_class=HTMLResponse)
async def scan_page(request: Request):
    """Live scan page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "scan.html",
        {
            "request": request,
            "title": "Live Scan",
        },
    )


@pages_router.get("/stock/{symbol}", response_class=HTMLResponse)
async def stock_page(request: Request, symbol: str):
    """Stock detail page."""
    templates = request.app.state.templates

    idx_source = IDXIndexSource()
    info = idx_source.get_stock_details(symbol.upper())

    if not info:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    return templates.TemplateResponse(
        "stock.html",
        {
            "request": request,
            "title": f"Analyze {symbol.upper()}",
            "symbol": symbol.upper(),
            "stock_info": info,
        },
    )


@pages_router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    """Portfolio page."""
    templates = request.app.state.templates

    # Get portfolio data
    init_database()
    from stockai.core.portfolio import PnLCalculator

    pnl_calc = PnLCalculator()
    summary = pnl_calc.get_portfolio_summary()

    return templates.TemplateResponse(
        "portfolio.html",
        {
            "request": request,
            "title": "Portfolio",
            "portfolio": summary,
        },
    )


@pages_router.get("/sentiment", response_class=HTMLResponse)
async def sentiment_page(request: Request):
    """Legacy sentiment route (kept for compatibility)."""
    templates = request.app.state.templates

    return templates.TemplateResponse(
        "alerts.html",
        {
            "request": request,
            "title": "Alerts",
            "legacy_mode": True,
        },
    )


@pages_router.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request):
    """Notification center page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "alerts.html",
        {
            "request": request,
            "title": "Alerts",
        },
    )


@api_router.get("/predictions/accuracy")
async def get_prediction_accuracy() -> dict:
    """Get overall prediction accuracy metrics.

    Returns accuracy statistics across all evaluated predictions including:
    - Overall accuracy rate
    - Accuracy breakdown by direction (UP/DOWN/NEUTRAL)
    - Accuracy breakdown by confidence level (HIGH/MEDIUM/LOW)
    """
    init_database()

    tracker = PredictionAccuracyTracker()
    metrics = tracker.get_accuracy_metrics()

    return metrics


@api_router.get("/predictions/accuracy/{symbol}")
async def get_stock_accuracy(symbol: str) -> dict:
    """Get prediction accuracy metrics for a specific stock.

    Returns stock-specific accuracy statistics including:
    - Overall accuracy rate for the stock
    - Accuracy breakdown by direction (UP/DOWN/NEUTRAL)
    - Accuracy breakdown by confidence level (HIGH/MEDIUM/LOW)
    - Recent predictions with outcomes
    - Monthly accuracy trend

    Args:
        symbol: Stock ticker symbol (e.g., "BBRI.JK")

    Raises:
        HTTPException 404: If the stock is not found or has no predictions
    """
    init_database()

    tracker = PredictionAccuracyTracker()
    metrics = tracker.get_stock_accuracy(symbol.upper())

    # Check if stock was not found or has no predictions
    if "message" in metrics:
        raise HTTPException(
            status_code=404,
            detail=metrics["message"],
        )

    return metrics


@api_router.post("/predictions/backfill")
async def backfill_prediction_accuracy() -> dict:
    """Trigger accuracy backfill for past predictions.

    Updates all predictions where target_date has passed but accuracy
    has not yet been calculated. Fetches actual price data and determines
    if each prediction was correct.

    Returns:
        Dictionary with backfill statistics:
        - updated_count: Number of predictions successfully updated
        - skipped_count: Number of predictions skipped (missing price data)
        - error_count: Number of predictions that encountered errors
        - total_pending: Total number of predictions that needed updating
    """
    init_database()

    tracker = PredictionAccuracyTracker()
    result = tracker.update_past_predictions()

    return result


@api_router.get("/export/{symbol}")
async def export_stock_report(symbol: str) -> dict:
    """Generate stock analysis report data for PDF export.

    Returns comprehensive analysis data that can be used
    to generate a PDF report client-side or server-side.
    """
    from datetime import datetime
    from stockai.core.sentiment import SentimentAnalyzer, NewsAggregator

    symbol = symbol.upper()
    report_data: dict[str, Any] = {
        "symbol": symbol,
        "generated_at": datetime.utcnow().isoformat(),
        "version": __version__,
    }

    # Get stock info
    idx_source = IDXIndexSource()
    stock_info = idx_source.get_stock_details(symbol)

    if not stock_info:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    report_data["stock_info"] = stock_info

    # Get price history
    yahoo = YahooFinanceSource()
    df = yahoo.get_price_history(symbol, period="3mo")

    if not df.empty:
        history = []
        for _, row in df.tail(30).iterrows():  # Last 30 days
            history.append({
                "date": row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"]),
                "close": round(row["close"], 2),
                "volume": int(row["volume"]),
            })
        report_data["price_history"] = history

        # Calculate basic stats
        if len(df) > 1:
            first_close = df.iloc[0]["close"]
            last_close = df.iloc[-1]["close"]
            change_pct = ((last_close - first_close) / first_close) * 100

            report_data["price_stats"] = {
                "current_price": round(last_close, 2),
                "period_change_pct": round(change_pct, 2),
                "high": round(df["high"].max(), 2),
                "low": round(df["low"].min(), 2),
                "avg_volume": int(df["volume"].mean()),
            }

    # Get sentiment
    try:
        news_agg = NewsAggregator()
        articles = news_agg.fetch_all(symbol, max_articles=10, days_back=7)

        if articles:
            analyzer = SentimentAnalyzer()
            aggregated = analyzer.aggregate_sentiment(articles, symbol)
            report_data["sentiment"] = {
                "overall": aggregated.dominant_label.value,
                "score": round(aggregated.avg_sentiment_score, 2),
                "confidence": round(aggregated.confidence, 2),
                "article_count": aggregated.article_count,
                "signal_strength": aggregated.signal_strength,
            }
    except Exception:
        report_data["sentiment"] = None

    # Get prediction (if models available)
    try:
        settings = get_settings()
        model_dir = settings.project_root / "data" / "models"

        ensemble = EnsemblePredictor(
            xgboost_path=model_dir / "xgboost_v1.json",
        )

        if not df.empty and len(df) >= 50:
            loaded = ensemble.load_models()
            if any(loaded.values()):
                result = ensemble.predict(df)
                report_data["prediction"] = {
                    "direction": result.get("direction"),
                    "confidence": round(result.get("confidence", 0), 2),
                    "confidence_level": result.get("confidence_level"),
                }
    except Exception:
        report_data["prediction"] = None

    return report_data
