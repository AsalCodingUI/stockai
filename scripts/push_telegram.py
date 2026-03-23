#!/usr/bin/env python3
"""Push morning scan results to Telegram."""

import os
import sys
import requests
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    # Coba load .env.local dulu, atau fallback ke .env
    load_dotenv(".env.local")
    load_dotenv(".env")
except ImportError:
    pass

from src.stockai.data.sources.yahoo import YahooFinanceSource
from src.stockai.core.foreign_flow import ForeignFlowMonitor
from src.stockai.core.volume_detector import UnusualVolumeDetector
from src.stockai.core.sentiment.stockbit import StockbitSentiment
from src.stockai.core.ml.probability import ProbabilityEngine
from src.stockai.scoring.analyzer import analyze_stock

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

WATCHLIST = [
    "BBCA", "BBRI", "BMRI", "BBNI", "BRIS",
    "ADRO", "PTBA", "ANTM", "INCO",
    "TLKM", "ASII", "ICBP", "KLBF", "UNVR",
]


def format_compact_rupiah(value: float) -> str:
    abs_value = abs(value)
    if abs_value >= 1_000_000_000_000:
        return f"Rp {value / 1_000_000_000_000:.1f}T"
    if abs_value >= 1_000_000_000:
        return f"Rp {value / 1_000_000_000:.1f}B"
    if abs_value >= 1_000_000:
        return f"Rp {value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"Rp {value / 1_000:.1f}K"
    return f"Rp {value:,.0f}"

def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not configured in environment.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    requests.post(url, json=payload)

def format_trade_signal(symbol: str, result, forecast: dict | None = None) -> str:
    price = result.current_price
    sr = result.support_resistance
    support = sr.nearest_support if sr.nearest_support else 0
    resistance = sr.nearest_resistance if sr.nearest_resistance else (price * 1.05)
    score = result.composite_score
    gates = result.gates.gates_passed

    sl = price * 0.95              # SL -5%
    tp1 = resistance               # TP1 = resistance terdekat
    tp2 = resistance * 1.05        # TP2 = 5% di atas resistance
    rr = (tp1 - price) / (price - sl) if price > sl else 0
    foreign_line = ""
    volume_line = ""
    sentiment_line = ""
    combo_line = ""
    probability_line = ""
    pattern_line = ""
    if getattr(result, "foreign_flow_source", "") == "volume_proxy":
        if result.foreign_flow_signal != "NEUTRAL":
            foreign_line = (
                f"🔍 Smart Money: {result.foreign_flow_signal} {result.foreign_flow_strength} "
                f"({result.foreign_consecutive_buy_days} hari berturut) [proxy]\n"
            )
    elif result.foreign_flow_signal == "ACCUMULATION":
        foreign_line = (
            f"🌏 Asing: Beli neto {format_compact_rupiah(result.foreign_latest_net)} "
            f"({result.foreign_consecutive_buy_days} hari berturut)\n"
        )
    elif result.foreign_flow_signal == "DISTRIBUTION":
        foreign_line = (
            f"🌏 Asing: Jual neto {format_compact_rupiah(abs(result.foreign_latest_net))} "
            f"(5 hari: {format_compact_rupiah(result.foreign_total_net_5d)})\n"
        )
    elif result.foreign_latest_net != 0:
        foreign_line = f"🌏 Asing: Neto {format_compact_rupiah(result.foreign_latest_net)}\n"

    if (
        getattr(result, "volume_classification", "NORMAL") != "NORMAL"
        and float(getattr(result, "volume_ratio", 0.0)) >= 2.0
    ):
        volume_line = (
            f"📊 Volume: {result.volume_classification} {result.volume_ratio:.1f}x "
            f"rata-rata ({result.volume_price_action.title()})\n"
        )

    if (
        getattr(result, "sentiment_label", "NEUTRAL") != "NEUTRAL"
        or getattr(result, "volume_classification", "NORMAL") in {"MODERATE", "HIGH", "EXTREME"}
    ):
        sentiment_score = int(getattr(result, "sentiment_score_raw", 0) or 0)
        sign = "+" if sentiment_score > 0 else ""
        sentiment_line = (
            f"💬 Komunitas: {result.sentiment_label} ({sign}{sentiment_score}) "
            f"— {result.sentiment_bullish_count} bullish vs {result.sentiment_bearish_count} bearish\n"
        )

    smart_money_ok = result.foreign_flow_signal == "ACCUMULATION"
    volume_ok = getattr(result, "volume_classification", "NORMAL") in {"HIGH", "EXTREME"}
    sentiment_ok = getattr(result, "sentiment_label", "NEUTRAL") == "BULLISH"
    active_signals = sum([smart_money_ok, volume_ok, sentiment_ok])
    if active_signals == 3:
        combo_line = "🚨 MEGA COMBO: Smart Money + Volume + Sentiment!\n"
    elif active_signals == 2:
        combo_line = "⚡ COMBO SIGNAL: 2/3 sinyal!\n"

    if forecast and forecast.get("confidence") != "LOW":
        probability_line = (
            f"🎯 Probabilitas +5%: {forecast.get('probability_5pct', 0):.0%} "
            f"({forecast.get('confidence')} confidence)\n"
            f"📈 Expected return: {forecast.get('expected_return', 0):+.1%} dalam 14 hari\n"
        )
        patterns = forecast.get("patterns_detected", []) or []
        if patterns:
            top = sorted(patterns, key=lambda x: float(x.get("confidence", 0)), reverse=True)[0]
            pattern_name = str(top.get("name", "")).replace("HEAD_AND_SHOULDERS", "HEAD & SHOULDERS").replace("_", " ")
            strength = top.get("strength", "MEDIUM")
            target = top.get("target_price")
            wr = float(top.get("historical_win_rate", 0.0))
            if isinstance(target, (int, float)):
                pattern_line = (
                    f"🔮 Pattern: {pattern_name} ({strength} confidence)\n"
                    f"   Target: Rp {target:,.0f} | Historical WR: {wr:.0%}\n"
                )
            else:
                pattern_line = f"🔮 Pattern: {pattern_name} ({strength} confidence)\n"

    return (
        f"🎯 <b>{symbol}</b> | Score: {score:.0f} | Gates: {gates}/6\n"
        f"💰 Entry: Rp {price:,.0f}\n"
        f"🛑 SL:    Rp {sl:,.0f} (-5%)\n"
        f"✅ TP1:   Rp {tp1:,.0f} (+{((tp1/price)-1)*100:.1f}%)\n"
        f"🚀 TP2:   Rp {tp2:,.0f} (+{((tp2/price)-1)*100:.1f}%)\n"
        f"⚖️  R/R:   1:{rr:.1f}\n"
        f"{foreign_line}"
        f"{volume_line}"
        f"{sentiment_line}"
        f"{probability_line}"
        f"{pattern_line}"
        f"{combo_line}"
    )

