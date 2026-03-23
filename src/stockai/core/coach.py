"""AI Entry Coach - teknikal + LLM untuk keputusan entry."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TechnicalSnapshot:
    symbol: str
    price: float
    change_pct: float
    ema8: float = 0.0
    ema21: float = 0.0
    ma50: float = 0.0
    ma200: float = 0.0
    trend: str = "NEUTRAL"
    rsi: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    volume: int = 0
    vol_ma20: float = 0.0
    vol_ratio: float = 1.0
    support: float = 0.0
    resistance: float = 0.0
    dist_support_pct: float = 0.0
    dist_resistance_pct: float = 0.0
    gates_pass: list[str] = field(default_factory=list)
    gates_fail: list[str] = field(default_factory=list)
    gate_score: int = 0
    ihsg_trend: str = "UNKNOWN"
    timestamp: str = ""


@dataclass
class CoachDecision:
    symbol: str
    action: str
    confidence: int
    entry_low: float = 0.0
    entry_high: float = 0.0
    stop_loss: float = 0.0
    target1: float = 0.0
    target2: float = 0.0
    risk_reward: float = 0.0
    suggested_lot: int = 0
    suggested_amount: float = 0.0
    summary: str = ""
    reason_entry: list[str] = field(default_factory=list)
    reason_wait: list[str] = field(default_factory=list)
    warning: list[str] = field(default_factory=list)
    what_to_wait: str = ""
    snapshot: TechnicalSnapshot | None = None
    modal: int = 5_000_000
    tujuan: str = "swing"
    timestamp: str = ""


def _compute_snapshot(symbol: str, df: pd.DataFrame) -> TechnicalSnapshot:
    """Compute technical indicators from OHLCV dataframe."""
    data = df.copy()
    data.columns = [c.lower() for c in data.columns]
    if "date" in data.columns:
        data = data.set_index("date")
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()

    close = data["close"]
    volume = data["volume"]

    price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2]) if len(close) > 1 else price
    change_pct = (price / prev_price - 1) * 100 if prev_price > 0 else 0.0

    ema8 = float(close.ewm(span=8, adjust=False).mean().iloc[-1])
    ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else price
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else price

    trend = (
        "UPTREND" if ema8 > ema21 and price > ma50 else
        "DOWNTREND" if ema8 < ema21 and price < ma50 else
        "NEUTRAL"
    )

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = 100 - 100 / (1 + rs)
    rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else 50.0

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_sig = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_sig

    vol_ma20 = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else float(volume.mean() or 0.0)
    vol_curr = int(volume.iloc[-1])
    vol_ratio = vol_curr / vol_ma20 if vol_ma20 > 0 else 1.0

    recent = data.tail(20)
    support = float(recent["low"].min())
    resistance = float(recent["high"].max())
    dist_support = (price / support - 1) * 100 if support > 0 else 0.0
    dist_resistance = (resistance / price - 1) * 100 if price > 0 else 0.0

    g1 = ema8 > ema21
    g2 = price > ma50
    g3 = float(macd_line.iloc[-1]) > float(macd_sig.iloc[-1])
    g4 = 40 <= rsi <= 65
    g5 = vol_ratio >= 1.2

    gates_pass: list[str] = []
    gates_fail: list[str] = []
    gate_map = {
        "Trend EMA8>EMA21": g1,
        "Harga di atas MA50": g2,
        "MACD bullish": g3,
        "RSI 40-65 (ideal)": g4,
        "Volume spike >1.2x": g5,
    }
    for name, passed in gate_map.items():
        (gates_pass if passed else gates_fail).append(name)

    return TechnicalSnapshot(
        symbol=symbol,
        price=round(price, 0),
        change_pct=round(change_pct, 2),
        ema8=round(ema8, 0),
        ema21=round(ema21, 0),
        ma50=round(ma50, 0),
        ma200=round(ma200, 0),
        trend=trend,
        rsi=round(rsi, 1),
        macd=round(float(macd_line.iloc[-1]), 2),
        macd_signal=round(float(macd_sig.iloc[-1]), 2),
        macd_hist=round(float(macd_hist.iloc[-1]), 2),
        volume=vol_curr,
        vol_ma20=round(vol_ma20, 0),
        vol_ratio=round(vol_ratio, 2),
        support=round(support, 0),
        resistance=round(resistance, 0),
        dist_support_pct=round(dist_support, 1),
        dist_resistance_pct=round(dist_resistance, 1),
        gates_pass=gates_pass,
        gates_fail=gates_fail,
        gate_score=len(gates_pass),
        timestamp=datetime.now().isoformat(),
    )


def _build_prompt(snap: TechnicalSnapshot, modal: int, tujuan: str) -> str:
    modal_fmt = f"Rp {modal:,.0f}".replace(",", ".")
    tujuan_map = {
        "scalp": "scalping (1-2 minggu)",
        "swing": "swing trading (1-2 bulan)",
        "invest": "investasi jangka menengah (6+ bulan)",
    }
    tujuan_str = tujuan_map.get(tujuan, tujuan)
    gates_pass_str = "\n".join(f"  ✅ {g}" for g in snap.gates_pass) or "  (tidak ada)"
    gates_fail_str = "\n".join(f"  ❌ {g}" for g in snap.gates_fail) or "  (tidak ada)"

    return f"""Kamu adalah AI Coach trading saham Indonesia yang berbicara dalam Bahasa Indonesia yang santai tapi profesional. Tugasmu adalah menganalisis data teknikal saham dan memberikan keputusan entry yang jelas untuk investor awam.

