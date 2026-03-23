"""Scheduled job handlers for daily automation."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import requests
from dotenv import load_dotenv

from stockai.autopilot import AutopilotConfig, AutopilotEngine
from stockai.autopilot.engine import IndexType
from stockai.config import get_settings
from stockai.core.portfolio import PnLCalculator
from stockai.data.cache import memory_cache_get, memory_cache_set

logger = logging.getLogger(__name__)

JAKARTA_LABEL = "WIB"
SCAN_HISTORY_KEY = "scheduler:scan_history"
MORNING_KEY = "scheduler:morning_scan"


def _fmt_date(now: datetime) -> str:
    return now.strftime("%A %d %b %Y")


def _safe_prob_line(signal: Any) -> str:
    p5 = signal.probability_5pct if signal and signal.probability_5pct is not None else 0.0
    patt = signal.pattern_dominant or "-"
    return f"🎯 Prob +5%: {p5:.0%} | Pattern: {patt}"


def _market_note() -> str:
    try:
        import yfinance as yf

        df = yf.Ticker("^JKSE").history(period="5d", interval="1d")
        if not df.empty and len(df) >= 2:
            last_close = float(df["Close"].iloc[-1])
            prev_close = float(df["Close"].iloc[-2])
            pct = ((last_close / prev_close) - 1) * 100 if prev_close else 0
            regime = "RISK_OFF" if pct < 0 else "RISK_ON"
            sign = "+" if pct >= 0 else ""
            return f"⚠️  Market: {regime} (IHSG {sign}{pct:.1f}%)"
    except Exception:
        pass
    return "⚠️  Market: NEUTRAL"


def _send_telegram(message: str) -> None:
    settings = get_settings()
    project_root = settings.project_root
    # Force override so runtime always follows current .env.local/.env values.
    load_dotenv(project_root / ".env.local", override=True)
    load_dotenv(project_root / ".env", override=True)

    token = (
        os.getenv("STOCKAI_TELEGRAM_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
    )
    chat_id = (
        os.getenv("STOCKAI_TELEGRAM_CHAT")
        or os.getenv("TELEGRAM_CHAT_ID")
    )
    if not token or not chat_id:
        logger.info("Telegram env not set (.env/.env.local), skipping notification")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logger.warning("Telegram send failed (HTTP %s): %s", response.status_code, response.text[:200])
            return
        body = response.json()
        if not body.get("ok", False):
            logger.warning("Telegram send failed (API): %s", body)
            return
        masked_chat = f"...{str(chat_id)[-4:]}" if str(chat_id) else "unknown"
        logger.info("Telegram message sent successfully to chat %s", masked_chat)
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)


def _scan(index: IndexType) -> Any:
    config = AutopilotConfig(
        index=index,
        capital=10_000_000,
        dry_run=True,
        ai_enabled=False,
    )
    engine = AutopilotEngine(config=config)
    return engine.run()


def _record_scan_history(kind: str, result: Any) -> None:
    history = memory_cache_get(SCAN_HISTORY_KEY)
    if not isinstance(history, list):
        history = []
    history.append({
        "kind": kind,
        "timestamp": datetime.now().isoformat(),
        "scanned": int(result.stocks_scanned),
        "watch": len(result.gate_qualified_buys),
        "ready": len([s for s in result.gate_qualified_buys if (s.gates_passed or 0) >= 5]),
    })
    memory_cache_set(SCAN_HISTORY_KEY, history[-200:], ttl=60 * 60 * 24 * 14)


async def morning_scan() -> dict[str, Any]:
    """08:45 WIB — Main daily scan + Telegram report."""
    now = datetime.now()
    result = _scan(IndexType.ALL)
    _record_scan_history("morning", result)

    ready = len([s for s in result.gate_qualified_buys if (s.gates_passed or 0) >= 5])
    watch = len(result.gate_qualified_buys)
    top = result.gate_qualified_buys[0] if result.gate_qualified_buys else None

    lines = [
        f"🌅 MORNING SCAN — {_fmt_date(now)}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 Scanned: {result.stocks_scanned} saham",
        f"✅ READY: {ready} | 👀 WATCH: {watch}",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    if top:
        rr = getattr(top.analysis_result.trade_plan, "risk_reward_ratio", None) if top.analysis_result and top.analysis_result.trade_plan else None
        lines.extend([
            f"👀 {top.symbol} @ Rp {top.current_price:,.0f}",
            f"SL: {top.stop_loss or 0:.0f} | TP: {top.target or 0:.0f} | R/R: {rr:.1f}x" if rr else f"SL: {top.stop_loss or 0:.0f} | TP: {top.target or 0:.0f}",
            _safe_prob_line(top),
        ])
    else:
        lines.append("Tidak ada kandidat WATCH/READY pagi ini.")
    lines.extend(["━━━━━━━━━━━━━━━━━━━━", _market_note()])
    msg = "\n".join(lines)
    _send_telegram(msg)

    result_rows = []
    for signal in result.gate_qualified_buys[:30]:
        status = "READY" if (signal.gates_passed or 0) >= 5 else "WATCH"
        result_rows.append(
            {
                "symbol": signal.symbol,
                "score": round(float(signal.score), 1),
                "gate_passed": int(signal.gates_passed or 0),
                "gate_total": int(signal.gates_total or 6),
                "status": status,
                "current_price": float(signal.current_price or 0),
                "sl": float(signal.stop_loss or 0) if signal.stop_loss else None,
                "tp1": float(signal.target or 0) if signal.target else None,
                "rr": (
                    float(signal.analysis_result.trade_plan.risk_reward_ratio)
                    if signal.analysis_result and signal.analysis_result.trade_plan
                    else None
                ),
            }
        )

    payload = {
        "timestamp": now.isoformat(),
        "index": "ALL",
        "scanned": int(result.stocks_scanned),
        "ready": ready,
        "watch": watch,
        "signals": [s.symbol for s in result.gate_qualified_buys[:20]],
        "results": result_rows,
        "message": msg,
    }
    memory_cache_set(MORNING_KEY, payload, ttl=60 * 60 * 12)

    try:
        from stockai.web import routes as web_routes

        web_routes._WEB_RUNTIME["last_scan"] = {
            "index": "ALL",
            "scanned": int(result.stocks_scanned),
            "timestamp": now.isoformat(),
            "results": result_rows,
        }
        web_routes._WEB_RUNTIME["last_scan_at"] = datetime.utcnow()
    except Exception:
        pass
    return payload


async def midday_check() -> dict[str, Any]:
    """11:30 WIB — Monitor positions and SL/TP proximity."""
    pnl = PnLCalculator().get_portfolio_summary()
    positions = pnl.get("positions", [])
    alerts = []
    for pos in positions:
        symbol = pos.get("symbol")
        current = float(pos.get("current_price") or 0)
        avg = float(pos.get("avg_cost") or 0)
        if not symbol or current <= 0 or avg <= 0:
            continue
        sl = avg * 0.95
        tp1 = avg * 1.10
        if current <= sl * 1.02:
            loss_pct = ((current / sl) - 1) * 100 if sl else 0
            alerts.append(
                f"🚨 SL ALERT — {symbol}\nHarga: Rp {current:,.0f} | SL: Rp {sl:,.0f}\n⚠️ Hampir kena SL! ({loss_pct:+.2f}%)"
            )
        elif current >= tp1:
            gain_pct = ((current / avg) - 1) * 100 if avg else 0
            alerts.append(
                f"🎯 TP1 REACHED — {symbol}\nEntry: {avg:,.0f} → Now: {current:,.0f} ({gain_pct:+.1f}%)\n💡 Pertimbangkan partial profit"
            )
    if alerts:
        _send_telegram("\n\n".join(alerts[:5]))
    return {"checked": len(positions), "alerts": len(alerts)}


async def closing_scan() -> dict[str, Any]:
    """15:45 WIB — Quick LQ45 scan and compare with morning."""
    result = _scan(IndexType.LQ45)
    _record_scan_history("closing", result)
    morning = memory_cache_get(MORNING_KEY) or {}
    morning_set = set(morning.get("signals", [])) if isinstance(morning, dict) else set()
    new_signals = [s for s in result.gate_qualified_buys if s.symbol not in morning_set]
    if new_signals:
        top = new_signals[0]
        msg = (
            "📊 CLOSING UPDATE\n"
            f"Sinyal baru: {top.symbol} masuk WATCHLIST\n"
            f"Score: {top.score:.0f} | Gate: {top.gates_passed or 0}/{top.gates_total}"
        )
        _send_telegram(msg)
    return {"scanned": int(result.stocks_scanned), "new_signals": len(new_signals)}


async def weekend_summary() -> dict[str, Any]:
    """Saturday summary with weekly performance snapshot."""
    history = memory_cache_get(SCAN_HISTORY_KEY)
    if not isinstance(history, list):
        history = []
    week_rows = history[-20:]
    watch_total = sum(int(r.get("watch", 0)) for r in week_rows)
    ready_total = sum(int(r.get("ready", 0)) for r in week_rows)

    source = YahooFinanceSource()
    ihsg_change = 0.0
    try:
        df = source.get_price_history("^JKSE", period="1wk")
        if not df.empty and len(df) >= 2:
            ihsg_change = ((float(df["close"].iloc[-1]) / float(df["close"].iloc[0])) - 1) * 100
    except Exception:
        pass

    top_rows = sorted(week_rows, key=lambda x: (x.get("watch", 0), x.get("ready", 0)), reverse=True)[:3]
    lines = [
        f"📅 WEEKLY SUMMARY — Week {datetime.now().isocalendar().week}, {datetime.now().year}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"IHSG: {ihsg_change:+.1f}% minggu ini",
        f"Sinyal minggu ini: {watch_total} WATCH, {ready_total} READY",
        "━━━━━━━━━━━━━━━━━━━━",
        "🏆 Top picks minggu ini:",
    ]
    for i, row in enumerate(top_rows, start=1):
        lines.append(f"{i}. {row.get('kind', 'scan').upper()} — WATCH {row.get('watch', 0)} READY {row.get('ready', 0)}")
    _send_telegram("\n".join(lines))
    return {"rows": len(week_rows), "watch_total": watch_total, "ready_total": ready_total}
