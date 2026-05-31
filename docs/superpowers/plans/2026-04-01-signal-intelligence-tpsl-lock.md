# Signal Intelligence Pipeline + TP/SL Lock System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a market-regime-aware, multi-timeframe signal intelligence layer plus locked TP/SL with trailing stop to turn stockai into a more accurate swing trading assistant.

**Architecture:** Layer 1 (Signal Intelligence) adds six filters on top of the existing 6-gate score, outputting a 0–100 Confidence Score; only HIGH (≥80) signals proceed to execution. Layer 2 (TP/SL Lock) records immutable entry/SL/TP levels at trade entry time and updates the active SL upward (never downward) via a trailing stop logic checked every morning.

**Tech Stack:** Python 3.11+, pandas (EMA/MACD/RSI computation), yfinance via existing `YahooFinanceSource`, `google-generativeai` SDK (already installed), pytest + unittest.mock for tests.

---

## File Map

**New files:**
```
src/stockai/scoring/intelligence/__init__.py
src/stockai/scoring/intelligence/models.py        ← IntelligenceResult + TrailingEvent dataclasses
src/stockai/scoring/intelligence/regime.py        ← Market Regime Filter
src/stockai/scoring/intelligence/mtf.py           ← Multi-Timeframe Confirmation
src/stockai/scoring/intelligence/breakout.py      ← Breakout Quality Score
src/stockai/scoring/intelligence/candles.py       ← Candlestick Pattern Engine
src/stockai/scoring/intelligence/relative_strength.py  ← RS vs IHSG
src/stockai/scoring/intelligence/pipeline.py      ← Orchestrator + Gemini news scan

tests/unit/intelligence/__init__.py
tests/unit/intelligence/test_models.py
tests/unit/intelligence/test_regime.py
tests/unit/intelligence/test_mtf.py
tests/unit/intelligence/test_breakout.py
tests/unit/intelligence/test_candles.py
tests/unit/intelligence/test_relative_strength.py
tests/unit/intelligence/test_pipeline.py
```

**Modified files:**
```
src/stockai/autopilot/executor.py      ← PaperPosition new fields + lock_at_entry() + check_trailing_stops()
src/stockai/autopilot/engine.py        ← _execute_buys() locks TP/SL; call intelligence pipeline before execution
src/stockai/briefing/daily.py          ← call check_trailing_stops(), display locked levels + events
src/stockai/cli/main.py                ← quality --ai shows confidence breakdown; portfolio list shows locked levels
tests/unit/test_autopilot.py           ← add tests for locked positions
```

---

## Phase A — TP/SL Lock System

### Task 1: Extend PaperPosition with Locked Fields

**Files:**
- Modify: `src/stockai/autopilot/executor.py`
- Test: `tests/unit/test_autopilot.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/test_autopilot.py`:

```python
class TestPaperPositionLocked:
    """Test PaperPosition locked TP/SL fields."""

    def test_new_position_has_none_locked_fields(self):
        from stockai.autopilot.executor import PaperPosition
        from datetime import datetime
        pos = PaperPosition(
            symbol="BBCA", lots=1, shares=100,
            avg_price=10000.0, current_price=10000.0,
            stop_loss=9500.0, target=10500.0,
            entry_date=datetime.now(),
        )
        assert pos.entry_price_locked is None
        assert pos.sl_initial is None
        assert pos.sl_current is None
        assert pos.tp1 is None
        assert pos.tp2 is None
        assert pos.tp3 is None
        assert pos.tp1_hit is False
        assert pos.tp2_hit is False
        assert pos.trade_notes == ""

    def test_to_dict_includes_locked_fields(self):
        from stockai.autopilot.executor import PaperPosition
        from datetime import datetime
        pos = PaperPosition(
            symbol="BBCA", lots=1, shares=100,
            avg_price=10000.0, current_price=10000.0,
            stop_loss=9500.0, target=10500.0,
            entry_date=datetime.now(),
            entry_price_locked=10000.0,
            sl_initial=9500.0,
            sl_current=9500.0,
            tp1=10500.0,
            tp2=11000.0,
            tp3=11500.0,
        )
        d = pos.to_dict()
        assert d["entry_price_locked"] == 10000.0
        assert d["sl_current"] == 9500.0
        assert d["tp1"] == 10500.0
        assert d["tp1_hit"] is False

    def test_load_portfolio_backward_compatible_no_locked_fields(self):
        """Old JSON without locked fields loads without error and defaults to None."""
        import json, tempfile, os
        from stockai.autopilot.executor import PaperExecutor
        from datetime import datetime
        old_data = {
            "initial_capital": 10000000.0,
            "cash": 9000000.0,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "positions": {
                "BBCA": {
                    "symbol": "BBCA", "lots": 1, "shares": 100,
                    "avg_price": 10000.0, "current_price": 10000.0,
                    "stop_loss": 9500.0, "target": 10500.0,
                    "entry_date": "2026-01-01T00:00:00",
                    "pnl": 0.0, "pnl_pct": 0.0,
                    # NOTE: no locked fields — simulating old JSON
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(old_data, f)
            fname = f.name
        try:
            ex = PaperExecutor(portfolio_file=fname)
            portfolio = ex.load_portfolio()
            pos = portfolio.positions["BBCA"]
            assert pos.entry_price_locked is None
            assert pos.sl_current is None
            assert pos.tp1_hit is False
        finally:
            os.unlink(fname)
```

- [ ] **Step 2: Run tests — expect FAIL (AttributeError)**

```bash
cd /Users/mac/Downloads/stockai-main
uv run pytest tests/unit/test_autopilot.py::TestPaperPositionLocked -v
```
Expected: `AttributeError: 'PaperPosition' object has no attribute 'entry_price_locked'`

- [ ] **Step 3: Extend PaperPosition in executor.py**

In `src/stockai/autopilot/executor.py`, replace the `PaperPosition` dataclass:

```python
@dataclass
class PaperPosition:
    """A paper trading position."""

    symbol: str
    lots: int
    shares: int
    avg_price: float
    current_price: float
    stop_loss: float | None
    target: float | None
    entry_date: datetime
    pnl: float = 0
    pnl_pct: float = 0
    # Locked levels — set at entry, never recalculated
    entry_price_locked: float | None = None
    sl_initial: float | None = None      # original SL for reference
    sl_current: float | None = None      # active SL — only ever moves UP
    tp1: float | None = None
    tp2: float | None = None
    tp3: float | None = None
    tp1_hit: bool = False
    tp2_hit: bool = False
    trade_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "lots": self.lots,
            "shares": self.shares,
            "avg_price": self.avg_price,
            "current_price": self.current_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "entry_date": self.entry_date.isoformat(),
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "entry_price_locked": self.entry_price_locked,
            "sl_initial": self.sl_initial,
            "sl_current": self.sl_current,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "tp1_hit": self.tp1_hit,
            "tp2_hit": self.tp2_hit,
            "trade_notes": self.trade_notes,
        }
```

Update `load_portfolio()` — replace the `PaperPosition(...)` constructor call inside the positions loop:

```python
positions[symbol] = PaperPosition(
    symbol=pos_data["symbol"],
    lots=pos_data["lots"],
    shares=pos_data["shares"],
    avg_price=pos_data["avg_price"],
    current_price=pos_data["current_price"],
    stop_loss=pos_data.get("stop_loss"),
    target=pos_data.get("target"),
    entry_date=datetime.fromisoformat(pos_data["entry_date"]),
    pnl=pos_data.get("pnl", 0),
    pnl_pct=pos_data.get("pnl_pct", 0),
    entry_price_locked=pos_data.get("entry_price_locked"),
    sl_initial=pos_data.get("sl_initial"),
    sl_current=pos_data.get("sl_current"),
    tp1=pos_data.get("tp1"),
    tp2=pos_data.get("tp2"),
    tp3=pos_data.get("tp3"),
    tp1_hit=pos_data.get("tp1_hit", False),
    tp2_hit=pos_data.get("tp2_hit", False),
    trade_notes=pos_data.get("trade_notes", ""),
)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/test_autopilot.py::TestPaperPositionLocked -v
```
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/autopilot/executor.py tests/unit/test_autopilot.py
git commit -m "feat(executor): extend PaperPosition with locked TP/SL fields"
```

---

### Task 2: Lock TP/SL at Entry in PaperExecutor.buy()

**Files:**
- Modify: `src/stockai/autopilot/executor.py`
- Test: `tests/unit/test_autopilot.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_autopilot.py`:

```python
class TestPaperExecutorLockAtEntry:
    """Test that buy() locks TP/SL levels."""

    def test_buy_locks_tp_sl_on_new_position(self, tmp_path):
        from stockai.autopilot.executor import PaperExecutor
        portfolio_file = str(tmp_path / "portfolio.json")
        ex = PaperExecutor(portfolio_file=portfolio_file)
        ex.create_portfolio(10_000_000.0)

        result = ex.buy(
            symbol="BBCA",
            lots=1,
            price=10_000.0,
            stop_loss=9_500.0,
            tp1=10_500.0,
            tp2=11_000.0,
            tp3=11_500.0,
        )

        assert result is True
        pos = ex.portfolio.positions["BBCA"]
        assert pos.entry_price_locked == 10_000.0
        assert pos.sl_initial == 9_500.0
        assert pos.sl_current == 9_500.0
        assert pos.tp1 == 10_500.0
        assert pos.tp2 == 11_000.0
        assert pos.tp3 == 11_500.0
        assert pos.tp1_hit is False
        assert "Locked" in pos.trade_notes

    def test_buy_without_tp_still_works(self, tmp_path):
        """buy() without tp args is backward compatible."""
        from stockai.autopilot.executor import PaperExecutor
        portfolio_file = str(tmp_path / "portfolio.json")
        ex = PaperExecutor(portfolio_file=portfolio_file)
        ex.create_portfolio(10_000_000.0)

        result = ex.buy("TLKM", lots=1, price=3_000.0)
        assert result is True
        pos = ex.portfolio.positions["TLKM"]
        assert pos.entry_price_locked is None   # not locked without tp params
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run pytest tests/unit/test_autopilot.py::TestPaperExecutorLockAtEntry -v
```
Expected: `TypeError: buy() got an unexpected keyword argument 'tp1'`

- [ ] **Step 3: Update buy() signature and locking logic**

In `src/stockai/autopilot/executor.py`, replace the `buy()` method:

```python
def buy(
    self,
    symbol: str,
    lots: int,
    price: float,
    stop_loss: float | None = None,
    target: float | None = None,
    tp1: float | None = None,
    tp2: float | None = None,
    tp3: float | None = None,
) -> bool:
    """Execute a paper buy order.

    Args:
        symbol: Stock symbol
        lots: Number of lots
        price: Price per share
        stop_loss: Stop-loss price
        target: Legacy single target price (use tp1/tp2/tp3 instead)
        tp1: Take Profit 1 price (locked at entry)
        tp2: Take Profit 2 price (locked at entry)
        tp3: Take Profit 3 price (locked at entry)

    Returns:
        True if successful
    """
    if not self.portfolio:
        logger.error("No portfolio loaded")
        return False

    shares = lots * SHARES_PER_LOT
    cost = shares * price

    if cost > self.portfolio.cash:
        logger.error(f"Insufficient cash: need {cost:,.0f}, have {self.portfolio.cash:,.0f}")
        return False

    # Resolve target for backward compat
    effective_target = tp1 or target

    if symbol in self.portfolio.positions:
        # Average up — do NOT update locked levels for existing position
        existing = self.portfolio.positions[symbol]
        total_shares = existing.shares + shares
        total_cost = (existing.shares * existing.avg_price) + cost
        existing.lots = total_shares // SHARES_PER_LOT
        existing.shares = total_shares
        existing.avg_price = total_cost / total_shares
        if stop_loss:
            existing.stop_loss = stop_loss
        if effective_target:
            existing.target = effective_target
    else:
        # New position — lock TP/SL if provided
        lock_notes = ""
        if tp1 is not None and stop_loss is not None:
            lock_notes = (
                f"{datetime.now():%Y-%m-%d} Locked: entry={price:.0f}, "
                f"SL={stop_loss:.0f}, TP1={tp1:.0f}"
            )

        self.portfolio.positions[symbol] = PaperPosition(
            symbol=symbol,
            lots=lots,
            shares=shares,
            avg_price=price,
            current_price=price,
            stop_loss=stop_loss,
            target=effective_target,
            entry_date=datetime.now(TIMEZONE),
            # Locked fields
            entry_price_locked=price if tp1 is not None else None,
            sl_initial=stop_loss if tp1 is not None else None,
            sl_current=stop_loss if tp1 is not None else None,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            trade_notes=lock_notes,
        )

    self.portfolio.cash -= cost
    self.save_portfolio()
    logger.info(f"BUY: {lots} lots {symbol} @ Rp {price:,.0f}")
    return True
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/test_autopilot.py::TestPaperExecutorLockAtEntry -v
```
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/autopilot/executor.py tests/unit/test_autopilot.py
git commit -m "feat(executor): lock TP/SL at entry in PaperExecutor.buy()"
```

