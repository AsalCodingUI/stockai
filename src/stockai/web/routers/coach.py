"""Coach router — /coach/*, /realtime/*, /adaptive/* endpoints."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from stockai.core.adaptive import get_adaptive_weight_engine
from stockai.core.decision_engine import generate_unified_decision
from stockai.core.monitor import get_monitor
from stockai.core.realtime import get_realtime_pipeline
from stockai.core.watchlist import get_watchlist as get_local_watchlist
from stockai.data.sources.yahoo import YahooFinanceSource
from stockai.web.utils import _to_native

router = APIRouter(tags=["coach"])


@router.get("/coach/watchlist")
async def get_coach_watchlist_api() -> dict[str, Any]:
    wl = get_local_watchlist()
    stocks = wl.get_all()
    return {"stocks": stocks, "count": len(stocks)}


@router.post("/coach/watchlist")
async def add_coach_watchlist_api(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = str(payload.get("symbol", "")).upper().strip()
    modal = int(payload.get("modal", 5_000_000))
    tujuan = str(payload.get("tujuan", "swing"))
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol wajib diisi")

    wl = get_local_watchlist()
    result = wl.add(symbol, modal=modal, tujuan=tujuan)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("reason", "Gagal tambah watchlist"))
    return result


@router.delete("/coach/watchlist/{symbol}")
async def remove_coach_watchlist_api(symbol: str) -> dict[str, Any]:
    wl = get_local_watchlist()
    result = wl.remove(symbol.upper())
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("reason", "Tidak ditemukan"))
    return result


@router.get("/coach/analyze/{symbol}")
async def analyze_coach_stock_api(
    symbol: str,
    modal: int = Query(5_000_000, description="Modal investasi (Rp)"),
    tujuan: str = Query("swing", description="scalp | swing | invest"),
) -> dict[str, Any]:
    from stockai.data.sources.yahoo import YahooFinanceSource
    from stockai.core.sentiment.stockbit import StockbitSentiment
    from stockai.core.sentiment.news import NewsAggregator

    clean = symbol.upper().strip()
    yahoo = YahooFinanceSource()
    df = yahoo.get_price_history(clean, period="3mo")
    if df.empty or len(df) < 30:
        raise HTTPException(status_code=404, detail=f"Data tidak cukup untuk {clean}")

    try:
        monitor = get_monitor()
        market_ctx = getattr(monitor, "_last_market_context", None) or {}
        if not market_ctx:
            try:
                market_ctx = await monitor._get_market_context(yahoo)
            except Exception:
                market_ctx = {
                    "ihsg_trend": "UNKNOWN",
                    "market_breadth": "MIXED",
                    "advance_ratio": 0.5,
                    "leading_sector": "UNKNOWN",
                    "lagging_sector": "UNKNOWN",
                }

        sentiment_signal = await asyncio.to_thread(StockbitSentiment().analyze, clean)
        sentiment_label = str(sentiment_signal.get("sentiment", "NEUTRAL")).upper()
        sentiment_raw = float(sentiment_signal.get("score", 0))
        sentiment_score = max(0.0, min(100.0, 50.0 + sentiment_raw * 5.0))
        news_bias = (
            "POSITIVE" if sentiment_label == "BULLISH"
            else "NEGATIVE" if sentiment_label == "BEARISH"
            else "NEUTRAL"
        )
        try:
            articles = await asyncio.to_thread(
                lambda: NewsAggregator().fetch_google_news(clean, max_articles=8)
            )
            pos_kw = ("naik", "optimis", "bullish", "outperform", "accumulate", "buy")
            neg_kw = ("turun", "melemah", "bearish", "downgrade", "sell", "risiko")
            score = 0
            for article in articles:
                title = str(getattr(article, "title", "")).lower()
                if any(k in title for k in pos_kw):
                    score += 1
                if any(k in title for k in neg_kw):
                    score -= 1
            if score > 1:
                news_bias = "POSITIVE"
            elif score < -1:
                news_bias = "NEGATIVE"
        except Exception:
            pass

        decision = await generate_unified_decision(
            symbol=clean,
            df=df,
            modal=modal,
            tujuan=tujuan,
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    payload = decision.__dict__.copy()
    payload["snapshot"] = _to_native(decision.snapshot.__dict__) if decision.snapshot else None
    get_realtime_pipeline().publish(
        {
            "type": "manual_analyze",
            "symbol": clean,
            "action": decision.action,
            "confidence": decision.confidence,
            "modal": modal,
            "tujuan": tujuan,
        }
    )
    return _to_native(payload)


@router.post("/coach/scan")
async def trigger_coach_scan_api() -> dict[str, Any]:
    monitor = get_monitor()
    asyncio.create_task(monitor._scan_all())
    return {"message": "Scan dimulai di background"}


@router.get("/coach/monitor/status")
async def get_coach_monitor_status_api() -> dict[str, Any]:
    monitor = get_monitor()
    return _to_native(monitor.get_status())


@router.get("/coach/monitor/logs")
async def get_coach_monitor_logs_api(
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    monitor = get_monitor()
    decisions = monitor.get_recent_decisions(limit=limit)
    alerts = monitor.get_recent_alerts(limit=limit)
    return _to_native(
        {
            "limit": limit,
            "decisions": decisions,
            "alerts": alerts,
            "decision_count": len(decisions),
            "alert_count": len(alerts),
        }
    )


@router.get("/realtime/status")
async def get_realtime_status_api() -> dict[str, Any]:
    return _to_native(get_realtime_pipeline().status())


@router.get("/realtime/signals")
async def get_realtime_signals_api(limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    rows = get_realtime_pipeline().get_recent(limit=limit)
    return _to_native({"count": len(rows), "signals": rows})


@router.get("/adaptive/status")
async def get_adaptive_status_api() -> dict[str, Any]:
    return _to_native(get_adaptive_weight_engine().get_status())


@router.post("/adaptive/feedback")
async def post_adaptive_feedback_api(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = str(payload.get("symbol", "")).upper().strip()
    action = str(payload.get("action", "ENTRY_NOW")).upper()
    confidence = int(payload.get("predicted_confidence", 50))
    realized = float(payload.get("realized_return_pct", 0.0))
    hold_days = int(payload.get("hold_days", 1))
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol wajib diisi")

    row = get_adaptive_weight_engine().record_outcome(
        symbol=symbol,
        action=action,
        predicted_confidence=confidence,
        realized_return_pct=realized,
        hold_days=hold_days,
    )
    get_realtime_pipeline().publish({"type": "adaptive_feedback", **row})
    return _to_native({"success": True, "result": row})


@router.post("/coach/test-telegram")
async def test_coach_telegram_api() -> dict[str, Any]:
    from stockai.notifications.telegram import send_simple_message

    ok = await send_simple_message(
        "✅ StockAI Entry Coach terhubung!\n"
        "Kamu akan menerima alert sinyal masuk saham di sini."
    )
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Gagal kirim ke Telegram. Cek TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di .env/.env.local",
        )
    return {"success": True}
