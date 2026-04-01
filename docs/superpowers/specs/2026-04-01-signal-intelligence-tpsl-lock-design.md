# Signal Intelligence Pipeline + TP/SL Lock System
**Date:** 2026-04-01
**Status:** Approved
**Scope:** stockai-main — swing trading enhancement for personal use

---

## 1. Problem Statement

Current system has three compounding issues for short swing trading (1–5 days):

1. **False signals** — no market regime or multi-timeframe filter; enters on weak breakouts
2. **Late entries** — signals generated after move already happened, RSI overbought at entry
3. **TP/SL drift** — every run recalculates TP/SL from current price, making locked levels meaningless

Target: higher signal selectivity (fewer but more accurate signals), winrate target 60–70%, with locked risk parameters per trade.

---

## 2. Architecture Overview

Two new layers are added on top of the existing 6-gate scoring system:

```
Existing 6-gate score (≥60 threshold)
        │
        ▼
┌─────────────────────────────────────┐
│  LAYER 1: SIGNAL INTELLIGENCE       │
│  src/stockai/scoring/intelligence/  │
│                                     │
│  1. Market Regime Filter  [GATE]    │
│  2. Multi-Timeframe Check [GATE]    │
│  3. Breakout Quality Score          │
│  4. Candlestick Pattern Engine      │
│  5. Relative Strength vs IHSG       │
│  6. Gemini News Risk Scan           │
│                                     │
│  → Confidence Score 0–100           │
│    HIGH ≥80   → proceed to Layer 2  │
│    MEDIUM 60–79 → watchlist only    │
│    LOW <60    → skip                │
└─────────────────────────────────────┘
        │ HIGH signals only
        ▼
┌─────────────────────────────────────┐
│  LAYER 2: TP/SL LOCK SYSTEM         │
│  src/stockai/autopilot/executor.py  │
│  src/stockai/briefing/daily.py      │
│                                     │
│  - Lock entry, SL, TP1/2/3 at BUY  │
│  - Trailing stop (only moves up)    │
│  - Morning alert on SL/TP events    │
└─────────────────────────────────────┘
```

---

## 3. Layer 1 — Signal Intelligence

### 3.1 New Files

```
src/stockai/scoring/intelligence/
├── __init__.py
├── regime.py          # Market Regime Filter
├── mtf.py             # Multi-Timeframe Confirmation
├── breakout.py        # Breakout Quality Score
├── candles.py         # Candlestick Pattern Engine
├── relative_strength.py  # RS vs IHSG
└── pipeline.py        # Orchestrates all 5 + Gemini call
```

`pipeline.py` exposes a single public function:
```python
def run_intelligence_pipeline(
    symbol: str,
    analysis_result: AnalysisResult,
    existing_score: float,
) -> IntelligenceResult
```

`IntelligenceResult` dataclass:
```python
@dataclass
class IntelligenceResult:
    symbol: str
    confidence_score: float        # 0–100
    confidence_level: str          # HIGH / MEDIUM / LOW
    regime: str                    # BULLISH / SIDEWAYS / BEARISH
    mtf_aligned: int               # 0, 1, 2, or 3 timeframes
    breakout_score: float
    candle_pattern: str            # e.g. "Bullish Engulfing" or "None"
    relative_strength: float
    news_status: str               # CLEAR / RISK_DETECTED / SKIPPED
    news_risk_reason: str
    score_breakdown: dict[str, float]
    recommendation: str            # EXECUTE / WATCH / SKIP
```

### 3.2 Market Regime Filter (`regime.py`)