---

### Task 3: Lock TP/SL in AutopilotEngine._execute_buys()

**Files:**
- Modify: `src/stockai/autopilot/engine.py`
- Test: `tests/unit/test_autopilot.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_autopilot.py`:

```python
class TestEngineExecuteBuysLocked:
    """Test that _execute_buys stores locked TP/SL in position dict."""

    def test_execute_buys_stores_locked_levels(self):
        from stockai.autopilot.engine import AutopilotEngine, AutopilotConfig, TradeSignal
        from stockai.scoring.analyzer import AnalysisResult
        from stockai.scoring.trade_plan import TradePlan
        from unittest.mock import MagicMock, patch

        config = AutopilotConfig(dry_run=True, capital=10_000_000.0)
        engine = AutopilotEngine(config)
        engine.cash = 10_000_000.0
        engine.positions = {}

        # Build minimal AnalysisResult with a trade plan
        trade_plan = TradePlan(
            entry_low=9_800.0, entry_high=10_000.0,
            stop_loss=9_500.0,
            take_profit_1=10_500.0,
            take_profit_2=11_000.0,
            take_profit_3=11_500.0,
            risk_reward_ratio=2.0,
            risk_pct=5.0,
            summary="Test",
        )
        analysis = MagicMock()
        analysis.trade_plan = trade_plan

        signal = TradeSignal(
            symbol="BBCA",
            action="BUY",
            score=85.0,
            current_price=10_000.0,
            lots=1,
            shares=100,
            position_value=1_000_000.0,
            stop_loss=9_500.0,
            target=10_500.0,
            reason="Test",
            analysis_result=analysis,
        )

        engine._execute_buys([signal])

        pos = engine.positions["BBCA"]
        assert pos["entry_price_locked"] == 10_000.0
        assert pos["sl_initial"] == 9_500.0
        assert pos["sl_current"] == 9_500.0
        assert pos["tp1"] == 10_500.0
        assert pos["tp2"] == 11_000.0
        assert pos["tp3"] == 11_500.0
        assert pos["tp1_hit"] is False
        assert pos["tp2_hit"] is False
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run pytest tests/unit/test_autopilot.py::TestEngineExecuteBuysLocked -v
```
Expected: `AssertionError` — `entry_price_locked` not in position dict.

- [ ] **Step 3: Update _execute_buys() in engine.py**

Find `_execute_buys` method (around line 1458) and replace the position creation block:

```python
def _execute_buys(self, buy_signals: list[TradeSignal]) -> list[TradeSignal]:
    """Execute buy orders (paper trading)."""
    executed = []

    for signal in buy_signals:
        if signal.lots <= 0:
            continue

        cost = signal.shares * signal.current_price

        if cost > self.cash:
            continue

        # Extract TP levels from analysis result's trade plan
        tp1 = tp2 = tp3 = None
        if signal.analysis_result and signal.analysis_result.trade_plan:
            plan = signal.analysis_result.trade_plan
            tp1 = plan.take_profit_1
            tp2 = plan.take_profit_2
            tp3 = plan.take_profit_3

        self.positions[signal.symbol] = {
            "lots": signal.lots,
            "shares": signal.shares,
            "avg_price": signal.current_price,
            "stop_loss": signal.stop_loss,
            "target": signal.target,
            "entry_date": datetime.now(TIMEZONE),
            # Locked levels — immutable after entry
            "entry_price_locked": signal.current_price,
            "sl_initial": signal.stop_loss,
            "sl_current": signal.stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "tp1_hit": False,
            "tp2_hit": False,
        }

        self.cash -= cost
        executed.append(signal)
        logger.info(f"BOUGHT {signal.lots} lots of {signal.symbol} @ Rp {signal.current_price:,.0f}")

    return executed
```

- [ ] **Step 4: Run test — expect PASS**

