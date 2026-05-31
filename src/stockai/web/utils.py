"""Shared helpers, constants, and Pydantic models for the StockAI web layer."""

import statistics
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from stockai.data.sources.yahoo import YahooFinanceSource
from stockai.data.listings import ALL_IDX_STOCKS
from stockai.data.sources.idx import IDXIndexSource
from stockai.scoring.analyzer import analyze_stock, GateConfig
from stockai.core.foreign_flow import ForeignFlowMonitor
from stockai.core.volume_detector import UnusualVolumeDetector
from stockai.core.sentiment.stockbit import StockbitSentiment
from stockai.core.ml.probability import ProbabilityEngine


# ── Constants ──────────────────────────────────────────────────────────────────

SCAN_LAST_TTL_SECONDS = 15 * 60
ALERT_DISMISS_TTL_SECONDS = 6 * 60 * 60
PORTFOLIO_META_TTL_SECONDS = 24 * 60 * 60

_WEB_RUNTIME: dict[str, Any] = {
    "last_scan": None,
    "last_scan_at": None,
    "alerts_dismissed_until": None,
    "portfolio_meta": {},
}


# ── Pydantic models ─────────────────────────────────────────────────────────────

class PortfolioPositionCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    shares: int = Field(gt=0)
    price: float = Field(gt=0)
    notes: str | None = None


class PortfolioPositionUpdate(BaseModel):
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    notes: str | None = None


# ── Private helpers ─────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _time_key(dt_value: datetime) -> str:
    return dt_value.strftime("%Y-%m-%d")