## Data Teknikal {snap.symbol} (IDX)
- Harga saat ini: Rp {snap.price:,.0f}
- Perubahan hari ini: {snap.change_pct:+.2f}%
- Trend: {snap.trend}

### Indikator Trend
- EMA8: Rp {snap.ema8:,.0f} | EMA21: Rp {snap.ema21:,.0f}
- MA50: Rp {snap.ma50:,.0f} | MA200: Rp {snap.ma200:,.0f}

### Momentum
- RSI: {snap.rsi} {"(overbought ⚠️)" if snap.rsi > 70 else "(oversold)" if snap.rsi < 30 else "(normal ✅)"}
- MACD: {snap.macd:+.2f} | Signal: {snap.macd_signal:+.2f} | Histogram: {snap.macd_hist:+.2f} {"(bullish ✅)" if snap.macd_hist > 0 else "(bearish ❌)"}

### Volume
- Volume hari ini: {snap.volume:,} lot
- Rata-rata 20 hari: {snap.vol_ma20:,.0f} lot
- Rasio volume: {snap.vol_ratio:.2f}x {"(ada akumulasi ✅)" if snap.vol_ratio >= 1.2 else "(sepi ⚠️)"}

### Support & Resistance (20 hari)
- Support: Rp {snap.support:,.0f} (jarak: {snap.dist_support_pct:.1f}% dari harga)
- Resistance: Rp {snap.resistance:,.0f} (jarak: {snap.dist_resistance_pct:.1f}% dari harga)

### Gate System ({snap.gate_score}/5 gates terbuka)
Gate PASS:
{gates_pass_str}

Gate FAIL:
{gates_fail_str}

## Profil Investor
- Modal: {modal_fmt}
- Tujuan: {tujuan_str}

## Instruksi Output
Berikan analisis dalam format JSON yang KETAT berikut (tidak ada teks di luar JSON):

{{
  "action": "ENTRY_NOW" | "WAIT" | "AVOID",
  "confidence": <angka 0-100>,
  "summary": "<1-2 kalimat ringkasan keputusan dalam bahasa santai>",
  "entry_low": <harga entry bawah (float)>,
  "entry_high": <harga entry atas (float)>,
  "stop_loss": <harga stop loss (float)>,
  "target1": <target profit 1 (float)>,
  "target2": <target profit 2 lebih tinggi (float)>,
  "suggested_lot": <jumlah lot yang disarankan berdasarkan modal (int)>,
  "reason_entry": ["<alasan 1>", "<alasan 2>", ...],
  "reason_wait": ["<alasan kenapa belum masuk jika WAIT/AVOID>", ...],
  "warning": ["<risiko yang perlu diperhatikan>", ...],
  "what_to_wait": "<kalau WAIT: kondisi spesifik yang harus terjadi sebelum masuk. Kalau ENTRY_NOW: kosong>"
}}

