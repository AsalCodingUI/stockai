"""Telegram notification sender untuk AI Entry Coach alerts."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from dotenv import load_dotenv

if TYPE_CHECKING:
    from stockai.core.coach import CoachDecision

logger = logging.getLogger(__name__)


def _get_telegram_config() -> tuple[str, str] | None:
    """Get BOT_TOKEN and CHAT_ID from environment (.env.local/.env supported)."""
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env.local", override=False)
    load_dotenv(project_root / ".env", override=False)

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        return None
    return bot_token, chat_id


def _format_alert(d: "CoachDecision") -> str:
    action_emoji = {"ENTRY_NOW": "🟢", "WAIT": "🟡", "AVOID": "🔴"}.get(d.action, "⚪")
    action_text = {
        "ENTRY_NOW": "MASUK SEKARANG",
        "WAIT": "TUNGGU DULU",
        "AVOID": "HINDARI",
    }.get(d.action, d.action)

    tujuan_map = {
        "scalp": "Scalping (1-2 minggu)",
        "swing": "Swing (1-2 bulan)",
        "invest": "Investasi (6+ bulan)",
    }

    lines = [
        f"{action_emoji} *{d.symbol}* - {action_text}",
        f"Confidence: {d.confidence}%",
        "",
        f"📝 _{d.summary}_",
        "",
        "💰 *Setup Entry*",
        f"• Entry: Rp {d.entry_low:,.0f} - {d.entry_high:,.0f}".replace(",", "."),
        f"• Stop Loss: Rp {d.stop_loss:,.0f}".replace(",", "."),
        f"• Target 1: Rp {d.target1:,.0f}".replace(",", "."),
        f"• Target 2: Rp {d.target2:,.0f}".replace(",", "."),
        f"• Risk/Reward: 1:{d.risk_reward}",
    ]

    if d.suggested_lot > 0:
        modal_fmt = f"Rp {d.modal:,.0f}".replace(",", ".")
        lines += [
            "",
            f"📦 *Posisi ({tujuan_map.get(d.tujuan, d.tujuan)})*",
            f"• Modal: {modal_fmt}",
            f"• Saran lot: {d.suggested_lot} lot",
        ]

    if d.reason_entry:
        lines += ["", "✅ *Kenapa masuk:*"]
        lines += [f"• {r}" for r in d.reason_entry[:3]]
    if d.reason_wait:
        lines += ["", "⚠️ *Perhatian:*"]
        lines += [f"• {r}" for r in d.reason_wait[:2]]
    if d.warning:
        lines += ["", "🚨 *Risiko:*"]
        lines += [f"• {w}" for w in d.warning[:2]]
    if d.what_to_wait:
        lines += ["", "⏳ *Yang harus terjadi dulu:*", f"_{d.what_to_wait}_"]

    if d.snapshot:
        snap = d.snapshot
        lines += [
            "",
            "📊 *Teknikal*",
            f"• Harga: Rp {snap.price:,.0f} ({snap.change_pct:+.2f}%)".replace(",", "."),
            f"• RSI: {snap.rsi} | Gate: {snap.gate_score}/5",
            f"• Trend: {snap.trend}",
            f"• Volume: {snap.vol_ratio:.1f}x rata-rata",
        ]

    lines += [
        "",
        f"🕐 {d.timestamp[:16].replace('T', ' ')} WIB",
        "━━━━━━━━━━━━━━━━━━━━",
        "_StockAI Entry Coach_",
    ]
    return "\n".join(lines)


async def send_coach_alert(decision: "CoachDecision") -> bool:
    """Send Telegram alert for coach decision."""
    config = _get_telegram_config()
    if not config:
        logger.warning("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        return False

    bot_token, chat_id = config
    message = _format_alert(decision)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            )
            resp.raise_for_status()
            logger.info("Telegram alert sent: %s", decision.symbol)
            return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False


async def send_simple_message(text: str) -> bool:
    """Send plain text to Telegram."""
    config = _get_telegram_config()
    if not config:
        return False
    bot_token, chat_id = config
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text})
            resp.raise_for_status()
            return True
    except Exception as exc:
        logger.error("Telegram test failed: %s", exc)
        return False