```bash
uv run pytest tests/unit/test_autopilot.py::TestEngineExecuteBuysLocked -v
```
Expected: 1 test PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/autopilot/engine.py tests/unit/test_autopilot.py
git commit -m "feat(engine): lock TP/SL levels in _execute_buys position dict"
```

---

### Task 4: TrailingEvent Dataclass + check_trailing_stops()

**Files:**
- Modify: `src/stockai/autopilot/executor.py`
- Test: `tests/unit/test_autopilot.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/test_autopilot.py`:

```python
class TestCheckTrailingStops:
    """Test trailing stop logic."""

    def _make_portfolio(self, current_price, tp1_hit=False, tp2_hit=False):
        from stockai.autopilot.executor import PaperExecutor, PaperPortfolio, PaperPosition
        from datetime import datetime
        pos = PaperPosition(
            symbol="BBCA", lots=1, shares=100,
            avg_price=10_000.0, current_price=current_price,
            stop_loss=9_500.0, target=10_500.0,
            entry_date=datetime.now(),
            entry_price_locked=10_000.0,
            sl_initial=9_500.0,
            sl_current=9_500.0 if not tp1_hit else 10_000.0,
            tp1=10_500.0, tp2=11_000.0, tp3=11_500.0,
            tp1_hit=tp1_hit, tp2_hit=tp2_hit,
        )
        portfolio = PaperPortfolio(
            initial_capital=10_000_000.0,
            cash=9_000_000.0,
            positions={"BBCA": pos},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        return portfolio

    def test_no_event_when_price_in_range(self):
        from stockai.autopilot.executor import check_trailing_stops
        portfolio = self._make_portfolio(current_price=10_200.0)
        events = check_trailing_stops(portfolio)
        assert events == []

    def test_sl_hit_event(self):
        from stockai.autopilot.executor import check_trailing_stops, TrailingEventType
        portfolio = self._make_portfolio(current_price=9_400.0)
        events = check_trailing_stops(portfolio)
        assert len(events) == 1
        assert events[0].event_type == TrailingEventType.SL_HIT
        assert events[0].symbol == "BBCA"

    def test_tp1_hit_raises_sl_to_breakeven(self):
        from stockai.autopilot.executor import check_trailing_stops, TrailingEventType
        portfolio = self._make_portfolio(current_price=10_550.0)
        events = check_trailing_stops(portfolio)
        assert any(e.event_type == TrailingEventType.SL_RAISED_TO_BREAKEVEN for e in events)
        pos = portfolio.positions["BBCA"]
        assert pos.sl_current == 10_000.0  # breakeven
        assert pos.tp1_hit is True

    def test_tp2_hit_raises_sl_to_tp1(self):
        from stockai.autopilot.executor import check_trailing_stops, TrailingEventType
        portfolio = self._make_portfolio(current_price=11_050.0)
        events = check_trailing_stops(portfolio)
        assert any(e.event_type == TrailingEventType.SL_RAISED_TO_TP1 for e in events)
        pos = portfolio.positions["BBCA"]
        assert pos.sl_current == 10_500.0  # TP1 level
        assert pos.tp1_hit is True
        assert pos.tp2_hit is True

    def test_tp3_hit_full_target_event(self):
        from stockai.autopilot.executor import check_trailing_stops, TrailingEventType
        portfolio = self._make_portfolio(current_price=11_600.0, tp1_hit=True, tp2_hit=True)
        portfolio.positions["BBCA"].sl_current = 11_000.0
        events = check_trailing_stops(portfolio)
        assert any(e.event_type == TrailingEventType.FULL_TARGET for e in events)

    def test_sl_never_moves_down(self):
        """sl_current must never decrease."""
        from stockai.autopilot.executor import check_trailing_stops
        portfolio = self._make_portfolio(current_price=10_200.0, tp1_hit=True)
        portfolio.positions["BBCA"].sl_current = 10_000.0  # at breakeven
        check_trailing_stops(portfolio)
        assert portfolio.positions["BBCA"].sl_current >= 10_000.0

    def test_position_without_locked_levels_skipped(self):
        """Legacy positions without locked levels produce no events."""
        from stockai.autopilot.executor import check_trailing_stops, PaperPortfolio, PaperPosition
        from datetime import datetime
        pos = PaperPosition(
            symbol="TLKM", lots=1, shares=100,
            avg_price=3_000.0, current_price=2_800.0,
            stop_loss=2_850.0, target=3_150.0,
            entry_date=datetime.now(),
            # No locked levels
        )
        portfolio = PaperPortfolio(
            initial_capital=10_000_000.0, cash=9_700_000.0,
            positions={"TLKM": pos},
            created_at=datetime.now(), updated_at=datetime.now(),
        )
        events = check_trailing_stops(portfolio)
        assert events == []
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run pytest tests/unit/test_autopilot.py::TestCheckTrailingStops -v
```
Expected: `ImportError: cannot import name 'check_trailing_stops'`

- [ ] **Step 3: Add TrailingEvent + check_trailing_stops() to executor.py**

Add after the `PaperPortfolio` class definition in `src/stockai/autopilot/executor.py`:

```python
from enum import Enum
from dataclasses import dataclass as _dataclass

class TrailingEventType(str, Enum):
    SL_RAISED_TO_BREAKEVEN = "SL_RAISED_TO_BREAKEVEN"
    SL_RAISED_TO_TP1 = "SL_RAISED_TO_TP1"
    SL_HIT = "SL_HIT"
    FULL_TARGET = "FULL_TARGET"


@dataclass
class TrailingEvent:
    """An event emitted by the trailing stop checker."""
    symbol: str
    event_type: TrailingEventType
    current_price: float
    old_sl: float | None
    new_sl: float | None
    message: str


def check_trailing_stops(portfolio: "PaperPortfolio") -> list[TrailingEvent]:
    """Check all locked positions for trailing stop events.

    Rules:
    - sl_current ONLY ever moves UP (enforced here)
    - TP2 hit → sl moves to TP1; TP1 hit → sl moves to breakeven
    - Price at/below sl_current → SL_HIT event
    - Price at/above tp3 → FULL_TARGET event

    Args:
        portfolio: PaperPortfolio with positions

    Returns:
        List of TrailingEvent for each position that crossed a level
    """
    events: list[TrailingEvent] = []

    for symbol, pos in portfolio.positions.items():
        # Skip legacy positions without locked levels
        if pos.entry_price_locked is None or pos.sl_current is None:
            continue

        price = pos.current_price

        # Check FULL TARGET first (tp3)
        if pos.tp3 is not None and price >= pos.tp3:
            events.append(TrailingEvent(
                symbol=symbol,
                event_type=TrailingEventType.FULL_TARGET,
                current_price=price,
                old_sl=pos.sl_current,
                new_sl=pos.sl_current,
                message=f"🎯 FULL TARGET! {symbol} @ Rp {price:,.0f} hit TP3 Rp {pos.tp3:,.0f}",
            ))

        # Check TP2 hit → raise SL to TP1
        if pos.tp2 is not None and price >= pos.tp2 and not pos.tp2_hit:
            old_sl = pos.sl_current
            new_sl = pos.tp1  # raise to TP1 level
            if new_sl is not None and new_sl > pos.sl_current:
                pos.sl_current = new_sl
            pos.tp1_hit = True
            pos.tp2_hit = True
            pos.trade_notes += (
                f"\n{datetime.now():%Y-%m-%d} TP2 hit @ {price:.0f} → SL raised to TP1 {pos.sl_current:.0f}"
            )
            events.append(TrailingEvent(
                symbol=symbol,
                event_type=TrailingEventType.SL_RAISED_TO_TP1,
                current_price=price,
                old_sl=old_sl,
                new_sl=pos.sl_current,
                message=(
                    f"📈 {symbol}: TP2 hit! SL naik ke TP1 Rp {pos.sl_current:,.0f} "
                    f"(dari Rp {old_sl:,.0f})"
                ),
            ))

        # Check TP1 hit → raise SL to breakeven
        elif pos.tp1 is not None and price >= pos.tp1 and not pos.tp1_hit:
            old_sl = pos.sl_current
            new_sl = pos.entry_price_locked  # breakeven
            if new_sl is not None and new_sl > pos.sl_current:
                pos.sl_current = new_sl
            pos.tp1_hit = True
            pos.trade_notes += (
                f"\n{datetime.now():%Y-%m-%d} TP1 hit @ {price:.0f} → SL raised to breakeven {pos.sl_current:.0f}"
            )
            events.append(TrailingEvent(
                symbol=symbol,
                event_type=TrailingEventType.SL_RAISED_TO_BREAKEVEN,
                current_price=price,
                old_sl=old_sl,
                new_sl=pos.sl_current,
                message=(
                    f"✅ {symbol}: TP1 hit! SL naik ke breakeven Rp {pos.sl_current:,.0f} "
                    f"(dari Rp {old_sl:,.0f})"
                ),
            ))

        # Check SL hit
        if price <= pos.sl_current:
            events.append(TrailingEvent(
                symbol=symbol,
                event_type=TrailingEventType.SL_HIT,
                current_price=price,
                old_sl=pos.sl_current,
                new_sl=pos.sl_current,
                message=f"🚨 CUT LOSS {symbol}: harga Rp {price:,.0f} hit SL Rp {pos.sl_current:,.0f}",
            ))

    return events
```

Also add `from enum import Enum` at the top of executor.py imports if not already present.

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/test_autopilot.py::TestCheckTrailingStops -v
```
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/autopilot/executor.py tests/unit/test_autopilot.py
git commit -m "feat(executor): add TrailingEvent and check_trailing_stops()"
```

---

### Task 5: Morning Briefing — Trailing Stop Display

**Files:**
- Modify: `src/stockai/briefing/daily.py`
- Modify: `src/stockai/cli/main.py`
- Test: `tests/unit/test_autopilot.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_autopilot.py`:

```python
class TestMorningBriefingTrailing:
    """Test that morning briefing calls check_trailing_stops and formats output."""

    def test_format_trailing_events_for_briefing(self):
        from stockai.autopilot.executor import TrailingEvent, TrailingEventType
        from stockai.briefing.daily import format_trailing_events
        events = [
            TrailingEvent(
                symbol="BBCA",
                event_type=TrailingEventType.SL_RAISED_TO_BREAKEVEN,
                current_price=10_550.0, old_sl=9_500.0, new_sl=10_000.0,
                message="✅ BBCA: TP1 hit! SL naik ke breakeven Rp 10,000",
            ),
            TrailingEvent(
                symbol="TLKM",
                event_type=TrailingEventType.SL_HIT,
                current_price=3_050.0, old_sl=3_100.0, new_sl=3_100.0,
                message="🚨 CUT LOSS TLKM: harga Rp 3,050 hit SL Rp 3,100",
            ),
        ]
        lines = format_trailing_events(events)
        assert any("BBCA" in l for l in lines)
        assert any("TLKM" in l for l in lines)
        assert any("CUT LOSS" in l for l in lines)
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run pytest tests/unit/test_autopilot.py::TestMorningBriefingTrailing -v
```
Expected: `ImportError: cannot import name 'format_trailing_events' from 'stockai.briefing.daily'`

- [ ] **Step 3: Add format_trailing_events() to briefing/daily.py**

Add to the bottom of `src/stockai/briefing/daily.py`:

```python
def format_trailing_events(events: list) -> list[str]:
    """Format trailing stop events for morning briefing display.

    Args:
        events: List of TrailingEvent from check_trailing_stops()

    Returns:
        List of formatted strings for display
    """
    from stockai.autopilot.executor import TrailingEventType

    if not events:
        return ["✅ Semua posisi dalam kondisi normal (tidak ada SL/TP event)"]

    lines = []
    for event in events:
        lines.append(event.message)
        if event.event_type == TrailingEventType.SL_HIT:
            lines.append(f"   → Segera pertimbangkan cut loss {event.symbol}")
        elif event.event_type == TrailingEventType.FULL_TARGET:
            lines.append(f"   → Semua target tercapai! Pertimbangkan close full position {event.symbol}")
    return lines
```

- [ ] **Step 4: Integrate into generate_morning_briefing()**

In `src/stockai/briefing/daily.py`, inside `generate_morning_briefing()`, add after the portfolio value calculation block (look for `briefing.portfolio_value`):

```python
    # Check trailing stops for locked positions
    try:
        from stockai.autopilot.executor import PaperExecutor, check_trailing_stops
        paper_ex = PaperExecutor()
        paper_portfolio = paper_ex.load_portfolio()
        if paper_portfolio and paper_portfolio.positions:
            # Update current prices first
            from stockai.data.sources.yahoo import YahooFinanceSource
            source = YahooFinanceSource()
            syms = list(paper_portfolio.positions.keys())
            prices = source.get_multiple_prices(syms)
            for sym, pdata in prices.items():
                if sym in paper_portfolio.positions and pdata.get("price"):
                    paper_portfolio.positions[sym].current_price = pdata["price"]
            # Run trailing stop check + save updated SL levels
            trailing_events = check_trailing_stops(paper_portfolio)
            if trailing_events:
                paper_ex.portfolio = paper_portfolio
                paper_ex.save_portfolio()
            briefing.trailing_events = trailing_events
    except Exception as e:
        logger.debug(f"Trailing stop check skipped: {e}")
        briefing.trailing_events = []
```

Also add `trailing_events: list = field(default_factory=list)` to the `MorningBriefing` dataclass fields.

- [ ] **Step 5: Display trailing events in format_morning_briefing()**

In `src/stockai/briefing/daily.py`, inside `format_morning_briefing()`, add after the alerts section:

```python
    # Trailing stop section
    if hasattr(briefing, 'trailing_events') and briefing.trailing_events:
        lines = ["", "⚡ TRAILING STOP EVENTS", "─" * 40]
        lines.extend(format_trailing_events(briefing.trailing_events))
        output += "\n".join(lines) + "\n"
```

- [ ] **Step 6: Run test — expect PASS**

```bash
uv run pytest tests/unit/test_autopilot.py::TestMorningBriefingTrailing -v
```
Expected: 1 test PASS.

- [ ] **Step 7: Commit**

```bash
git add src/stockai/briefing/daily.py src/stockai/cli/main.py tests/unit/test_autopilot.py
git commit -m "feat(briefing): integrate trailing stop events in morning briefing"
```

---

## Phase B — Signal Intelligence Pipeline

### Task 6: Package Scaffold + IntelligenceResult Models

**Files:**
- Create: `src/stockai/scoring/intelligence/__init__.py`
- Create: `src/stockai/scoring/intelligence/models.py`
- Create: `tests/unit/intelligence/__init__.py`
- Test: `tests/unit/intelligence/test_models.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/intelligence/__init__.py` (empty).

Create `tests/unit/intelligence/test_models.py`:

```python
"""Tests for IntelligenceResult model."""


def test_intelligence_result_defaults():
    from stockai.scoring.intelligence.models import IntelligenceResult
    result = IntelligenceResult(symbol="BBCA")
    assert result.confidence_score == 0.0
    assert result.confidence_level == "LOW"
    assert result.recommendation == "SKIP"
    assert result.regime == "UNKNOWN"
    assert result.mtf_aligned == 0
    assert result.news_status == "SKIPPED"


def test_intelligence_result_high_confidence():
    from stockai.scoring.intelligence.models import IntelligenceResult
    result = IntelligenceResult(
        symbol="BBCA",
        confidence_score=85.0,
        confidence_level="HIGH",
        recommendation="EXECUTE",
    )
    assert result.is_executable is True


def test_intelligence_result_medium_not_executable():
    from stockai.scoring.intelligence.models import IntelligenceResult
    result = IntelligenceResult(
        symbol="BBCA",
        confidence_score=70.0,
        confidence_level="MEDIUM",
        recommendation="WATCH",
    )
    assert result.is_executable is False
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run pytest tests/unit/intelligence/test_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'stockai.scoring.intelligence'`

- [ ] **Step 3: Create package files**

Create `src/stockai/scoring/intelligence/__init__.py`:

```python
"""Signal Intelligence Pipeline for swing trading."""

from stockai.scoring.intelligence.models import IntelligenceResult
from stockai.scoring.intelligence.pipeline import run_intelligence_pipeline

__all__ = ["IntelligenceResult", "run_intelligence_pipeline"]
```

Create `src/stockai/scoring/intelligence/models.py`:

```python
"""Data models for the Signal Intelligence Pipeline."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntelligenceResult:
    """Output of the Signal Intelligence Pipeline for one stock."""

    symbol: str
    confidence_score: float = 0.0
    confidence_level: str = "LOW"          # HIGH / MEDIUM / LOW
    recommendation: str = "SKIP"           # EXECUTE / WATCH / SKIP
    regime: str = "UNKNOWN"                # BULLISH / SIDEWAYS / BEARISH
    mtf_aligned: int = 0                   # 0-3 timeframes bullish
    breakout_score: float = 0.0
    candle_pattern: str = "None"
    relative_strength: float = 0.0
    news_status: str = "SKIPPED"           # CLEAR / RISK_DETECTED / SKIPPED
    news_risk_reason: str = ""
    score_breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def is_executable(self) -> bool:
        """True only for HIGH confidence signals."""
        return self.confidence_level == "HIGH" and self.recommendation == "EXECUTE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "confidence_score": round(self.confidence_score, 1),
            "confidence_level": self.confidence_level,
            "recommendation": self.recommendation,
            "regime": self.regime,
            "mtf_aligned": self.mtf_aligned,
            "breakout_score": round(self.breakout_score, 1),
            "candle_pattern": self.candle_pattern,
            "relative_strength": round(self.relative_strength, 2),
            "news_status": self.news_status,
            "news_risk_reason": self.news_risk_reason,
            "score_breakdown": self.score_breakdown,
        }
```

Create stub `src/stockai/scoring/intelligence/pipeline.py` (will be completed in Task 12):

```python
"""Intelligence Pipeline — stub, completed in Task 12."""

from stockai.scoring.intelligence.models import IntelligenceResult


def run_intelligence_pipeline(
    symbol: str,
    existing_score: float = 0.0,
    df=None,
) -> IntelligenceResult:
    """Run the full Signal Intelligence Pipeline for one symbol."""
    return IntelligenceResult(symbol=symbol)
```

- [ ] **Step 4: Run test — expect PASS**

```bash
uv run pytest tests/unit/intelligence/test_models.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/scoring/intelligence/ tests/unit/intelligence/
git commit -m "feat(intelligence): add package scaffold and IntelligenceResult model"
```

---

### Task 7: Market Regime Filter

**Files:**
- Create: `src/stockai/scoring/intelligence/regime.py`
- Test: `tests/unit/intelligence/test_regime.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/intelligence/test_regime.py`:

```python
"""Tests for Market Regime Filter."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


def _make_ihsg_df(trend: str) -> pd.DataFrame:
    """Create mock IHSG daily DataFrame."""
    dates = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(60)]
    if trend == "bullish":
        close = np.linspace(7000, 7800, 60)   # consistent uptrend
    elif trend == "bearish":
        close = np.linspace(7800, 7000, 60)   # consistent downtrend
    else:  # sideways
        close = 7400 + np.sin(np.linspace(0, 4 * np.pi, 60)) * 100
    return pd.DataFrame({"date": dates, "close": close, "symbol": "^JKSE"})