Aturan:
- action ENTRY_NOW: gate_score >= 3 dan trend UPTREND dan RSI < 70
- action AVOID: trend DOWNTREND dan gate_score <= 1, atau RSI > 75
- action WAIT: kondisi lainnya
- entry_low/high: range harga masuk yang realistis (±1-2% dari harga sekarang)
- stop_loss: support terdekat atau -7% dari entry (pilih yang lebih dekat)
- target1: resistance terdekat atau +10%
- target2: +20% dari entry
- suggested_lot: hitung berdasarkan modal / (entry_high * 100), bulatkan ke bawah ke kelipatan 1 lot
- Semua narasi dalam Bahasa Indonesia yang mudah dimengerti awam
- Jangan gunakan jargon teknikal yang tidak dijelaskan
"""


async def _call_gemini(prompt: str) -> dict[str, Any]:
    """Call Gemini 2.0 Flash and parse JSON response."""
    import json
    import re

    from stockai.config import get_settings

    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY tidak ditemukan di .env/.env.local")

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={
                "temperature": 0.3,
                "top_p": 0.8,
                "response_mime_type": "application/json",
            },
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
        raw = (response.text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as exc:
        logger.error("Gemini call failed: %s", exc)
        raise


def _rule_based_fallback(snap: TechnicalSnapshot, modal: int) -> dict[str, Any]:
    """Fallback if LLM fails."""
    if snap.gate_score >= 3 and snap.trend == "UPTREND" and snap.rsi < 70:
        action = "ENTRY_NOW"
        confidence = snap.gate_score * 15 + 25
    elif snap.trend == "DOWNTREND" and snap.gate_score <= 1:
        action = "AVOID"
        confidence = 70
    else:
        action = "WAIT"
        confidence = 40

    entry_low = snap.price * 0.99
    entry_high = snap.price * 1.01
    stop_loss = max(snap.support, snap.price * 0.93)
    target1 = min(snap.resistance, snap.price * 1.10)
    target2 = snap.price * 1.20
    lot = int(modal / (entry_high * 100))

    return {
        "action": action,
        "confidence": confidence,
        "summary": f"{snap.symbol} {'siap entry' if action == 'ENTRY_NOW' else 'belum ideal' if action == 'WAIT' else 'hindari dulu'}.",
        "entry_low": round(entry_low, 0),
        "entry_high": round(entry_high, 0),
        "stop_loss": round(stop_loss, 0),
        "target1": round(target1, 0),
        "target2": round(target2, 0),
        "suggested_lot": lot,
        "reason_entry": snap.gates_pass,
        "reason_wait": snap.gates_fail,
        "warning": [],
        "what_to_wait": "",
    }


async def analyze_entry(
    symbol: str,
    df: pd.DataFrame,
    modal: int = 5_000_000,
    tujuan: str = "swing",
    ihsg_trend: str = "UNKNOWN",
) -> CoachDecision:
    """Analyze symbol and produce coach decision."""
    snap = _compute_snapshot(symbol, df)
    snap.ihsg_trend = ihsg_trend
    prompt = _build_prompt(snap, modal, tujuan)

    try:
        llm_result = await _call_gemini(prompt)
    except Exception as exc:
        logger.warning("LLM failed, using fallback rules: %s", exc)
        llm_result = _rule_based_fallback(snap, modal)

    decision = CoachDecision(
        symbol=symbol,
        action=str(llm_result.get("action", "WAIT")),
        confidence=int(llm_result.get("confidence", 50)),
        entry_low=float(llm_result.get("entry_low", snap.price * 0.99)),
        entry_high=float(llm_result.get("entry_high", snap.price * 1.01)),
        stop_loss=float(llm_result.get("stop_loss", snap.price * 0.93)),
        target1=float(llm_result.get("target1", snap.price * 1.10)),
        target2=float(llm_result.get("target2", snap.price * 1.20)),
        suggested_lot=int(llm_result.get("suggested_lot", 0)),
        suggested_amount=int(llm_result.get("suggested_lot", 0)) * float(llm_result.get("entry_high", snap.price)) * 100,
        summary=str(llm_result.get("summary", "")),
        reason_entry=list(llm_result.get("reason_entry", [])),
        reason_wait=list(llm_result.get("reason_wait", [])),
        warning=list(llm_result.get("warning", [])),
        what_to_wait=str(llm_result.get("what_to_wait", "")),
        snapshot=snap,
        modal=modal,
        tujuan=tujuan,
        timestamp=datetime.now().isoformat(),
    )

    entry_mid = (decision.entry_low + decision.entry_high) / 2
    risk = entry_mid - decision.stop_loss
    reward = decision.target1 - entry_mid
    decision.risk_reward = round(reward / risk, 2) if risk > 0 else 0.0
    return decision
