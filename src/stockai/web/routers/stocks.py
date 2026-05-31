"""Stocks router — /stock/{symbol}/*, /stocks/*, /sentiment, /predict*, /export, /predictions."""

import asyncio
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from stockai import __version__
from stockai.config import get_settings
from stockai.core.decision_engine import decision_to_trade_plan, generate_unified_decision
from stockai.core.foreign_flow import ForeignFlowMonitor
from stockai.core.ml.probability import ProbabilityEngine
from stockai.core.monitor import get_monitor
from stockai.core.predictor import EnsemblePredictor, PredictionAccuracyTracker
from stockai.core.realtime import get_realtime_pipeline
from stockai.core.sentiment.stockbit import StockbitSentiment
from stockai.core.volume_detector import UnusualVolumeDetector
from stockai.data.cache import async_cached, memory_cache_get, memory_cache_set
from stockai.data.database import init_database
from stockai.data.sources.idx import IDXIndexSource
from stockai.data.sources.yahoo import YahooFinanceSource
from stockai.scoring.analyzer import analyze_stock, GateConfig
from stockai.web.utils import (
    _build_trade_plan_fallback,
    _normalize_indicator_period,
    _normalize_tujuan,
    _now_iso,
    _price_or_none,
    _resolve_period,
    _safe_support_distance_pct,
    _symbol_to_yf,
    _to_native,
)

router = APIRouter(tags=["stocks"])