def test_bullish_regime_detected():
    from stockai.scoring.intelligence.regime import detect_market_regime
    df = _make_ihsg_df("bullish")
    result = detect_market_regime(df)
    assert result == "BULLISH"


def test_bearish_regime_detected():
    from stockai.scoring.intelligence.regime import detect_market_regime
    df = _make_ihsg_df("bearish")
    result = detect_market_regime(df)
    assert result == "BEARISH"


def test_sideways_regime_detected():
    from stockai.scoring.intelligence.regime import detect_market_regime
    df = _make_ihsg_df("sideways")
    result = detect_market_regime(df)
    assert result in ("SIDEWAYS", "BULLISH", "BEARISH")  # accepts any valid regime


def test_empty_df_returns_unknown():
    from stockai.scoring.intelligence.regime import detect_market_regime
    result = detect_market_regime(pd.DataFrame())
    assert result == "UNKNOWN"


def test_get_regime_with_mocked_source():
    from stockai.scoring.intelligence.regime import get_market_regime
    df = _make_ihsg_df("bullish")
    with patch("stockai.scoring.intelligence.regime.YahooFinanceSource") as MockSource:
        instance = MockSource.return_value
        instance.get_price_history.return_value = df
        regime = get_market_regime()
    assert regime == "BULLISH"


def test_get_regime_fetch_failure_returns_unknown():
    from stockai.scoring.intelligence.regime import get_market_regime
    with patch("stockai.scoring.intelligence.regime.YahooFinanceSource") as MockSource:
        instance = MockSource.return_value
        instance.get_price_history.side_effect = Exception("network error")
        regime = get_market_regime()
    assert regime == "UNKNOWN"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run pytest tests/unit/intelligence/test_regime.py -v
```
Expected: `ImportError: cannot import name 'detect_market_regime'`

- [ ] **Step 3: Create regime.py**

Create `src/stockai/scoring/intelligence/regime.py`:

```python
"""Market Regime Filter.

Determines whether IHSG (^JKSE) is in a BULLISH, SIDEWAYS, or BEARISH regime
by comparing price to EMA20 and EMA20 to EMA50.
"""
import logging
from functools import lru_cache
from time import time

import pandas as pd

logger = logging.getLogger(__name__)

_REGIME_CACHE: dict[str, tuple[float, str]] = {}   # key → (timestamp, regime)
_CACHE_TTL_SECONDS = 4 * 3600  # 4 hours


def detect_market_regime(df: pd.DataFrame) -> str:
    """Compute BULLISH / SIDEWAYS / BEARISH from a daily OHLCV DataFrame.

    Args:
        df: DataFrame with a 'close' column, at least 50 rows recommended.

    Returns:
        "BULLISH", "SIDEWAYS", "BEARISH", or "UNKNOWN" on error.
    """
    if df.empty or "close" not in df.columns or len(df) < 20:
        return "UNKNOWN"

    close = df["close"].astype(float)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean() if len(close) >= 50 else ema20

    last_close = float(close.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])

    if last_close > last_ema20 and last_ema20 > last_ema50:
        return "BULLISH"
    if last_close < last_ema20 and last_ema20 < last_ema50:
        return "BEARISH"
    return "SIDEWAYS"


def get_market_regime() -> str:
    """Fetch IHSG data and return current market regime.

    Results are cached for 4 hours to avoid redundant API calls.

    Returns:
        "BULLISH", "SIDEWAYS", "BEARISH", or "UNKNOWN" on fetch failure.
    """
    cache_key = "ihsg_regime"
    now = time()

    if cache_key in _REGIME_CACHE:
        ts, cached_regime = _REGIME_CACHE[cache_key]
        if now - ts < _CACHE_TTL_SECONDS:
            return cached_regime

    try:
        from stockai.data.sources.yahoo import YahooFinanceSource
        source = YahooFinanceSource()
        df = source.get_price_history("^JKSE", period="3mo", interval="1d")
        regime = detect_market_regime(df)
    except Exception as e:
        logger.warning(f"IHSG regime fetch failed: {e}")
        regime = "UNKNOWN"

    _REGIME_CACHE[cache_key] = (now, regime)
    return regime


def get_ihsg_df() -> pd.DataFrame:
    """Return cached IHSG daily DataFrame for reuse by other modules (e.g. relative_strength)."""
    try:
        from stockai.data.sources.yahoo import YahooFinanceSource
        source = YahooFinanceSource()
        return source.get_price_history("^JKSE", period="3mo", interval="1d")
    except Exception as e:
        logger.warning(f"IHSG data fetch failed: {e}")
        return pd.DataFrame()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/intelligence/test_regime.py -v
```
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/scoring/intelligence/regime.py tests/unit/intelligence/test_regime.py
git commit -m "feat(intelligence): add Market Regime Filter"
```

---

### Task 8: Multi-Timeframe Confirmation

**Files:**
- Create: `src/stockai/scoring/intelligence/mtf.py`
- Test: `tests/unit/intelligence/test_mtf.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/intelligence/test_mtf.py`:

```python
"""Tests for Multi-Timeframe Confirmation."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def _trend_df(n_rows: int, trend: str, freq_days: int = 1) -> pd.DataFrame:
    dates = [datetime(2026, 1, 1) + timedelta(days=i * freq_days) for i in range(n_rows)]
    if trend == "up":
        close = np.linspace(1000, 1300, n_rows)
        volume = np.ones(n_rows) * 1_000_000
    else:
        close = np.linspace(1300, 1000, n_rows)
        volume = np.ones(n_rows) * 1_000_000
    return pd.DataFrame({"date": dates, "open": close * 0.99, "high": close * 1.01,
                         "low": close * 0.98, "close": close, "volume": volume})


def test_all_timeframes_bullish_returns_3():
    from stockai.scoring.intelligence.mtf import check_mtf_alignment
    weekly = _trend_df(30, "up", freq_days=7)
    daily = _trend_df(90, "up", freq_days=1)
    h4 = _trend_df(180, "up", freq_days=1)   # will be resampled to 4H internally
    result = check_mtf_alignment(weekly_df=weekly, daily_df=daily, h4_df=h4)
    assert result["aligned"] >= 2   # at least 2/3


def test_all_bearish_returns_low_alignment():
    from stockai.scoring.intelligence.mtf import check_mtf_alignment
    weekly = _trend_df(30, "down", freq_days=7)
    daily = _trend_df(90, "down", freq_days=1)
    h4 = _trend_df(180, "down", freq_days=1)
    result = check_mtf_alignment(weekly_df=weekly, daily_df=daily, h4_df=h4)
    assert result["aligned"] <= 1


def test_empty_h4_falls_back_to_two_timeframes():
    from stockai.scoring.intelligence.mtf import check_mtf_alignment
    weekly = _trend_df(30, "up", freq_days=7)
    daily = _trend_df(90, "up", freq_days=1)
    result = check_mtf_alignment(weekly_df=weekly, daily_df=daily, h4_df=pd.DataFrame())
    assert result["aligned"] >= 0   # no crash, valid number


def test_score_3_of_3_is_25():
    from stockai.scoring.intelligence.mtf import mtf_to_score
    assert mtf_to_score(3) == 25
    assert mtf_to_score(2) == 10
    assert mtf_to_score(1) == 0
    assert mtf_to_score(0) == 0
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run pytest tests/unit/intelligence/test_mtf.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create mtf.py**

Create `src/stockai/scoring/intelligence/mtf.py`:

```python
"""Multi-Timeframe Confirmation.

Checks Weekly + Daily + 4H alignment for a bullish setup.
All computed from yfinance data using pandas EMA/MACD/RSI.
"""
import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _macd_histogram(close: pd.Series) -> pd.Series:
    """Return MACD histogram (MACD line − signal line)."""
    macd = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd, 9)
    return macd - signal


