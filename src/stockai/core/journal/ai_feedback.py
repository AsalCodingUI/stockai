"""AI Feedback Loop for Trade Journal.

Analyses the trader's historical plans/outcomes with Gemini and returns
structured coaching feedback. Falls back to rule-based stats if no API key.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _rule_based_feedback(stats: dict, plans: list[dict]) -> dict:
    """Fallback: pure-statistics coaching without LLM."""
    win_rate = stats.get("win_rate", 0)
    avg_pnl = stats.get("avg_pnl_pct", 0)
    total = stats.get("total", 0)
    closed = stats.get("closed", 0)

    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []

    if win_rate >= 60:
        strengths.append(f"Win rate {win_rate:.1f}% — di atas rata-rata (>60%). Seleksi saham sudah cukup baik.")
    elif win_rate >= 40:
        weaknesses.append(f"Win rate {win_rate:.1f}% masih di zona rata-rata. Perlu perbaikan entry timing.")
    else:
        weaknesses.append(f"Win rate {win_rate:.1f}% — terlalu rendah. Evaluasi ulang kriteria entry.")

    if avg_pnl > 3:
        strengths.append(f"Rata-rata P&L +{avg_pnl:.1f}% — risk/reward sudah positif.")
    elif avg_pnl < 0:
        weaknesses.append(f"Rata-rata P&L {avg_pnl:.1f}% negatif — SL mungkin terlalu sempit atau TP terlalu jauh.")

    # Check symbol concentration
    by_symbol = stats.get("by_symbol", {})
    if by_symbol:
        worst = min(by_symbol.items(), key=lambda x: x[1].get("wins", 0) - x[1].get("losses", 0), default=None)
        best = max(by_symbol.items(), key=lambda x: x[1].get("wins", 0) - x[1].get("losses", 0), default=None)
        if worst and worst[1].get("losses", 0) > worst[1].get("wins", 0):
            weaknesses.append(f"Saham {worst[0]} sering loss — pertimbangkan untuk skip saham ini sementara.")
        if best and best[1].get("wins", 0) > 0:
            strengths.append(f"Saham {best[0]} performanya bagus — pertimbangkan alokasi lebih besar.")

    # Suggestions
    if closed < 5:
        suggestions.append("Belum cukup data untuk analisis mendalam. Butuh minimal 10 closed plans.")
    else:
        if win_rate < 50:
            suggestions.append("Coba tingkatkan minimum gate yang harus pass sebelum entry (misal: 5/6 instead of 4/6).")
        if avg_pnl < 0:
            suggestions.append("Review ulang posisi SL — pastikan SL di bawah support kuat, bukan hanya % arbitrary.")
        suggestions.append("Tambahkan notes alasan entry di setiap plan untuk pattern recognition yang lebih baik.")

    return {
        "source": "rule_based",
        "summary": (
            f"Dari {total} total plan ({closed} closed, {stats.get('open', 0)} open): "
            f"win rate {win_rate:.1f}%, rata-rata P&L {avg_pnl:+.1f}%."
        ),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "win_rate_analysis": {
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "total_trades": closed,
            "grade": "A" if win_rate >= 65 else "B" if win_rate >= 50 else "C" if win_rate >= 35 else "D",
        },
    }


def analyze_journal_patterns(stats: dict, plans: list[dict]) -> dict:
    """Main entry point. Uses Gemini if available, else rule-based."""
    try:
        from stockai.config import get_settings
        settings = get_settings()
        if not settings.has_google_api:
            raise ValueError("No Google API key")

        return _gemini_feedback(stats, plans, settings)
    except Exception as exc:
        logger.info("AI feedback falling back to rule-based: %s", exc)
        return _rule_based_feedback(stats, plans)


def _gemini_feedback(stats: dict, plans: list[dict], settings: Any) -> dict:
    """Call Gemini to analyse trading patterns."""
    import google.generativeai as genai

    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Build compact context
    closed_plans = [p for p in plans if p.get("status") not in ("OPEN", "CANCELLED")]
    plan_lines = []
    for p in closed_plans[-30:]:  # last 30 trades
        plan_lines.append(
            f"- {p['symbol']} | {p['tujuan']} | {p['status']} | "
            f"P&L: {p.get('pnl_pct', 0):+.1f}% | "
            f"Days held: {p.get('days_held', 0)} | "
            f"R/R: {p.get('risk_reward', 0):.2f} | "
            f"Notes: {(p.get('notes') or '')[:80]}"
        )

    prompt = f"""Kamu adalah trading coach profesional untuk pasar saham Indonesia (IDX).
Analisa history trading berikut dan berikan feedback yang konstruktif dan actionable dalam Bahasa Indonesia.

STATISTIK:
- Total plans: {stats.get('total', 0)}
- Closed: {stats.get('closed', 0)}
- Win rate: {stats.get('win_rate', 0):.1f}%
- Rata-rata P&L: {stats.get('avg_pnl_pct', 0):+.1f}%
- Total wins: {stats.get('wins', 0)}
- Total losses: {stats.get('losses', 0)}

RIWAYAT TRADING (30 terbaru):
{chr(10).join(plan_lines) if plan_lines else 'Belum ada closed trades.'}

Berikan respons dalam format JSON berikut (tanpa markdown):
{{
  "summary": "ringkasan 2-3 kalimat",
  "strengths": ["kekuatan 1", "kekuatan 2"],
  "weaknesses": ["kelemahan 1", "kelemahan 2"],
  "suggestions": ["saran konkret 1", "saran konkret 2", "saran konkret 3"],
  "win_rate_analysis": {{
    "grade": "A/B/C/D",
    "win_rate": {stats.get('win_rate', 0)},
    "avg_pnl": {stats.get('avg_pnl_pct', 0)},
    "total_trades": {stats.get('closed', 0)},
    "comment": "komentar singkat tentang win rate"
  }}
}}"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Strip possible markdown code fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        import json
        result = json.loads(text.strip())
        result["source"] = "gemini"
        return result
    except Exception as exc:
        logger.warning("Gemini parsing failed, falling back: %s", exc)
        return _rule_based_feedback(stats, plans)
