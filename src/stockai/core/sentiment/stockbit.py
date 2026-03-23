"""Stockbit sentiment scraper with Google News fallback."""

from __future__ import annotations

import logging
from typing import Any

import requests

from stockai.data.cache import get_cache, memory_cache_get, memory_cache_set

logger = logging.getLogger(__name__)


class StockbitSentiment:
    """Analyze community sentiment from Stockbit posts."""

    API_URL = "https://api.stockbit.com/v2.4/stream/{symbol}?limit=20&offset=0"
    CACHE_TTL_SECONDS = 1800
    REQUEST_TIMEOUT_SECONDS = 8

    BULLISH_KEYWORDS = [
        "beli", "buy", "accumulate", "akumulasi", "naik", "up", "bullish",
        "breakout", "target", "mantap", "cuan", "gas", "recommend", "masuk",
        "support kuat", "golden cross", "uptrend",
    ]
    BEARISH_KEYWORDS = [
        "jual", "sell", "turun", "down", "bearish", "breakdown", "stop loss",
        "cut loss", "hindari", "jelek", "downtrend", "resistan kuat", "death cross",
    ]

    def __init__(self) -> None:
        self.cache = get_cache()
        self.session = requests.Session()
        self._signal_cache: dict[str, dict[str, Any]] = {}

    def analyze(self, symbol: str) -> dict[str, Any]:
        clean_symbol = symbol.upper().replace(".JK", "").strip()
        if clean_symbol in self._signal_cache:
            return self._signal_cache[clean_symbol]

        cache_key = f"stockbit_sentiment:{clean_symbol}"
        memory_cached = memory_cache_get(cache_key)
        if isinstance(memory_cached, dict):
            self._signal_cache[clean_symbol] = memory_cached
            return memory_cached

        persistent_cached = self.cache.get(cache_key)
        if isinstance(persistent_cached, dict):
            memory_cache_set(cache_key, persistent_cached, ttl=self.CACHE_TTL_SECONDS)
            self._signal_cache[clean_symbol] = persistent_cached
            return persistent_cached

        posts = self._fetch_stockbit_posts(clean_symbol)
        if posts:
            result = self._analyze_texts(clean_symbol, posts, source="stockbit")
        else:
            result = self._fallback_google_news(clean_symbol)

        self.cache.set(cache_key, result, ttl=self.CACHE_TTL_SECONDS)
        memory_cache_set(cache_key, result, ttl=self.CACHE_TTL_SECONDS)
        self._signal_cache[clean_symbol] = result
        return result

    def _fetch_stockbit_posts(self, symbol: str) -> list[str]:
        url = self.API_URL.format(symbol=symbol)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36"
            ),
            "Accept": "application/json",
            "Referer": f"https://stockbit.com/symbol/{symbol}",
        }

        try:
            response = self.session.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.debug("Stockbit sentiment fetch failed for %s: %s", symbol, exc)
            return []

        rows = self._extract_rows(payload)
        texts = [self._extract_text(row) for row in rows]
        return [text for text in texts if text][:20]

    def _extract_rows(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if not isinstance(payload, dict):
            return []

        for key in ("data", "items", "posts", "stream", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
            if isinstance(value, dict):
                nested_list = value.get("items") or value.get("data") or value.get("posts")
                if isinstance(nested_list, list):
                    return [row for row in nested_list if isinstance(row, dict)]
        return []

    def _extract_text(self, row: dict[str, Any]) -> str:
        for key in ("content", "body", "message", "text", "description", "title"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _analyze_texts(self, symbol: str, texts: list[str], source: str) -> dict[str, Any]:
        total_score = 0
        bullish_count = 0
        bearish_count = 0

        for text in texts:
            normalized = text.lower()
            bullish_hits = sum(1 for word in self.BULLISH_KEYWORDS if word in normalized)
            bearish_hits = sum(1 for word in self.BEARISH_KEYWORDS if word in normalized)
            post_score = bullish_hits - bearish_hits
            total_score += post_score

            if post_score > 0:
                bullish_count += 1
            elif post_score < 0:
                bearish_count += 1

        sentiment = self._classify(total_score)

        return {
            "symbol": symbol,
            "sentiment": sentiment,
            "score": int(total_score),
            "post_count": len(texts),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "source": source,
        }

    def _classify(self, score: int) -> str:
        if score >= 5:
            return "BULLISH"
        if score <= -5:
            return "BEARISH"
        return "NEUTRAL"

    def _fallback_google_news(self, symbol: str) -> dict[str, Any]:
        try:
            from stockai.core.sentiment.news import NewsAggregator

            aggregator = NewsAggregator()
            articles = aggregator.fetch_google_news(symbol, max_articles=20)
            texts = [article.title for article in articles if article.title]
            if texts:
                return self._analyze_texts(symbol, texts, source="google_news")
        except Exception as exc:
            logger.debug("Google News fallback failed for %s: %s", symbol, exc)

        return {
            "symbol": symbol,
            "sentiment": "NEUTRAL",
            "score": 0,
            "post_count": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "source": "google_news",
        }