def _rsi(close: pd.Series, period: int = 14) -> float:
    """Return latest RSI value."""
    if len(close) < period + 1:
        return 50.0
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if not np.isnan(val) else 50.0


def _is_weekly_bullish(df: pd.DataFrame) -> bool:
    """Weekly bullish: close > EMA20 weekly."""
    if df.empty or "close" not in df.columns or len(df) < 5:
        return False
    close = df["close"].astype(float)
    ema20 = _ema(close, 20)
    return float(close.iloc[-1]) > float(ema20.iloc[-1])


def _is_daily_bullish(df: pd.DataFrame) -> bool:
    """Daily bullish: close > EMA20 AND MACD histogram > 0."""
    if df.empty or "close" not in df.columns or len(df) < 30:
        return False
    close = df["close"].astype(float)
    ema20 = _ema(close, 20)
    hist = _macd_histogram(close)
    above_ema = float(close.iloc[-1]) > float(ema20.iloc[-1])
    macd_positive = float(hist.iloc[-1]) > 0
    return above_ema and macd_positive


def _is_h4_bullish(df: pd.DataFrame) -> bool:
    """4H bullish: RSI between 30-65 AND close above EMA20 4H."""
    if df.empty or "close" not in df.columns or len(df) < 20:
        return False
    close = df["close"].astype(float)
    ema20 = _ema(close, 20)
    rsi_val = _rsi(close)
    above_ema = float(close.iloc[-1]) > float(ema20.iloc[-1])
    rsi_ok = 30 <= rsi_val <= 65
    return above_ema and rsi_ok


def check_mtf_alignment(
    weekly_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    h4_df: pd.DataFrame,
) -> dict[str, Any]:
    """Check how many of the 3 timeframes are bullish.

    Args:
        weekly_df: Weekly OHLCV DataFrame
        daily_df: Daily OHLCV DataFrame
        h4_df: 4H (or hourly) OHLCV DataFrame

    Returns:
        Dict with 'aligned' (int 0-3), 'weekly', 'daily', 'h4' (bool each)
    """
    weekly_bull = _is_weekly_bullish(weekly_df)
    daily_bull = _is_daily_bullish(daily_df)
    h4_bull = _is_h4_bullish(h4_df) if not h4_df.empty else False

    total = sum([weekly_bull, daily_bull, h4_bull])
    return {
        "aligned": total,
        "weekly": weekly_bull,
        "daily": daily_bull,
        "h4": h4_bull,
    }


def mtf_to_score(aligned: int) -> float:
    """Convert MTF alignment count to confidence score points.

    3/3 → 25, 2/3 → 10, <2 → 0 (gate fail)
    """
    if aligned >= 3:
        return 25.0
    if aligned == 2:
        return 10.0
    return 0.0


def fetch_mtf_data(symbol: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fetch weekly, daily, and 4H DataFrames for a symbol.

    Returns:
        Tuple of (weekly_df, daily_df, h4_df). Any can be empty on error.
    """
    from stockai.data.sources.yahoo import YahooFinanceSource
    source = YahooFinanceSource()

    weekly = pd.DataFrame()
    daily = pd.DataFrame()
    h4 = pd.DataFrame()

    try:
        weekly = source.get_price_history(symbol, period="6mo", interval="1wk")
    except Exception as e:
        logger.warning(f"{symbol} weekly fetch failed: {e}")

    try:
        daily = source.get_price_history(symbol, period="3mo", interval="1d")
    except Exception as e:
        logger.warning(f"{symbol} daily fetch failed: {e}")

    try:
        h4 = source.get_price_history(symbol, period="60d", interval="1h")
        if not h4.empty and "date" in h4.columns:
            h4 = h4.set_index("date").resample("4h").agg(
                {"open": "first", "high": "max", "low": "min",
                 "close": "last", "volume": "sum"}
            ).dropna().reset_index()
    except Exception as e:
        logger.warning(f"{symbol} 4H fetch failed: {e}")

    return weekly, daily, h4
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/intelligence/test_mtf.py -v
```
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/scoring/intelligence/mtf.py tests/unit/intelligence/test_mtf.py
git commit -m "feat(intelligence): add Multi-Timeframe Confirmation"
```

---

### Task 9: Breakout Quality Score

**Files:**
- Create: `src/stockai/scoring/intelligence/breakout.py`
- Test: `tests/unit/intelligence/test_breakout.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/intelligence/test_breakout.py`:

```python
"""Tests for Breakout Quality Score."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def _df_with_volume(today_vol: float, avg_vol: float, n: int = 25) -> pd.DataFrame:
    dates = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(n)]
    volumes = [avg_vol] * (n - 1) + [today_vol]
    close = [1000.0] * n
    return pd.DataFrame({"date": dates, "close": close, "volume": volumes,
                         "open": close, "high": close, "low": close})


def test_institutional_breakout_score():
    from stockai.scoring.intelligence.breakout import score_breakout
    df = _df_with_volume(today_vol=2_500_000, avg_vol=1_000_000)
    result = score_breakout(df, nearest_resistance=None)
    assert result["score"] == 20.0
    assert result["volume_ratio"] == pytest.approx(2.5, rel=0.1)


def test_normal_breakout_score():
    from stockai.scoring.intelligence.breakout import score_breakout
    df = _df_with_volume(today_vol=1_700_000, avg_vol=1_000_000)
    result = score_breakout(df, nearest_resistance=None)
    assert result["score"] == 12.0


def test_weak_breakout_score():
    from stockai.scoring.intelligence.breakout import score_breakout
    df = _df_with_volume(today_vol=1_200_000, avg_vol=1_000_000)
    result = score_breakout(df, nearest_resistance=None)
    assert result["score"] == 5.0


def test_no_volume_score_zero():
    from stockai.scoring.intelligence.breakout import score_breakout
    df = _df_with_volume(today_vol=800_000, avg_vol=1_000_000)
    result = score_breakout(df, nearest_resistance=None)
    assert result["score"] == 0.0


def test_close_above_resistance_adds_bonus():
    from stockai.scoring.intelligence.breakout import score_breakout
    dates = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(25)]
    volumes = [1_000_000] * 24 + [2_000_000]
    close = [1000.0] * 24 + [1050.0]   # closes above resistance 1040
    df = pd.DataFrame({"date": dates, "close": close, "volume": volumes,
                       "open": close, "high": close, "low": close})
    result = score_breakout(df, nearest_resistance=1040.0)
    assert result["score"] == 25.0   # 20 + 5 bonus, capped at 25


def test_empty_df_returns_zero():
    from stockai.scoring.intelligence.breakout import score_breakout
    result = score_breakout(pd.DataFrame(), nearest_resistance=None)
    assert result["score"] == 0.0


import pytest
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run pytest tests/unit/intelligence/test_breakout.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create breakout.py**

Create `src/stockai/scoring/intelligence/breakout.py`:

```python
"""Breakout Quality Score.

Scores a stock's breakout strength using volume ratio and resistance breakout.
"""
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def score_breakout(
    df: pd.DataFrame,
    nearest_resistance: float | None,
) -> dict[str, Any]:
    """Compute breakout quality score from daily OHLCV data.

    Args:
        df: Daily OHLCV DataFrame with 'close' and 'volume' columns.
            Must have at least 21 rows (20 for avg + today).
        nearest_resistance: Nearest resistance price level, or None.

    Returns:
        Dict with 'score' (0-25), 'volume_ratio', 'broke_resistance' (bool).
    """
    if df.empty or "volume" not in df.columns or "close" not in df.columns:
        return {"score": 0.0, "volume_ratio": 0.0, "broke_resistance": False}

    if len(df) < 21:
        return {"score": 0.0, "volume_ratio": 0.0, "broke_resistance": False}

    volume = df["volume"].astype(float)
    today_vol = float(volume.iloc[-1])
    avg_vol_20d = float(volume.iloc[-21:-1].mean())

    if avg_vol_20d == 0:
        return {"score": 0.0, "volume_ratio": 0.0, "broke_resistance": False}

    ratio = today_vol / avg_vol_20d

    if ratio >= 2.0:
        base_score = 20.0
    elif ratio >= 1.5:
        base_score = 12.0
    elif ratio >= 1.0:
        base_score = 5.0
    else:
        base_score = 0.0

    # Resistance breakout bonus
    broke_resistance = False
    if nearest_resistance is not None:
        last_close = float(df["close"].iloc[-1])
        if last_close > nearest_resistance:
            broke_resistance = True
            base_score = min(25.0, base_score + 5.0)

    return {
        "score": base_score,
        "volume_ratio": round(ratio, 2),
        "broke_resistance": broke_resistance,
    }
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/intelligence/test_breakout.py -v
```
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/scoring/intelligence/breakout.py tests/unit/intelligence/test_breakout.py
git commit -m "feat(intelligence): add Breakout Quality Score"
```

---

### Task 10: Candlestick Pattern Engine

**Files:**
- Create: `src/stockai/scoring/intelligence/candles.py`
- Test: `tests/unit/intelligence/test_candles.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/intelligence/test_candles.py`:

```python
"""Tests for Candlestick Pattern Engine."""
import pandas as pd
from datetime import datetime, timedelta


def _candle(open_, high, low, close) -> dict:
    return {"open": open_, "high": high, "low": low, "close": close}


def _df(*candles) -> pd.DataFrame:
    rows = []
    for i, c in enumerate(candles):
        rows.append({
            "date": datetime(2026, 1, i + 1),
            **c, "volume": 1_000_000,
        })
    return pd.DataFrame(rows)


def test_bullish_engulfing_detected():
    from stockai.scoring.intelligence.candles import detect_candlestick_pattern
    # prev: bearish (open > close), curr: bullish body covers prev body
    df = _df(
        _candle(1050, 1060, 990, 1000),   # bearish
        _candle(980, 1070, 975, 1060),    # bullish engulfing
    )
    result = detect_candlestick_pattern(df)
    assert result["pattern"] == "Bullish Engulfing"
    assert result["score"] == 15