- Fetch `^JKSE` daily via `YahooFinanceSource.get_price_history('^JKSE', period='3mo')`
- Calculate EMA20 and EMA50 on close prices
- **BULLISH**: price > EMA20 AND EMA20 > EMA50
- **SIDEWAYS**: neither fully bullish nor fully bearish
- **BEARISH**: price < EMA20 AND EMA20 < EMA50
- BEARISH → hard gate, return `IntelligenceResult(confidence_level="LOW", recommendation="SKIP")`
- SIDEWAYS → only signals with RS > 1.2 proceed
- Result cached 4 hours (IHSG regime doesn't change intraday)

### 3.3 Multi-Timeframe Confirmation (`mtf.py`)

Fetch per symbol:
- **Weekly** (`1wk`, period `6mo`): bullish = close > EMA20 weekly
- **Daily** (`1d`, period `3mo`): bullish = close > EMA20 daily AND MACD histogram > 0
- **4H** (resample `1h` data into 4H bars, period `60d`): bullish = RSI between 30–65 AND close above EMA20 4H

Score:
- 3/3 aligned → +25 points, gate passed
- 2/3 aligned → +10 points, gate passed
- 1/3 or 0/3 → gate failed, SKIP signal

### 3.4 Breakout Quality Score (`breakout.py`)

```
volume_ratio = today_volume / avg_volume_20d

≥ 2.0x  → +20 points  (institutional)
1.5–2.0x → +12 points (normal breakout)
1.0–1.5x → +5 points  (weak)
< 1.0x  → +0 points   (no confirmation)

close > nearest_resistance → +5 bonus points (capped at 25 total)
```

Uses existing `support_resistance.py` for resistance levels.

### 3.5 Candlestick Pattern Engine (`candles.py`)

Pure pandas, no external library. Analyzes last 3 daily candles:

| Pattern | Logic | Points |
|---------|-------|--------|
| Bullish Engulfing | current body fully covers previous bearish body | 15 |
| Hammer / Pin Bar | lower wick ≥ 2× body, upper wick < body, small body | 12 |
| Morning Star | bearish → doji/small → bullish gap up | 15 |
| Bullish Harami | small bullish inside previous bearish | 8 |
| Piercing Line | gap down open, close above midpoint of previous candle | 10 |
| None | — | 0 |

Contribution **capped at 15 points** regardless of pattern strength.

### 3.6 Relative Strength vs IHSG (`relative_strength.py`)

```
stock_return_20d = (close_today - close_20d_ago) / close_20d_ago
ihsg_return_20d  = (ihsg_today - ihsg_20d_ago) / ihsg_20d_ago

RS = stock_return_20d / ihsg_return_20d  (handle ihsg=0 edge case)

RS > 1.5  → +10 points
RS 1.0–1.5 → +6 points
RS 0.5–1.0 → +2 points
RS < 0.5  → +0 points
```

IHSG data reused from regime.py cache — no extra API call.

### 3.7 Gemini News Risk Scan (in `pipeline.py`)

Called only for signals that pass regime + MTF gates (avoid wasting API quota on SKIPs).

Single Gemini call using existing `google-generativeai` SDK:

**Prompt template:**
```
Kamu adalah analis risiko saham IDX. Cari dan analisa berita terbaru
saham {symbol} di Indonesia (dalam 7 hari terakhir).

Apakah ada:
- Berita negatif material (skandal, kerugian besar, gagal bayar)
- Right issue atau stock split yang menekan harga
- Masalah regulasi atau tindakan OJK/BEI
- Corporate action negatif lainnya

Jawab HANYA dengan format:
STATUS: CLEAR atau RISK_DETECTED
REASON: [satu kalimat, atau "Tidak ada berita negatif material"]
```

- `CLEAR` → +10 points
- `RISK_DETECTED` → signal langsung SKIP (hard override, regardless of other scores)
- Exception/timeout → +0 points, signal tetap jalan (tidak diblock)

### 3.8 Confidence Score Summary

| Component | Max Points | Gate |
|-----------|-----------|------|
| Market Regime | — | Hard gate (BEARISH = SKIP all) |
| MTF Confirmation | 25 | Min 2/3 timeframes |
| Breakout Quality | 25 | — |
| Candlestick Pattern | 15 | — |
| Relative Strength | 10 | — |
| Gemini News | 10 | RISK_DETECTED = SKIP |
| Existing 6-Gate Score | 15 | (normalized: gate_score/100 × 15) |
| **Total** | **100** | |

**HIGH ≥ 80** → `EXECUTE` (passed to autopilot/quality command)
**MEDIUM 60–79** → `WATCH` (shown in briefing, not executed)
**LOW < 60** → `SKIP` (filtered out silently)

---

## 4. Layer 2 — TP/SL Lock System

### 4.1 PaperPosition Extension

Add fields to `PaperPosition` in `autopilot/executor.py`. JSON-backward-compatible (old positions get defaults on load):

```python
# New fields (all optional with defaults for backward compat)
entry_price_locked: float | None = None   # Immutable after entry
sl_initial: float | None = None           # Original SL (immutable, reference)
sl_current: float | None = None           # Active SL — only ever moves UP
tp1: float | None = None                  # Take Profit 1 (immutable)
tp2: float | None = None                  # Take Profit 2 (immutable)
tp3: float | None = None                  # Take Profit 3 (immutable)
tp1_hit: bool = False                     # Has price reached TP1?
tp2_hit: bool = False                     # Has price reached TP2?
trade_notes: str = ""                     # Audit log of SL movements
```

### 4.2 Lock at Entry

In `PaperExecutor.buy()`, after creating the position:

```python
entry = fill_price  # actual execution price
sl = trade_plan.stop_loss
pos.entry_price_locked = entry
pos.sl_initial = sl
pos.sl_current = sl
pos.tp1 = trade_plan.take_profit_1
pos.tp2 = trade_plan.take_profit_2
pos.tp3 = trade_plan.take_profit_3
pos.tp1_hit = False
pos.tp2_hit = False
pos.trade_notes = f"{datetime.now():%Y-%m-%d} Locked: entry={entry}, SL={sl}"
```

TP/SL is **never recalculated** for positions where `entry_price_locked is not None`.

### 4.3 Trailing Stop Logic

New function `check_trailing_stops(portfolio: PaperPortfolio) -> list[TrailingEvent]` in `autopilot/executor.py`:

```
For each position with locked levels:

  IF current_price >= tp2 AND NOT tp2_hit:
      sl_current = tp1  (lock TP1 profit)
      tp1_hit = True   # also mark TP1 hit (price passed through it)
      tp2_hit = True
      emit: TrailingEvent(type="SL_RAISED_TO_TP1", symbol, old_sl, new_sl)

  ELIF current_price >= tp1 AND NOT tp1_hit:
      sl_current = entry_price_locked  (breakeven)
      tp1_hit = True
      emit: TrailingEvent(type="SL_RAISED_TO_BREAKEVEN", symbol, old_sl, new_sl)

  IF current_price <= sl_current:
      emit: TrailingEvent(type="SL_HIT", symbol, sl_current, current_price)

  IF current_price >= tp3:
      emit: TrailingEvent(type="FULL_TARGET", symbol, tp3, current_price)
```

Rule: `sl_current` is only ever assigned a value **higher** than its current value.

### 4.4 Morning Briefing Integration

`briefing/daily.py` calls `check_trailing_stops()` and displays:

```
📊 POSISI AKTIF
─────────────────────────────────────────
BBCA  Rp 10,300  (+4.6%)  ✅ TP1 HIT — SL naik ke breakeven (9,850)
      SL: 9,850 | TP2: 10,835 | TP3: 11,328

TLKM  Rp 3,050   (-4.7%)  ⚠️  DEKAT SL! Gap: -1.7%
      SL: 3,104 | TP1: 3,360 | TP2: 3,520

BBRI  Rp 4,500   (0.0%)   ─  Dalam range
      SL: 4,275 | TP1: 4,725 | TP2: 4,950
```

### 4.5 Integration with `quality` and `autopilot` commands

- `quality SYMBOL --ai` → runs intelligence pipeline, shows Confidence Score + breakdown
- `autopilot` → only executes HIGH confidence signals, locks TP/SL on entry
- `portfolio list` → shows locked levels + trailing stop status

---

## 5. Integration Points

### Modified files
| File | Change |
|------|--------|
| `scoring/intelligence/__init__.py` | New package |
| `scoring/intelligence/regime.py` | New |
| `scoring/intelligence/mtf.py` | New |
| `scoring/intelligence/breakout.py` | New |
| `scoring/intelligence/candles.py` | New |
| `scoring/intelligence/relative_strength.py` | New |
| `scoring/intelligence/pipeline.py` | New |
| `autopilot/engine.py` | Call intelligence pipeline before signal execution |
| `autopilot/executor.py` | Lock TP/SL at entry; add `check_trailing_stops()` |
| `briefing/daily.py` | Call `check_trailing_stops()`, display locked levels |
| `cli/main.py` | `quality --ai` shows confidence breakdown; `portfolio list` shows locked levels |

### Unchanged
- Existing 6-gate scoring (`scoring/gates.py`, `scoring/factors.py`) — intelligence pipeline runs **after** gates, not replacing them
- `focused_validator.py` — still runs for final AI approval on HIGH signals
- All existing CLI commands retain backward compatibility

---

## 6. Error Handling

| Failure | Behaviour |
|---------|-----------|
| IHSG fetch fails | Log warning, skip regime filter (don't block all signals) |
| 4H data unavailable (symbol too new) | MTF uses 2/2 (weekly + daily) instead of 3/3 |
| Gemini API error / timeout | +0 points, signal not blocked |
| Candlestick data < 3 candles | Skip pattern detection, +0 points |
| Position has no locked levels (legacy) | Skip trailing stop check, show warning |

---

## 7. Out of Scope

- Real-time tick data (not available with yfinance-only)
- ML/XGBoost model training
- Backtesting of the new pipeline (future phase)
- Fundamental scoring changes (irrelevant for 1–5 day swing)
- Notification via Telegram (existing system handles this)
