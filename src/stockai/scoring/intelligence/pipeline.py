"""Orchestrates the signal intelligence pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os

from stockai.data.sources.yahoo import YahooFinanceSource
from stockai.scoring.analyzer import AnalysisResult
from stockai.scoring.intelligence.breakout import evaluate_breakout_quality
from stockai.scoring.intelligence.candles import detect_bullish_pattern
from stockai.scoring.intelligence.mtf import evaluate_mtf_confirmation
from stockai.scoring.intelligence.regime import get_market_regime
from stockai.scoring.intelligence.relative_strength import calculate_relative_strength

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceResult:
    """Confidence model for executing a signal."""

    symbol: str
    confidence_score: float
    confidence_level: str
    regime: str
    mtf_aligned: int
    breakout_score: float
    candle_pattern: str
    relative_strength: float
    news_status: str
    news_risk_reason: str
    score_breakdown: dict[str, float] = field(default_factory=dict)
    recommendation: str = "SKIP"


def run_intelligence_pipeline(
    symbol: str,
    analysis_result: AnalysisResult,
    existing_score: float,
    yahoo: YahooFinanceSource | None = None,
) -> IntelligenceResult:
    """Run the intelligence pipeline for a candidate BUY signal."""
    yahoo = yahoo or YahooFinanceSource()

    stock_history = yahoo.get_price_history(symbol, period="6mo")
    regime_result = get_market_regime(yahoo)
    index_history = yahoo.get_price_history("^JKSE", period="3mo")

    if regime_result.regime == "BEARISH":
        return IntelligenceResult(
            symbol=symbol,
            confidence_score=0.0,
            confidence_level="LOW",
            regime=regime_result.regime,
            mtf_aligned=0,
            breakout_score=0.0,
            candle_pattern="None",
            relative_strength=0.0,
            news_status="SKIPPED",
            news_risk_reason="Market regime bearish",
            score_breakdown={"regime_gate": 0.0},
            recommendation="SKIP",
        )

    mtf_result = evaluate_mtf_confirmation(symbol, yahoo=yahoo)
    breakout_result = evaluate_breakout_quality(stock_history)
    candle_result = detect_bullish_pattern(stock_history)
    rs_result = calculate_relative_strength(stock_history, index_history)
    news_status, news_reason, news_score = _scan_news_risk(symbol)

    normalized_existing = max(0.0, min(15.0, (existing_score / 100.0) * 15.0))
    breakdown = {
        "mtf": mtf_result.score,
        "breakout": breakout_result.breakout_score,
        "candles": candle_result.score,
        "relative_strength": rs_result.score,
        "news": news_score,
        "existing_score": normalized_existing,
    }

    if not mtf_result.passed:
        recommendation = "SKIP"
        confidence_score = 0.0
    elif regime_result.regime == "SIDEWAYS" and rs_result.value <= 1.2:
        recommendation = "SKIP"
        confidence_score = 0.0
        news_reason = news_reason or "Sideways market requires RS > 1.2"
    elif news_status == "RISK_DETECTED":
        recommendation = "SKIP"
        confidence_score = 0.0
    else:
        confidence_score = round(sum(breakdown.values()), 1)
        if confidence_score >= 80:
            recommendation = "EXECUTE"
        elif confidence_score >= 60:
            recommendation = "WATCH"
        else:
            recommendation = "SKIP"

    confidence_level = (
        "HIGH" if confidence_score >= 80 else "MEDIUM" if confidence_score >= 60 else "LOW"
    )

    return IntelligenceResult(
        symbol=symbol,
        confidence_score=confidence_score,
        confidence_level=confidence_level,
        regime=regime_result.regime,
        mtf_aligned=mtf_result.aligned_count,
        breakout_score=breakout_result.breakout_score,
        candle_pattern=candle_result.pattern,
        relative_strength=rs_result.value,
        news_status=news_status,
        news_risk_reason=news_reason,
        score_breakdown=breakdown,
        recommendation=recommendation,
    )


def _scan_news_risk(symbol: str) -> tuple[str, str, float]:
    """Use Gemini when configured; otherwise skip without blocking."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "SKIPPED", "Gemini API key not configured", 0.0

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "Kamu adalah analis risiko saham IDX. Cari dan analisa berita terbaru "
            f"saham {symbol} di Indonesia (dalam 7 hari terakhir).\n\n"
            "Apakah ada:\n"
            "- Berita negatif material (skandal, kerugian besar, gagal bayar)\n"
            "- Right issue atau stock split yang menekan harga\n"
            "- Masalah regulasi atau tindakan OJK/BEI\n"
            "- Corporate action negatif lainnya\n\n"
            "Jawab HANYA dengan format:\n"
            "STATUS: CLEAR atau RISK_DETECTED\n"
            'REASON: [satu kalimat, atau "Tidak ada berita negatif material"]'
        )
        response = model.generate_content(prompt)
        text = getattr(response, "text", "") or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        status = "SKIPPED"
        reason = "Gemini response not parseable"
        for line in lines:
            upper = line.upper()
            if upper.startswith("STATUS:"):
                value = line.split(":", 1)[1].strip().upper()
                if value in {"CLEAR", "RISK_DETECTED"}:
                    status = value
            elif upper.startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()

        if status == "CLEAR":
            return status, reason or "Tidak ada berita negatif material", 10.0
        if status == "RISK_DETECTED":
            return status, reason or "Risiko berita terdeteksi", 0.0
        return "SKIPPED", reason, 0.0
    except Exception as exc:
        logger.debug("Gemini news scan skipped for %s: %s", symbol, exc)
        return "SKIPPED", f"News scan skipped: {exc}", 0.0