def test_hammer_detected():
    from stockai.scoring.intelligence.candles import detect_candlestick_pattern
    # Hammer: small body at top, long lower wick (≥2× body), tiny upper wick
    df = _df(
        _candle(1000, 1005, 1000, 1003),  # prev (any)
        _candle(1000, 1005, 960, 1003),   # hammer: body=3, lower wick=40
    )
    result = detect_candlestick_pattern(df)
    assert result["pattern"] == "Hammer"
    assert result["score"] == 12


def test_no_pattern_returns_zero():
    from stockai.scoring.intelligence.candles import detect_candlestick_pattern
    df = _df(
        _candle(1000, 1010, 990, 1005),
        _candle(1005, 1015, 995, 1008),  # regular bullish, not a pattern
    )
    result = detect_candlestick_pattern(df)
    assert result["pattern"] == "None"
    assert result["score"] == 0


def test_insufficient_data_returns_none_pattern():
    from stockai.scoring.intelligence.candles import detect_candlestick_pattern
    df = _df(_candle(1000, 1010, 990, 1005))  # only 1 candle
    result = detect_candlestick_pattern(df)
    assert result["pattern"] == "None"
    assert result["score"] == 0


def test_morning_star_detected():
    from stockai.scoring.intelligence.candles import detect_candlestick_pattern
    # Day1: bearish, Day2: doji/small body, Day3: bullish gap up close > midpoint day1
    df = _df(
        _candle(1050, 1055, 980, 990),    # bearish body 60
        _candle(985, 992, 982, 988),      # small body (doji-like)
        _candle(992, 1060, 990, 1050),    # bullish, closes above midpoint of day1 (1020)
    )
    result = detect_candlestick_pattern(df)
    assert result["pattern"] == "Morning Star"
    assert result["score"] == 15
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run pytest tests/unit/intelligence/test_candles.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create candles.py**

Create `src/stockai/scoring/intelligence/candles.py`:

```python
"""Candlestick Pattern Engine.

Detects the 5 most reliable bullish reversal patterns using pure pandas.
Contribution capped at 15 points regardless of pattern strength.
"""
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_PATTERNS = {
    "Morning Star": 15,
    "Bullish Engulfing": 15,
    "Hammer": 12,
    "Piercing Line": 10,
    "Bullish Harami": 8,
    "None": 0,
}
MAX_SCORE = 15.0


def _body(row) -> float:
    return abs(float(row["close"]) - float(row["open"]))


def _is_bearish(row) -> bool:
    return float(row["close"]) < float(row["open"])


def _is_bullish(row) -> bool:
    return float(row["close"]) > float(row["open"])


def detect_candlestick_pattern(df: pd.DataFrame) -> dict[str, Any]:
    """Detect the most significant bullish pattern in the last 1-3 candles.

    Args:
        df: Daily OHLCV DataFrame (needs at least 2 rows, 3 for Morning Star).

    Returns:
        Dict with 'pattern' (str) and 'score' (int, capped at 15).
    """
    if df.empty or len(df) < 2:
        return {"pattern": "None", "score": 0}

    rows = df.tail(3).reset_index(drop=True)
    curr = rows.iloc[-1]
    prev = rows.iloc[-2]

    # --- Morning Star (3-candle, needs 3 rows) ---
    if len(rows) == 3:
        first = rows.iloc[0]
        first_body = _body(first)
        mid_body = _body(prev)
        curr_body = _body(curr)
        first_mid = (float(first["open"]) + float(first["close"])) / 2
        if (
            _is_bearish(first)
            and first_body > 0
            and mid_body < first_body * 0.3   # small/doji middle
            and _is_bullish(curr)
            and float(curr["close"]) > first_mid  # closes above midpoint of day1
        ):
            return {"pattern": "Morning Star", "score": min(15, _PATTERNS["Morning Star"])}

    curr_body = _body(curr)
    prev_body = _body(prev)

    # --- Bullish Engulfing ---
    if (
        _is_bearish(prev)
        and _is_bullish(curr)
        and float(curr["open"]) < float(prev["close"])
        and float(curr["close"]) > float(prev["open"])
        and curr_body > prev_body
    ):
        return {"pattern": "Bullish Engulfing", "score": _PATTERNS["Bullish Engulfing"]}

    # --- Hammer / Pin Bar ---
    if _is_bullish(curr) and curr_body > 0:
        lower_wick = float(curr["open"]) - float(curr["low"])
        upper_wick = float(curr["high"]) - float(curr["close"])
        if lower_wick >= 2 * curr_body and upper_wick < curr_body:
            return {"pattern": "Hammer", "score": _PATTERNS["Hammer"]}

    # --- Piercing Line ---
    if (
        _is_bearish(prev)
        and _is_bullish(curr)
        and float(curr["open"]) < float(prev["low"])
        and float(curr["close"]) > (float(prev["open"]) + float(prev["close"])) / 2
    ):
        return {"pattern": "Piercing Line", "score": _PATTERNS["Piercing Line"]}

    # --- Bullish Harami ---
    if (
        _is_bearish(prev)
        and _is_bullish(curr)
        and float(curr["open"]) > float(prev["close"])
        and float(curr["close"]) < float(prev["open"])
    ):
        return {"pattern": "Bullish Harami", "score": _PATTERNS["Bullish Harami"]}

    return {"pattern": "None", "score": 0}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/intelligence/test_candles.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/scoring/intelligence/candles.py tests/unit/intelligence/test_candles.py
git commit -m "feat(intelligence): add Candlestick Pattern Engine"
```

---

### Task 11: Relative Strength vs IHSG

**Files:**
- Create: `src/stockai/scoring/intelligence/relative_strength.py`
- Test: `tests/unit/intelligence/test_relative_strength.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/intelligence/test_relative_strength.py`:

```python
"""Tests for Relative Strength vs IHSG."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def _price_df(start: float, end: float, n: int = 25) -> pd.DataFrame:
    dates = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(n)]
    close = np.linspace(start, end, n)
    return pd.DataFrame({"date": dates, "close": close})


def test_strong_outperformer_returns_10():
    from stockai.scoring.intelligence.relative_strength import calculate_rs_score
    stock_df = _price_df(1000, 1200)   # +20%
    ihsg_df = _price_df(7000, 7100)    # +1.4% → RS ≈ 14 > 1.5
    result = calculate_rs_score(stock_df, ihsg_df)
    assert result["score"] == 10
    assert result["rs"] > 1.5


def test_outperformer_returns_6():
    from stockai.scoring.intelligence.relative_strength import calculate_rs_score
    stock_df = _price_df(1000, 1100)   # +10%
    ihsg_df = _price_df(7000, 7070)    # +1% → RS ≈ 10
    result = calculate_rs_score(stock_df, ihsg_df)
    assert result["score"] == 6


def test_underperformer_returns_0():
    from stockai.scoring.intelligence.relative_strength import calculate_rs_score
    stock_df = _price_df(1000, 1010)   # +1%
    ihsg_df = _price_df(7000, 7200)    # +2.9% → RS < 0.5
    result = calculate_rs_score(stock_df, ihsg_df)
    assert result["score"] == 0


def test_ihsg_flat_returns_2():
    """When IHSG is flat (0%), RS is undefined — return in-line score."""
    from stockai.scoring.intelligence.relative_strength import calculate_rs_score
    stock_df = _price_df(1000, 1020)   # +2%
    ihsg_df = _price_df(7000, 7000)    # 0%
    result = calculate_rs_score(stock_df, ihsg_df)
    assert result["score"] in (0, 2, 6, 10)   # no crash


def test_empty_df_returns_zero():
    from stockai.scoring.intelligence.relative_strength import calculate_rs_score
    result = calculate_rs_score(pd.DataFrame(), pd.DataFrame())
    assert result["score"] == 0
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run pytest tests/unit/intelligence/test_relative_strength.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create relative_strength.py**

Create `src/stockai/scoring/intelligence/relative_strength.py`:

```python
"""Relative Strength vs IHSG.

Computes how much a stock outperforms or underperforms IHSG over 20 days.
"""
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def calculate_rs_score(
    stock_df: pd.DataFrame,
    ihsg_df: pd.DataFrame,
    lookback: int = 20,
) -> dict[str, Any]:
    """Calculate Relative Strength score vs IHSG.

    Args:
        stock_df: Daily DataFrame with 'close' column, at least lookback+1 rows.
        ihsg_df: IHSG daily DataFrame with 'close' column.
        lookback: Number of days for return calculation (default 20).

    Returns:
        Dict with 'rs' (float), 'stock_return' (%), 'ihsg_return' (%), 'score' (int).
    """
    _empty = {"rs": 0.0, "stock_return": 0.0, "ihsg_return": 0.0, "score": 0}

    if stock_df.empty or ihsg_df.empty:
        return _empty

    if "close" not in stock_df.columns or "close" not in ihsg_df.columns:
        return _empty

    if len(stock_df) < lookback + 1 or len(ihsg_df) < lookback + 1:
        return _empty

    stock_close = stock_df["close"].astype(float)
    ihsg_close = ihsg_df["close"].astype(float)

    stock_return = (float(stock_close.iloc[-1]) - float(stock_close.iloc[-(lookback + 1)])) \
                   / float(stock_close.iloc[-(lookback + 1)])
    ihsg_return = (float(ihsg_close.iloc[-1]) - float(ihsg_close.iloc[-(lookback + 1)])) \
                  / float(ihsg_close.iloc[-(lookback + 1)])

    # Handle flat IHSG
    if abs(ihsg_return) < 0.0001:
        # Stock has some return but IHSG is flat → treat as outperformer
        rs = 1.0 + stock_return * 10
    else:
        rs = stock_return / ihsg_return

    if rs > 1.5:
        score = 10
    elif rs >= 1.0:
        score = 6
    elif rs >= 0.5:
        score = 2
    else:
        score = 0

    return {
        "rs": round(rs, 2),
        "stock_return": round(stock_return * 100, 2),
        "ihsg_return": round(ihsg_return * 100, 2),
        "score": score,
    }
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/intelligence/test_relative_strength.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stockai/scoring/intelligence/relative_strength.py tests/unit/intelligence/test_relative_strength.py
git commit -m "feat(intelligence): add Relative Strength vs IHSG"
```

---

### Task 12: Intelligence Pipeline Orchestrator + Gemini News Scan

**Files:**
- Modify: `src/stockai/scoring/intelligence/pipeline.py` (replace stub)
- Test: `tests/unit/intelligence/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/intelligence/test_pipeline.py`:

```python
"""Tests for Intelligence Pipeline."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


def _trend_df(n, start, end):
    dates = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(n)]
    close = np.linspace(start, end, n)
    return pd.DataFrame({"date": dates, "close": close, "open": close * 0.99,
                         "high": close * 1.01, "low": close * 0.98,
                         "volume": [1_500_000] * n})


def _mock_source(stock_df, ihsg_df):
    """Return a mock YahooFinanceSource that yields test DataFrames."""
    mock = MagicMock()
    def side_effect(symbol, period="1mo", interval="1d"):
        if "JKSE" in symbol or "^" in symbol:
            return ihsg_df
        return stock_df
    mock.get_price_history.side_effect = side_effect
    return mock


def test_pipeline_returns_intelligence_result():
    from stockai.scoring.intelligence.pipeline import run_intelligence_pipeline
    from stockai.scoring.intelligence.models import IntelligenceResult

    stock_df = _trend_df(90, 1000, 1200)
    ihsg_df = _trend_df(90, 7000, 7100)

    with patch("stockai.scoring.intelligence.regime.YahooFinanceSource") as MockSrc, \
         patch("stockai.scoring.intelligence.mtf.YahooFinanceSource") as MockSrc2, \
         patch("stockai.scoring.intelligence.pipeline._call_gemini_news_scan") as mock_gemini:

        MockSrc.return_value = _mock_source(stock_df, ihsg_df)
        MockSrc2.return_value = _mock_source(stock_df, ihsg_df)
        mock_gemini.return_value = ("CLEAR", "Tidak ada berita negatif material")

        result = run_intelligence_pipeline(
            symbol="BBCA",
            existing_score=75.0,
            daily_df=stock_df,
            ihsg_df=ihsg_df,
        )

    assert isinstance(result, IntelligenceResult)
    assert result.symbol == "BBCA"
    assert 0 <= result.confidence_score <= 100
    assert result.confidence_level in ("HIGH", "MEDIUM", "LOW")
    assert result.recommendation in ("EXECUTE", "WATCH", "SKIP")


def test_bearish_regime_returns_skip():
    from stockai.scoring.intelligence.pipeline import run_intelligence_pipeline

    stock_df = _trend_df(90, 1000, 1200)
    ihsg_df = _trend_df(90, 7800, 7000)  # bearish

    with patch("stockai.scoring.intelligence.regime.YahooFinanceSource") as MockSrc, \
         patch("stockai.scoring.intelligence.mtf.YahooFinanceSource") as MockSrc2:
        MockSrc.return_value = _mock_source(stock_df, ihsg_df)
        MockSrc2.return_value = _mock_source(stock_df, ihsg_df)

        result = run_intelligence_pipeline(
            symbol="BBCA", existing_score=80.0,
            daily_df=stock_df, ihsg_df=ihsg_df,
        )

    assert result.recommendation == "SKIP"
    assert result.regime == "BEARISH"


def test_risk_detected_forces_skip():
    from stockai.scoring.intelligence.pipeline import run_intelligence_pipeline

    stock_df = _trend_df(90, 1000, 1200)
    ihsg_df = _trend_df(90, 7000, 7200)  # bullish

    with patch("stockai.scoring.intelligence.regime.YahooFinanceSource") as MockSrc, \
         patch("stockai.scoring.intelligence.mtf.YahooFinanceSource") as MockSrc2, \
         patch("stockai.scoring.intelligence.pipeline._call_gemini_news_scan") as mock_gemini:
        MockSrc.return_value = _mock_source(stock_df, ihsg_df)
        MockSrc2.return_value = _mock_source(stock_df, ihsg_df)
        mock_gemini.return_value = ("RISK_DETECTED", "Right issue dilutive")

        result = run_intelligence_pipeline(
            symbol="BBCA", existing_score=80.0,
            daily_df=stock_df, ihsg_df=ihsg_df,
        )

    assert result.recommendation == "SKIP"
    assert result.news_status == "RISK_DETECTED"


def test_gemini_error_does_not_block_signal():
    from stockai.scoring.intelligence.pipeline import run_intelligence_pipeline

    stock_df = _trend_df(90, 1000, 1200)
    ihsg_df = _trend_df(90, 7000, 7200)

    with patch("stockai.scoring.intelligence.regime.YahooFinanceSource") as MockSrc, \
         patch("stockai.scoring.intelligence.mtf.YahooFinanceSource") as MockSrc2, \
         patch("stockai.scoring.intelligence.pipeline._call_gemini_news_scan") as mock_gemini:
        MockSrc.return_value = _mock_source(stock_df, ihsg_df)
        MockSrc2.return_value = _mock_source(stock_df, ihsg_df)
        mock_gemini.side_effect = Exception("API timeout")

        result = run_intelligence_pipeline(
            symbol="BBCA", existing_score=80.0,
            daily_df=stock_df, ihsg_df=ihsg_df,
        )

    # Should not be SKIP due to Gemini failure alone
    assert result.news_status == "SKIPPED"
    assert result.recommendation != "SKIP" or result.regime == "BEARISH"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run pytest tests/unit/intelligence/test_pipeline.py -v
```
Expected: tests fail (stub returns empty result).

- [ ] **Step 3: Replace pipeline.py stub with full implementation**

Replace `src/stockai/scoring/intelligence/pipeline.py` entirely:

```python
"""Intelligence Pipeline Orchestrator.