def _price_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_native(value: Any) -> Any:
    """Recursively convert numpy/pandas scalar types into native Python types."""
    if isinstance(value, dict):
        return {str(k): _to_native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_native(v) for v in value]
    if isinstance(value, tuple):
        return [_to_native(v) for v in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return [_to_native(v) for v in value.tolist()]
    return value


def _safe_support_distance_pct(analysis: Any) -> float | None:
    """Return distance_to_support_pct safely (supports None at every level)."""
    support_resistance = getattr(analysis, "support_resistance", None)
    if support_resistance is None:
        return None
    raw = getattr(support_resistance, "distance_to_support_pct", None)
    try:
        return float(raw) if raw is not None else None
    except Exception:
        return None


def _build_trade_plan_fallback(
    analysis: Any,
    current_price: float | None,
) -> dict[str, Any]:
    """Build trade plan from analyzer output, fallback to SR/risk-derived values."""
    tp = getattr(analysis, "trade_plan", None)
    price = float(current_price or 0.0)

    entry_low = _price_or_none(getattr(tp, "entry_low", None)) if tp else None
    entry_high = _price_or_none(getattr(tp, "entry_high", None)) if tp else None
    sl = _price_or_none(getattr(tp, "stop_loss", None)) if tp else None
    tp1 = _price_or_none(getattr(tp, "take_profit_1", None)) if tp else None
    tp2 = _price_or_none(getattr(tp, "take_profit_2", None)) if tp else None
    tp3 = _price_or_none(getattr(tp, "take_profit_3", None)) if tp else None
    rr = _price_or_none(getattr(tp, "risk_reward_ratio", None)) if tp else None

    if price > 0:
        sr = getattr(analysis, "support_resistance", None)
        support = _price_or_none(getattr(sr, "nearest_support", None)) if sr else None
        resistances = getattr(sr, "resistances", None) if sr else None
        resistance = _price_or_none(resistances[0]) if isinstance(resistances, list) and resistances else None
        if resistance is None:
            resistance = _price_or_none(getattr(sr, "nearest_resistance", None)) if sr else None

        if entry_low is None:
            entry_low = support or round(price * 0.99, 0)
        if entry_high is None:
            entry_high = round(price * 1.005, 0)

        if sl is None and entry_low is not None:
            if support and support > 0:
                sl = round(min(entry_low * 0.97, support * 0.995), 0)
            else:
                sl = round(entry_low * 0.97, 0)

        if entry_low is not None:
            risk = (entry_low - sl) if (sl is not None) else (price * 0.03)
            if risk <= 0:
                risk = price * 0.03
            if tp1 is None:
                tp1 = round(entry_low + risk * 1.5, 0)
            if tp2 is None:
                tp2 = round(entry_low + risk * 2.5, 0)
            if tp3 is None:
                fallback_tp3 = entry_low + risk * 3.5
                tp3 = round(resistance if resistance and resistance > (tp2 or 0) else fallback_tp3, 0)

            if rr is None and sl is not None and entry_low is not None:
                actual_risk = entry_low - sl
                actual_reward = (tp1 or entry_low) - entry_low
                rr = round(actual_reward / actual_risk, 2) if actual_risk > 0 else None

    return {
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "rr": rr,
        "is_fallback": tp is None,
    }


def _get_index_symbols(index_name: str) -> list[str]:
    idx = IDXIndexSource()
    upper = index_name.upper()
    if upper == "IDX30":
        return idx.get_idx30_symbols()
    if upper == "LQ45":
        return idx.get_lq45_symbols()
    if upper == "JII70":
        return idx.get_jii70_symbols()
    if upper == "IDX80":
        return idx.get_idx80_symbols()
    if upper == "ALL":
        symbols = []
        seen = set()
        for row in ALL_IDX_STOCKS:
            symbol = str(row.get("symbol", "")).upper().strip()
            if not symbol or symbol in seen:
                continue
            symbols.append(symbol)
            seen.add(symbol)
        return symbols
    return idx.get_idx30_symbols()


def _resolve_timeframe(timeframe: str) -> str:
    mapping = {"1w": "5d", "1m": "1mo", "3m": "3mo", "6m": "6mo"}
    return mapping.get(timeframe.lower(), "3mo")


def _resolve_period(period: str | None, timeframe: str | None) -> str:
    if period:
        return period
    if timeframe:
        return _resolve_timeframe(timeframe)
    return "3mo"


def _normalize_tujuan(value: str | None) -> str:
    raw = (value or "swing").strip().lower()
    if raw in {"scalp", "swing", "invest"}:
        return raw
    return "swing"


def _symbol_to_yf(symbol: str) -> str:
    clean = symbol.strip().upper()
    if clean.startswith("^"):
        return clean
    if clean.endswith(".JK"):
        return clean
    return f"{clean}.JK"


def _normalize_indicator_period(period: str) -> str:
    mapping = {
        "1wk": "5d",
        "1w": "5d",
        "5d": "5d",
        "1mo": "1mo",
        "3mo": "3mo",
        "6mo": "6mo",
        "1y": "1y",
    }
    return mapping.get((period or "3mo").lower(), "3mo")


def _calc_rr(entry: float | None, sl: float | None, tp: float | None) -> float | None:
    if entry is None or sl is None or tp is None:
        return None
    risk = entry - sl
    reward = tp - entry
    if risk <= 0:
        return None
    return reward / risk


def _scan_status(gates_passed: int) -> str:
    if gates_passed >= 5:
        return "READY"
    if gates_passed >= 4:
        return "WATCH"
    return "REJECTED"


def _rank_search_results(rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Rank stock search results by exactness before fuzzy score."""
    q_upper = query.upper().strip()
    q_lower = query.lower().strip()

    def rank_key(row: dict[str, Any]) -> tuple[int, float]:
        symbol = str(row.get("symbol", "")).upper()
        name = str(row.get("name", "")).lower()
        score = float(row.get("score", 0.0) or 0.0)
        if symbol == q_upper:
            return (0, -score)
        if symbol.startswith(q_upper):
            return (1, -score)
        if q_upper in symbol or q_lower in name:
            return (2, -score)
        return (3, -score)

    return sorted(rows, key=rank_key)


def _is_scan_cache_fresh() -> bool:
    last_scan_at = _WEB_RUNTIME.get("last_scan_at")
    if not isinstance(last_scan_at, datetime):
        return False
    return (datetime.utcnow() - last_scan_at).total_seconds() < SCAN_LAST_TTL_SECONDS


def _build_signal_event(symbol: str) -> dict[str, Any]:
    yahoo = YahooFinanceSource()
    foreign = ForeignFlowMonitor()
    volume = UnusualVolumeDetector()
    sentiment = StockbitSentiment()
    probability = ProbabilityEngine()

    info = yahoo.get_stock_info(symbol)
    history = yahoo.get_price_history(symbol, period="6mo")
    if history.empty:
        raise ValueError(f"No history for {symbol}")

    fundamentals = {
        "pe_ratio": info.get("pe_ratio") if info else None,
        "pb_ratio": info.get("pb_ratio") if info else None,
        "roe": None,
        "debt_to_equity": None,
        "profit_margin": None,
        "current_ratio": None,
    }

    flow_signal = foreign.get_flow_signal(symbol, days=5)
    volume_signal = volume.detect(symbol, history=history)
    sentiment_signal = sentiment.analyze(symbol)
    analysis = analyze_stock(
        ticker=symbol,
        df=history,
        fundamentals=fundamentals,
        config=GateConfig(),
        foreign_flow_signal=flow_signal,
        unusual_volume_signal=volume_signal,
        sentiment_signal=sentiment_signal,
    )
    support_distance_pct = _safe_support_distance_pct(analysis)
    forecast = probability.forecast(
        symbol,
        {
            "volume_ratio": volume_signal.get("volume_ratio", 0),
            "adx": analysis.adx.get("adx", 0),
            "near_support": (
                support_distance_pct <= 10 if support_distance_pct is not None else False
            ),
            "sentiment_label": sentiment_signal.get("sentiment", "NEUTRAL"),
            "volume_classification": volume_signal.get("classification", "NORMAL"),
            "smart_money_signal": flow_signal.get("signal", "NEUTRAL"),
        },
    )

    trade_plan = analysis.trade_plan
    rr_value = _calc_rr(
        _price_or_none(analysis.current_price),
        _price_or_none(getattr(trade_plan, "stop_loss", None) if trade_plan else None),
        _price_or_none(getattr(trade_plan, "take_profit_1", None) if trade_plan else None),
    )

    gates_passed = int(getattr(analysis.gates, "gates_passed", 0))
    result = {
        "symbol": symbol,
        "score": round(float(analysis.composite_score), 1),
        "gate_passed": gates_passed,
        "gate_total": int(getattr(analysis.gates, "total_gates", 6)),
        "status": _scan_status(gates_passed),
        "current_price": _price_or_none(analysis.current_price),
        "sl": _price_or_none(getattr(trade_plan, "stop_loss", None) if trade_plan else None),
        "tp1": _price_or_none(getattr(trade_plan, "take_profit_1", None) if trade_plan else None),
        "tp2": _price_or_none(getattr(trade_plan, "take_profit_2", None) if trade_plan else None),
        "rr": round(rr_value, 2) if rr_value is not None else None,
        "smart_money": {
            "signal": flow_signal.get("signal", "NEUTRAL"),
            "strength": flow_signal.get("strength", "WEAK"),
            "source": flow_signal.get("source", "volume_proxy"),
        },
        "volume": {
            "classification": volume_signal.get("classification", "NORMAL"),
            "ratio": round(float(volume_signal.get("volume_ratio", 0.0) or 0.0), 2),
            "price_action": volume_signal.get("price_action", "NEUTRAL"),
        },
        "sentiment": {
            "label": sentiment_signal.get("sentiment", "NEUTRAL"),
            "score": int(sentiment_signal.get("score", 0) or 0),
            "source": sentiment_signal.get("source", "stockbit"),
        },
        "probability": {
            "p5": float(forecast.get("probability_5pct", 0.0)),
            "expected": float(forecast.get("expected_return", 0.0)),
            "confidence": forecast.get("confidence", "LOW"),
        },
        "pattern": {
            "dominant": forecast.get("dominant_pattern"),
            "bias": forecast.get("overall_pattern_bias", "NEUTRAL"),
            "count": int(forecast.get("pattern_count", 0) or 0),
        },
    }
    return result


def _portfolio_history(days: int = 30) -> list[dict[str, Any]]:
    from stockai.core.portfolio import PortfolioManager

    yahoo = YahooFinanceSource()
    manager = PortfolioManager()
    positions = manager.get_positions()
    if not positions:
        return []

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=max(days * 2, 40))

    series_map: dict[str, dict[str, float]] = {}
    for pos in positions:
        symbol = str(pos.get("symbol", "")).upper().strip()
        shares = float(pos.get("shares", 0) or 0)
        if not symbol or shares <= 0:
            continue
        df = yahoo.get_price_history(
            symbol,
            start=datetime.combine(start_date, datetime.min.time()),
            end=datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        )
        if df.empty:
            continue
        points: dict[str, float] = {}
        for _, row in df.iterrows():
            date_key = _time_key(row["date"])
            close_price = _price_or_none(row.get("close"))
            if close_price is None:
                continue
            points[date_key] = close_price * shares
        series_map[symbol] = points

    if not series_map:
        return []

    all_dates = sorted(set().union(*[set(v.keys()) for v in series_map.values()]))
    total_cost = sum(float(p.get("cost_basis", 0) or 0) for p in positions)
    history: list[dict[str, Any]] = []
    last_value = total_cost
    for date_key in all_dates:
        day_value = 0.0
        for symbol, symbol_points in series_map.items():
            if date_key in symbol_points:
                day_value += symbol_points[date_key]
            else:
                day_value += 0.0
        if day_value <= 0:
            day_value = last_value
        pnl = day_value - total_cost
        pnl_pct = (pnl / total_cost * 100) if total_cost > 0 else 0
        history.append({
            "date": date_key,
            "value": round(day_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })
        last_value = day_value

    return history[-days:]


def _risk_metrics_from_history(
    history: list[dict[str, Any]],
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    values = [float(point.get("value", 0) or 0) for point in history if point.get("value") is not None]
    if len(values) < 3:
        return {
            "var_95": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate": 0.0,
            "win_trades": 0,
            "total_trades": 0,
        }

    returns = []
    for prev, curr in zip(values[:-1], values[1:]):
        if prev > 0:
            returns.append((curr / prev) - 1)

    if returns:
        sorted_returns = sorted(returns)
        var95 = sorted_returns[max(int(len(sorted_returns) * 0.05) - 1, 0)] * values[-1]
        avg_ret = statistics.mean(returns)
        std_ret = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        sharpe = (avg_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0.0
    else:
        var95 = 0.0
        sharpe = 0.0

    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (value - peak) / peak
            max_dd = min(max_dd, drawdown)

    pnl_points = [float(point.get("pnl", 0) or 0) for point in history]
    wins = len([p for p in pnl_points if p > 0])
    total = len(pnl_points)
    win_rate = (wins / total * 100) if total > 0 else 0.0

    return {
        "var_95": round(var95, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate": round(win_rate, 2),
        "win_trades": wins,
        "total_trades": total,
    }


def _compose_alerts() -> list[dict[str, Any]]:
    now = datetime.utcnow()
    dismissed_until = _WEB_RUNTIME.get("alerts_dismissed_until")
    if isinstance(dismissed_until, datetime) and now <= dismissed_until:
        return []

    alerts: list[dict[str, Any]] = []
    from stockai.core.portfolio import PnLCalculator

    try:
        portfolio = PnLCalculator().get_portfolio_summary()
        for pos in portfolio.get("positions", []):
            pnl_pct = float(pos.get("pnl_percent", 0) or 0)
            if pnl_pct <= -4.5:
                alerts.append({
                    "level": "CRITICAL",
                    "title": f"{pos.get('symbol')} mendekati stop-loss ({pnl_pct:.1f}%)",
                    "timestamp": _now_iso(),
                })
    except Exception:
        pass

    last_scan = _WEB_RUNTIME.get("last_scan") or {}
    for item in (last_scan.get("results", [])[:5] if isinstance(last_scan, dict) else []):
        status = str(item.get("status", "REJECTED")).upper()
        if status in {"WATCH", "READY"}:
            alerts.append({
                "level": "WATCH",
                "title": f"{item.get('symbol')} masuk {status}",
                "timestamp": _now_iso(),
            })

    if isinstance(last_scan, dict) and last_scan.get("index"):
        alerts.append({
            "level": "INFO",
            "title": f"Scan {last_scan.get('index')} selesai ({last_scan.get('scanned', 0)} saham)",
            "timestamp": last_scan.get("timestamp", _now_iso()),
        })

    return alerts[:50]