@router.get("/stock/{symbol}/full")
async def get_stock_full(
    symbol: str,
    tujuan: str = Query("swing", description="scalp | swing | invest"),
    min_tp: float | None = Query(None, description="Minimum take profit percentage"),
    min_cl: float | None = Query(None, description="Minimum cut loss percentage"),
) -> dict:
    clean_symbol = symbol.upper().strip()
    tujuan_clean = _normalize_tujuan(tujuan)
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

    support_distance_pct = _safe_support_distance_pct(analysis)
    monitor = get_monitor()
    market_ctx = getattr(monitor, "_last_market_context", None) or {
        "ihsg_trend": "UNKNOWN",
        "market_breadth": "MIXED",
        "advance_ratio": 0.5,
        "leading_sector": "UNKNOWN",
        "lagging_sector": "UNKNOWN",
    }
    sentiment_label = str(sentiment_signal.get("sentiment", "NEUTRAL")).upper()
    sentiment_raw = float(sentiment_signal.get("score", 0))
    sentiment_score = max(0.0, min(100.0, 50.0 + sentiment_raw * 5.0))
    news_bias = (
        "POSITIVE" if sentiment_label == "BULLISH"
        else "NEGATIVE" if sentiment_label == "BEARISH"
        else "NEUTRAL"
    )
    unified_decision = await generate_unified_decision(
        symbol=clean_symbol,
        df=history,
        modal=5_000_000,
        tujuan=tujuan_clean,
        ihsg_trend=str(market_ctx.get("ihsg_trend", "UNKNOWN")),
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        news_bias=news_bias,
        market_breadth=str(market_ctx.get("market_breadth", "MIXED")),
        advance_ratio=float(market_ctx.get("advance_ratio", 0.5)),
        leading_sector=str(market_ctx.get("leading_sector", "UNKNOWN")),
        lagging_sector=str(market_ctx.get("lagging_sector", "UNKNOWN")),
        mtf_score=0,
    )
    unified_trade_plan = decision_to_trade_plan(unified_decision, min_tp=min_tp, min_cl=min_cl)

    forecast = probability.forecast(
        clean_symbol,
        {
            "volume_ratio": volume_signal.get("volume_ratio", 0),
            "adx": analysis.adx.get("adx", 0),
            "near_support": (
                support_distance_pct <= 10 if support_distance_pct is not None else False
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
        {"name": "Support", "passed": support_distance_pct <= 10 if support_distance_pct is not None else False, "value": round(float(support_distance_pct or 0), 2), "threshold": 10},
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
            "gates": {
                "passed": int(getattr(analysis.gates, "gates_passed", 0)),
                "total": int(getattr(analysis.gates, "total_gates", 6)),
                "confidence": getattr(analysis.gates, "confidence", "REJECTED"),
                "reasons": list(getattr(analysis.gates, "rejection_reasons", [])),
                "all_passed": bool(getattr(analysis.gates, "all_passed", False)),
            },
            "gate_status": gate_status,
            "trade_plan": unified_trade_plan,
            "trade_plan_legacy": _build_trade_plan_fallback(analysis, _price_or_none(analysis.current_price)),
            "unified_decision": _to_native(
                {
                    "action": unified_decision.action,
                    "confidence": unified_decision.confidence,
                    "summary": unified_decision.summary,
                    "warning": unified_decision.warning[:3],
                    "tujuan": tujuan_clean,
                }
            ),
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


@router.get("/stock/{symbol}/scoring")
async def get_stock_scoring(
    symbol: str,
    tujuan: str = Query("swing", description="scalp | swing | invest"),
    min_tp: float | None = Query(None, description="Minimum take profit percentage"),
    min_cl: float | None = Query(None, description="Minimum cut loss percentage"),
) -> dict:
    """Fast stock scoring endpoint without heavy ML/news aggregation."""
    clean_symbol = symbol.upper().strip()
    tujuan_clean = _normalize_tujuan(tujuan)
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
    sentiment_signal = StockbitSentiment().analyze(clean_symbol)
    monitor = get_monitor()
    market_ctx = getattr(monitor, "_last_market_context", None) or {
        "ihsg_trend": "UNKNOWN",
        "market_breadth": "MIXED",
        "advance_ratio": 0.5,
        "leading_sector": "UNKNOWN",
        "lagging_sector": "UNKNOWN",
    }
    sentiment_label = str(sentiment_signal.get("sentiment", "NEUTRAL")).upper()
    sentiment_raw = float(sentiment_signal.get("score", 0))
    sentiment_score = max(0.0, min(100.0, 50.0 + sentiment_raw * 5.0))
    news_bias = (
        "POSITIVE" if sentiment_label == "BULLISH"
        else "NEGATIVE" if sentiment_label == "BEARISH"
        else "NEUTRAL"
    )
    unified_decision = await generate_unified_decision(
        symbol=clean_symbol,
        df=history,
        modal=5_000_000,
        tujuan=tujuan_clean,
        ihsg_trend=str(market_ctx.get("ihsg_trend", "UNKNOWN")),
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        news_bias=news_bias,
        market_breadth=str(market_ctx.get("market_breadth", "MIXED")),
        advance_ratio=float(market_ctx.get("advance_ratio", 0.5)),
        leading_sector=str(market_ctx.get("leading_sector", "UNKNOWN")),
        lagging_sector=str(market_ctx.get("lagging_sector", "UNKNOWN")),
        mtf_score=0,
    )
    unified_trade_plan = decision_to_trade_plan(unified_decision, min_tp=min_tp, min_cl=min_cl)

    sr = getattr(analysis, "support_resistance", None)
    sr_resistances = getattr(sr, "resistances", None) if sr else None
    sr_resistance = _price_or_none(sr_resistances[0]) if isinstance(sr_resistances, list) and sr_resistances else None
    if sr_resistance is None:
        sr_resistance = _price_or_none(getattr(sr, "nearest_resistance", None)) if sr else None

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
        "trade_plan": unified_trade_plan,
        "trade_plan_legacy": _build_trade_plan_fallback(analysis, _price_or_none(analysis.current_price)),
        "unified_decision": _to_native(
            {
                "action": unified_decision.action,
                "confidence": unified_decision.confidence,
                "summary": unified_decision.summary,
                "warning": unified_decision.warning[:3],
                "tujuan": tujuan_clean,
            }
        ),
        "support_resistance": {
            "support": _price_or_none(getattr(sr, "nearest_support", None)) if sr else None,
            "resistance": sr_resistance,
            "distance_to_support_pct": _price_or_none(getattr(sr, "distance_to_support_pct", None)) if sr else None,
        },
    }
    return _to_native(payload)


@router.get("/stock/{symbol}/indicators")
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


@router.get("/stock/{symbol}/chart")
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


@router.get("/stocks")
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


@router.get("/stocks/{symbol}")
async def get_stock_info(symbol: str) -> dict:
    """Get detailed stock information."""
    idx_source = IDXIndexSource()
    info = idx_source.get_stock_details(symbol.upper())

    if not info:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    return info


@router.get("/stocks/{symbol}/history")
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


@router.get("/stocks/{symbol}/chart")
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


@router.get("/sentiment/{symbol}")
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


@router.get("/predict/{symbol}")
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


@router.get("/predictions/accuracy")
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


@router.get("/predictions/accuracy/{symbol}")
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


@router.post("/predictions/backfill")
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


@router.get("/export/{symbol}")
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