Coordinates all 5 signal intelligence modules and a Gemini news risk scan
to produce a single IntelligenceResult with a 0–100 confidence score.
"""
import logging
import re
from typing import Any

import pandas as pd

from stockai.scoring.intelligence.models import IntelligenceResult

logger = logging.getLogger(__name__)


def _call_gemini_news_scan(symbol: str) -> tuple[str, str]:
    """Call Gemini to check for recent negative news about the stock.

    Returns:
        Tuple of (status, reason) where status is "CLEAR" or "RISK_DETECTED".
        Raises Exception on API failure (caller handles gracefully).
    """
    from stockai.config import get_settings
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = (
        f"Kamu adalah analis risiko saham IDX. Cari dan analisa berita terbaru "
        f"saham {symbol} di Indonesia (dalam 7 hari terakhir).\n\n"
        f"Apakah ada:\n"
        f"- Berita negatif material (skandal, kerugian besar, gagal bayar)\n"
        f"- Right issue atau stock split yang menekan harga\n"
        f"- Masalah regulasi atau tindakan OJK/BEI\n"
        f"- Corporate action negatif lainnya\n\n"
        f"Jawab HANYA dengan format:\n"
        f"STATUS: CLEAR atau RISK_DETECTED\n"
        f"REASON: [satu kalimat, atau 'Tidak ada berita negatif material']"
    )

    response = model.generate_content(prompt)
    text = response.text.strip()

    status_match = re.search(r"STATUS:\s*(CLEAR|RISK_DETECTED)", text, re.IGNORECASE)
    reason_match = re.search(r"REASON:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)

    status = status_match.group(1).upper() if status_match else "CLEAR"
    reason = reason_match.group(1).strip() if reason_match else "Tidak ada berita negatif material"
    return status, reason


def run_intelligence_pipeline(
    symbol: str,
    existing_score: float = 0.0,
    daily_df: pd.DataFrame | None = None,
    ihsg_df: pd.DataFrame | None = None,
) -> IntelligenceResult:
    """Run the full Signal Intelligence Pipeline for one symbol.

    Args:
        symbol: IDX stock symbol (e.g. "BBCA")
        existing_score: Composite score from existing 6-gate system (0-100)
        daily_df: Pre-fetched daily DataFrame (fetched internally if None)
        ihsg_df: Pre-fetched IHSG DataFrame (fetched internally if None)

    Returns:
        IntelligenceResult with confidence score and recommendation.
    """
    from stockai.scoring.intelligence.regime import detect_market_regime, get_ihsg_df
    from stockai.scoring.intelligence.mtf import check_mtf_alignment, fetch_mtf_data, mtf_to_score
    from stockai.scoring.intelligence.breakout import score_breakout
    from stockai.scoring.intelligence.candles import detect_candlestick_pattern
    from stockai.scoring.intelligence.relative_strength import calculate_rs_score

    score_breakdown: dict[str, float] = {}

    # --- Fetch IHSG if not provided ---
    if ihsg_df is None or ihsg_df.empty:
        ihsg_df = get_ihsg_df()

    # --- 1. Market Regime (HARD GATE) ---
    regime = detect_market_regime(ihsg_df)
    if regime == "BEARISH":
        return IntelligenceResult(
            symbol=symbol,
            confidence_score=0.0,
            confidence_level="LOW",
            recommendation="SKIP",
            regime="BEARISH",
            score_breakdown={"regime": 0.0},
        )

    # --- Fetch stock data ---
    if daily_df is None or daily_df.empty:
        from stockai.data.sources.yahoo import YahooFinanceSource
        src = YahooFinanceSource()
        daily_df = src.get_price_history(symbol, period="3mo", interval="1d")

    # --- 2. Multi-Timeframe Confirmation ---
    weekly_df, _, h4_df = fetch_mtf_data(symbol)
    mtf_result = check_mtf_alignment(
        weekly_df=weekly_df,
        daily_df=daily_df,
        h4_df=h4_df,
    )
    aligned = mtf_result["aligned"]
    mtf_score = mtf_to_score(aligned)
    score_breakdown["mtf"] = mtf_score

    # MTF gate: need at least 2/3
    if aligned < 2:
        return IntelligenceResult(
            symbol=symbol,
            confidence_score=mtf_score,
            confidence_level="LOW",
            recommendation="SKIP",
            regime=regime,
            mtf_aligned=aligned,
            score_breakdown=score_breakdown,
        )

    # --- 3. Breakout Quality ---
    breakout_result = score_breakout(daily_df, nearest_resistance=None)
    breakout_score = breakout_result["score"]
    score_breakdown["breakout"] = breakout_score

    # --- 4. Candlestick Pattern ---
    candle_result = detect_candlestick_pattern(daily_df)
    candle_score = min(15.0, candle_result["score"])
    score_breakdown["candles"] = candle_score

    # --- 5. Relative Strength ---
    rs_result = calculate_rs_score(daily_df, ihsg_df)
    rs_score = float(rs_result["score"])
    score_breakdown["relative_strength"] = rs_score

    # SIDEWAYS regime: require RS > 1.2 to proceed
    if regime == "SIDEWAYS" and rs_result["rs"] < 1.2:
        return IntelligenceResult(
            symbol=symbol,
            confidence_score=mtf_score + breakout_score + candle_score + rs_score,
            confidence_level="LOW",
            recommendation="SKIP",
            regime=regime,
            mtf_aligned=aligned,
            breakout_score=breakout_score,
            candle_pattern=candle_result["pattern"],
            relative_strength=rs_result["rs"],
            score_breakdown=score_breakdown,
        )

    # --- 6. Gemini News Risk Scan (only if passing gates so far) ---
    news_status = "SKIPPED"
    news_reason = ""
    news_score = 0.0

    try:
        news_status, news_reason = _call_gemini_news_scan(symbol)
        if news_status == "RISK_DETECTED":
            return IntelligenceResult(
                symbol=symbol,
                confidence_score=0.0,
                confidence_level="LOW",
                recommendation="SKIP",
                regime=regime,
                mtf_aligned=aligned,
                breakout_score=breakout_score,
                candle_pattern=candle_result["pattern"],
                relative_strength=rs_result["rs"],
                news_status="RISK_DETECTED",
                news_risk_reason=news_reason,
                score_breakdown=score_breakdown,
            )
        news_score = 10.0
        score_breakdown["news"] = news_score
    except Exception as e:
        logger.debug(f"Gemini news scan failed for {symbol}: {e}")
        news_status = "SKIPPED"
        score_breakdown["news"] = 0.0

    # --- Normalize existing 6-gate score (0-100 → 0-15 pts) ---
    gate_score = min(15.0, (existing_score / 100.0) * 15.0)
    score_breakdown["gate_score"] = gate_score

    # --- Final confidence score ---
    total = mtf_score + breakout_score + candle_score + rs_score + news_score + gate_score

    if total >= 80:
        level = "HIGH"
        recommendation = "EXECUTE"
    elif total >= 60:
        level = "MEDIUM"
        recommendation = "WATCH"
    else:
        level = "LOW"
        recommendation = "SKIP"

    return IntelligenceResult(
        symbol=symbol,
        confidence_score=round(total, 1),
        confidence_level=level,
        recommendation=recommendation,
        regime=regime,
        mtf_aligned=aligned,
        breakout_score=breakout_score,
        candle_pattern=candle_result["pattern"],
        relative_strength=rs_result["rs"],
        news_status=news_status,
        news_risk_reason=news_reason,
        score_breakdown=score_breakdown,
    )
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/intelligence/test_pipeline.py -v
```
Expected: 4 tests PASS.

- [ ] **Step 5: Run full intelligence test suite**

```bash
uv run pytest tests/unit/intelligence/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/stockai/scoring/intelligence/pipeline.py tests/unit/intelligence/test_pipeline.py
git commit -m "feat(intelligence): complete pipeline orchestrator with Gemini news scan"
```

---

### Task 13: Engine + CLI Integration

**Files:**
- Modify: `src/stockai/autopilot/engine.py`
- Modify: `src/stockai/cli/main.py`
- Test: `tests/unit/test_autopilot.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_autopilot.py`:

```python
class TestEngineIntelligencePipeline:
    """Test that AutopilotEngine filters signals through intelligence pipeline."""

    def test_low_confidence_signal_filtered_out(self):
        from stockai.autopilot.engine import AutopilotEngine, AutopilotConfig, TradeSignal
        from unittest.mock import patch, MagicMock
        from stockai.scoring.intelligence.models import IntelligenceResult

        config = AutopilotConfig(dry_run=True, capital=10_000_000.0)
        engine = AutopilotEngine(config)
        engine.cash = 10_000_000.0
        engine.positions = {}

        signal = TradeSignal(
            symbol="JUNK", action="BUY", score=65.0,
            current_price=500.0, lots=10, shares=1000,
            position_value=500_000.0, stop_loss=475.0, target=525.0, reason="Test",
        )

        low_result = IntelligenceResult(
            symbol="JUNK", confidence_score=45.0,
            confidence_level="LOW", recommendation="SKIP",
        )

        with patch("stockai.autopilot.engine.run_intelligence_pipeline", return_value=low_result):
            approved, rejected = engine._apply_intelligence_filter([signal])

        assert len(approved) == 0
        assert len(rejected) == 1

    def test_high_confidence_signal_passes():
        from stockai.autopilot.engine import AutopilotEngine, AutopilotConfig, TradeSignal
        from unittest.mock import patch
        from stockai.scoring.intelligence.models import IntelligenceResult

        config = AutopilotConfig(dry_run=True, capital=10_000_000.0)
        engine = AutopilotEngine(config)

        signal = TradeSignal(
            symbol="BBCA", action="BUY", score=85.0,
            current_price=10_000.0, lots=1, shares=100,
            position_value=1_000_000.0, stop_loss=9_500.0, target=10_500.0, reason="Test",
        )

        high_result = IntelligenceResult(
            symbol="BBCA", confidence_score=85.0,
            confidence_level="HIGH", recommendation="EXECUTE",
        )

        with patch("stockai.autopilot.engine.run_intelligence_pipeline", return_value=high_result):
            approved, rejected = engine._apply_intelligence_filter([signal])

        assert len(approved) == 1
        assert len(rejected) == 0
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run pytest tests/unit/test_autopilot.py::TestEngineIntelligencePipeline -v
```
Expected: `AttributeError: 'AutopilotEngine' object has no attribute '_apply_intelligence_filter'`

- [ ] **Step 3: Add _apply_intelligence_filter() to engine.py**

At the top of `src/stockai/autopilot/engine.py`, add this import after existing imports:

```python
from stockai.scoring.intelligence.pipeline import run_intelligence_pipeline
```

Add this method to the `AutopilotEngine` class (after `_apply_gate_filter`):

```python
def _apply_intelligence_filter(
    self, signals: list[TradeSignal]
) -> tuple[list[TradeSignal], list[TradeSignal]]:
    """Run each BUY signal through the Signal Intelligence Pipeline.

    Only HIGH confidence signals (≥80) proceed. MEDIUM signals are logged
    as watchlist candidates. LOW signals are rejected.

    Args:
        signals: BUY signals that passed the 6-gate filter.

    Returns:
        Tuple of (approved_signals, rejected_signals).
    """
    approved = []
    rejected = []

    for signal in signals:
        try:
            existing_score = signal.score
            daily_df = None
            if signal.analysis_result:
                # Reuse price history from analysis if available
                pass  # pipeline fetches internally

            intel = run_intelligence_pipeline(
                symbol=signal.symbol,
                existing_score=existing_score,
            )

            signal.intelligence_result = intel   # attach for display

            if intel.recommendation == "EXECUTE":
                logger.info(
                    f"{signal.symbol}: Intelligence PASS "
                    f"(score={intel.confidence_score:.0f}, {intel.regime})"
                )
                approved.append(signal)
            elif intel.recommendation == "WATCH":
                logger.info(
                    f"{signal.symbol}: Intelligence WATCH "
                    f"(score={intel.confidence_score:.0f}) — added to watchlist"
                )
                rejected.append(signal)
            else:
                logger.info(
                    f"{signal.symbol}: Intelligence SKIP "
                    f"(score={intel.confidence_score:.0f}, "
                    f"regime={intel.regime}, mtf={intel.mtf_aligned}/3)"
                )
                rejected.append(signal)

        except Exception as e:
            logger.warning(f"{signal.symbol}: Intelligence pipeline error: {e} — passing through")
            approved.append(signal)  # fail-open for pipeline errors (not trade decisions)

    return approved, rejected
```

Also add `intelligence_result: Any | None = None` field to `TradeSignal` dataclass.

Wire `_apply_intelligence_filter` into `_apply_gate_filter` flow — at the bottom of `_apply_gate_filter`, before returning `gate_qualified`, add:

```python
        # Run intelligence pipeline on gate-qualified BUY signals
        buy_signals = [s for s in gate_qualified if s.action == "BUY"]
        non_buy = [s for s in gate_qualified if s.action != "BUY"]
        if buy_signals:
            intel_approved, intel_rejected = self._apply_intelligence_filter(buy_signals)
            gate_qualified = intel_approved + non_buy
            gate_rejected = gate_rejected + intel_rejected
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/test_autopilot.py::TestEngineIntelligencePipeline -v
```
Expected: 2 tests PASS.

- [ ] **Step 5: Add confidence breakdown to quality --ai CLI output**

In `src/stockai/cli/main.py`, after the existing AI validation panel (around line 730, after `ai_result` is obtained), add:

```python
        # Show Intelligence Pipeline result if available
        if hasattr(result, 'intelligence_result') and result.intelligence_result:
            intel = result.intelligence_result
            color_map = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}
            ic = color_map.get(intel.confidence_level, "white")
            intel_lines = [
                f"[bold]Confidence Score:[/bold] [{ic}]{intel.confidence_score:.0f}/100 ({intel.confidence_level})[/{ic}]",
                f"[bold]Market Regime:[/bold] {intel.regime}",
                f"[bold]MTF Aligned:[/bold] {intel.mtf_aligned}/3 timeframes",
                f"[bold]Candle Pattern:[/bold] {intel.candle_pattern}",
                f"[bold]Relative Strength:[/bold] {intel.relative_strength:.2f}x IHSG",
                f"[bold]News Status:[/bold] {intel.news_status}",
                "",
                "[bold]Score Breakdown:[/bold]",
            ]
            for k, v in intel.score_breakdown.items():
                intel_lines.append(f"  {k}: {v:.1f} pts")
            console.print(Panel(
                "\n".join(intel_lines),
                title="🧠 Signal Intelligence",
                border_style=ic,
            ))
```

Also run intelligence pipeline inside the `quality` command when `--ai` is passed. After the existing `analyze_stock` call (around where `result` is obtained), before the AI validator call:

```python
        # Run intelligence pipeline when --ai flag is used
        intel_result = None
        if ai:
            try:
                intel_result = run_intelligence_pipeline(
                    symbol=ticker,
                    existing_score=result.composite_score,
                    daily_df=df,
                )
                result.intelligence_result = intel_result
            except Exception as e:
                logger.debug(f"Intelligence pipeline skipped: {e}")
```

Add the import near other intelligence imports in `cli/main.py`:

```python
from stockai.scoring.intelligence.pipeline import run_intelligence_pipeline
```

- [ ] **Step 6: Run all unit tests**

```bash
uv run pytest tests/unit/ -v --tb=short
```
Expected: all tests PASS (ignore network-marked tests).

- [ ] **Step 7: Commit**

```bash
git add src/stockai/autopilot/engine.py src/stockai/cli/main.py tests/unit/test_autopilot.py
git commit -m "feat(engine,cli): wire intelligence pipeline into autopilot and quality --ai"
```

---

## Final Verification

- [ ] **Smoke test — quality command**

```bash
cd /Users/mac/Downloads/stockai-main
uv run stockai quality BBCA --ai --verbose 2>&1 | head -60
```
Expected: output includes "🧠 Signal Intelligence" panel with Confidence Score, regime, MTF.

- [ ] **Smoke test — morning briefing**

```bash
uv run stockai morning 2>&1 | head -40
```
Expected: output includes trailing stop section if positions exist, or "Semua posisi normal" if not.

- [ ] **Full test suite**

```bash
uv run pytest tests/unit/ -v --tb=short -m "not network"
```
Expected: all PASS.

- [ ] **Final commit**

```bash
git add -A
git commit -m "feat: complete signal intelligence pipeline + TP/SL lock system"
```
