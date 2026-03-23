"""Probability forecast engine based on historical backtesting."""

from __future__ import annotations

from typing import Any

from stockai.data.cache import get_cache, memory_cache_get, memory_cache_set
from stockai.core.ml.backtester import HistoricalBacktester
from stockai.core.ml.pattern_recognition import PatternRecognizer


class ProbabilityEngine:
    """Combine historical win rates + live signals into probability forecast."""

    CACHE_TTL_SECONDS = 3600

    def __init__(self):
        self.backtester = HistoricalBacktester()
        self.pattern_recognizer = PatternRecognizer()
        self.cache = get_cache()

    def forecast(self, symbol: str, current_analysis: dict[str, Any]) -> dict[str, Any]:
        clean_symbol = symbol.upper().replace(".JK", "").strip()
        signal_signature = self._signature(current_analysis)
        cache_key = f"ml_forecast:{clean_symbol}:{signal_signature}"

        memory_cached = memory_cache_get(cache_key)
        if isinstance(memory_cached, dict):
            return memory_cached

        persistent_cached = self.cache.get(cache_key)
        if isinstance(persistent_cached, dict):
            memory_cache_set(cache_key, persistent_cached, ttl=self.CACHE_TTL_SECONDS)
            return persistent_cached

        win_rate = self.backtester.calculate_win_rate(clean_symbol, current_analysis)
        market = self.backtester.get_market_context()

        base_5 = float(win_rate.get("win_rate_5pct", 0.0))
        base_10 = float(win_rate.get("win_rate_10pct", 0.0))
        expected_return = float(win_rate.get("avg_return_14d", 0.0))
        confidence = win_rate.get("confidence", "LOW")
        similar_cases = int(win_rate.get("similar_cases", 0))

        regime = market.get("market_regime", "NEUTRAL")
        regime_multiplier = 1.0
        regime_note = "NEUTRAL"
        if regime == "RISK_OFF":
            regime_multiplier = 0.75
            regime_note = "RISK_OFF (adjusted)"
        elif regime == "RISK_ON":
            regime_multiplier = 1.10
            regime_note = "RISK_ON (adjusted)"

        adjusted_5 = base_5 * regime_multiplier
        adjusted_10 = base_10 * regime_multiplier
        adjusted_return = expected_return * regime_multiplier

        signal_boost = 0.0
        if str(current_analysis.get("sentiment_label", "")).upper() == "BULLISH":
            signal_boost += 0.05
        if str(current_analysis.get("volume_classification", "")).upper() in {"HIGH", "EXTREME"}:
            signal_boost += 0.05
        if str(current_analysis.get("smart_money_signal", "")).upper() == "ACCUMULATION":
            signal_boost += 0.08

        pattern_data = self.pattern_recognizer.detect(clean_symbol)
        patterns = pattern_data.get("patterns_detected", [])
        bullish_patterns = [p for p in patterns if p.get("type") == "BULLISH"]
        bearish_patterns = [p for p in patterns if p.get("type") == "BEARISH"]

        bullish_boost = 0.0
        if any((p.get("strength") == "HIGH" and float(p.get("confidence", 0)) >= 0.75) for p in bullish_patterns):
            bullish_boost = 0.10
        elif any(p.get("strength") == "MEDIUM" for p in bullish_patterns):
            bullish_boost = 0.05
        if len(bullish_patterns) >= 2:
            bullish_boost = max(bullish_boost, 0.15)

        bearish_penalty = -0.10 if bearish_patterns else 0.0
        pattern_boost = bullish_boost + bearish_penalty

        probability_5 = max(0.0, min(1.0, adjusted_5 + signal_boost + pattern_boost))
        probability_10 = max(0.0, min(1.0, adjusted_10 + signal_boost * 0.7 + pattern_boost * 0.7))

        if probability_5 >= 0.60:
            verdict = "FAVORABLE"
        elif probability_5 >= 0.40:
            verdict = "NEUTRAL"
        else:
            verdict = "UNFAVORABLE"

        result = {
            "symbol": clean_symbol,
            "probability_5pct": round(probability_5, 4),
            "probability_10pct": round(probability_10, 4),
            "expected_return": round(adjusted_return, 4),
            "market_context": regime_note,
            "signal_boost": f"+{int(round(signal_boost * 100))}% dari combo sinyal",
            "pattern_boost": f"{int(round(pattern_boost * 100)):+d}% dari pattern",
            "confidence": confidence,
            "verdict": verdict,
            "similar_cases": similar_cases,
            "patterns_detected": patterns,
            "dominant_pattern": pattern_data.get("dominant_pattern"),
            "overall_pattern_bias": pattern_data.get("overall_bias", "NEUTRAL"),
            "pattern_count": int(pattern_data.get("pattern_count", 0) or 0),
        }

        self.cache.set(cache_key, result, ttl=self.CACHE_TTL_SECONDS)
        memory_cache_set(cache_key, result, ttl=self.CACHE_TTL_SECONDS)
        return result

    def format_forecast(self, forecast: dict[str, Any]) -> str:
        probability_5 = float(forecast.get("probability_5pct", 0.0))
        expected_return = float(forecast.get("expected_return", 0.0))
        similar_cases = int(forecast.get("similar_cases", 0))
        confidence = forecast.get("confidence", "LOW")
        market_context = forecast.get("market_context", "NEUTRAL")
        verdict = forecast.get("verdict", "NEUTRAL")

        return (
            f"🎯 Probabilitas naik 5%: {probability_5:.0%} "
            f"({similar_cases} kasus serupa, {confidence} confidence)\n"
            f"📈 Expected return 14 hari: {expected_return:+.1%}\n"
            f"⚠️  Market: {market_context}\n"
            f"💡 Verdict: {verdict}"
        )

    def _signature(self, analysis: dict[str, Any]) -> str:
        keys = [
            str(analysis.get("volume_ratio", "")),
            str(analysis.get("adx", "")),
            str(analysis.get("near_support", "")),
            str(analysis.get("sentiment_label", "")),
            str(analysis.get("volume_classification", "")),
            str(analysis.get("smart_money_signal", "")),
            str(analysis.get("pattern_hint", "")),
        ]
        return "|".join(keys)