def main():
    yahoo = YahooFinanceSource()
    foreign_flow = ForeignFlowMonitor()
    volume_detector = UnusualVolumeDetector()
    sentiment_monitor = StockbitSentiment()
    probability_engine = ProbabilityEngine()
    candidates = []

    print("🔍 Scanning watchlist...")
    for symbol in WATCHLIST:
        try:
            history = yahoo.get_price_history(symbol, period="3mo")
            if history is None or history.empty:
                print(f"  ⚠️ {symbol}: No price data")
                continue

            info = yahoo.get_stock_info(symbol)
            fundamentals = {}
            if info:
                fundamentals = {
                    "pe_ratio": info.get("pe_ratio"),
                    "pb_ratio": info.get("pb_ratio"),
                    "roe": info.get("roe"),
                    "debt_to_equity": info.get("debt_to_equity"),
                    "profit_margin": info.get("profit_margin"),
                    "current_ratio": info.get("current_ratio"),
                    "sector": info.get("sector"),
                }

            result = analyze_stock(
                ticker=symbol,
                df=history,
                fundamentals=fundamentals,
                foreign_flow_signal=foreign_flow.get_flow_signal(symbol, days=5),
                unusual_volume_signal=volume_detector.detect(symbol, history=history),
                sentiment_signal=sentiment_monitor.analyze(symbol),
            )
            
            gates = result.gates.gates_passed
            confidence = result.confidence
            
            if confidence in ("HIGH", "WATCH") or gates >= 4:
                # Calculate R/R
                price = result.current_price
                sr = result.support_resistance
                sl = price * 0.95
                resistance = sr.nearest_resistance if sr.nearest_resistance else (price * 1.05)
                tp1 = max(resistance, price * 1.01)
                rr = (tp1 - price) / (price - sl) if price > sl else 0

                if rr >= 1.5:
                    forecast = probability_engine.forecast(
                        symbol,
                        {
                            "volume_ratio": result.volume_ratio,
                            "adx": result.adx.get("adx", 20) if result.adx else 20,
                            "near_support": (
                                result.support_resistance.distance_to_support_pct <= 10
                                if result.support_resistance
                                else False
                            ),
                            "sentiment_label": result.sentiment_label,
                            "volume_classification": result.volume_classification,
                            "smart_money_signal": result.foreign_flow_signal,
                        },
                    )
                    candidates.append((symbol, result, gates, forecast))
                    print(f"  ✅ {symbol}: {gates}/6 gates (R/R 1:{rr:.1f})")
                else:
                    print(f"  ⚠️ {symbol}: {gates}/6 gates (Skipped R/R {rr:.1f} < 1.5)")
            else:
                print(f"  ❌ {symbol}: {gates}/6 gates")
        except Exception as e:
            print(f"  ⚠️ {symbol}: Error - {e}")

    ready_to_buy = []
    watchlist = []

    for symbol, result, gates, forecast in candidates:
        if gates == 6:
            ready_to_buy.append((symbol, result, gates, forecast))
        elif gates >= 4:
            watchlist.append((symbol, result, gates, forecast))

    ready_to_buy.sort(key=lambda x: x[1].composite_score, reverse=True)
    watchlist.sort(key=lambda x: x[1].composite_score, reverse=True)

    if not ready_to_buy and not watchlist:
        msg = "📊 <b>Morning Scan</b>\n\nTidak ada sinyal BUY hari ini. Market mungkin sideways/bearish."
    else:
        msg = "📊 <b>Morning Scan Results</b>\n\n"
        
        if ready_to_buy:
            msg += f"✅ <b>READY TO BUY ({len(ready_to_buy)} Stocks)</b>\n"
            for symbol, result, gates, forecast in ready_to_buy[:3]:  # Top 3
                msg += format_trade_signal(symbol, result, forecast)
            msg += "\n"

        if watchlist:
            msg += f"👀 <b>WATCHLIST ({len(watchlist)} Stocks)</b>\n"
            for symbol, result, gates, forecast in watchlist[:3]:  # Top 3
                msg += format_trade_signal(symbol, result, forecast)

    send_telegram(msg)
    print("\n✅ Pushed to Telegram!")

if __name__ == "__main__":
    main()
