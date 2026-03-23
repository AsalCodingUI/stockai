"""
Grid-search tuner for gate thresholds using recent market data.

Usage:
    uv run python scripts/tune_gates.py --symbols IDX30 --period 6mo --horizon 10

Output: top gate configs by F1 for BUY capture (precision/recall vs forward return label).
"""

from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass
from typing import Iterable, List

import numpy as np
import pandas as pd

from stockai.data.sources.yahoo import YahooFinanceSource
from stockai.data.listings import IDX30_STOCKS
from stockai.scoring.analyzer import analyze_stock
from stockai.scoring.gates import GateConfig


@dataclass
class EvalResult:
    cfg: GateConfig
    precision: float
    recall: float
    f1: float
    signals: int
    opportunities: int


def f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def get_symbols(choice: str, max_symbols: int | None = None) -> list[str]:
    if choice.upper() == "IDX30":
        symbols = [s["symbol"] for s in IDX30_STOCKS]
        return symbols[:max_symbols] if max_symbols else symbols
    # fallback: treat as comma list
    symbols = [s.strip().upper() for s in choice.split(",") if s.strip()]
    return symbols[:max_symbols] if max_symbols else symbols


def label_forward_returns(df: pd.DataFrame, horizon: int, buy_thresh: float) -> pd.Series:
    close = df["close"]
    fwd = close.shift(-horizon) / close - 1
    return fwd >= buy_thresh


def evaluate_cfg(
    cfg: GateConfig,
    dfs: dict[str, pd.DataFrame],
    horizon: int,
    buy_thresh: float,
    smart_money_version: str,
) -> EvalResult:
    tp = fp = fn = 0
    signals = 0
    opportunities = 0

    for symbol, df in dfs.items():
        if df is None or df.empty or len(df) < 60:
            continue
        labels = label_forward_returns(df, horizon, buy_thresh)
        for idx in range(len(df) - horizon):
            window = df.iloc[: idx + 1].tail(60)  # use last 60 bars up to idx
            if len(window) < 30:
                continue
            label = bool(labels.iloc[idx])
            if label:
                opportunities += 1

            try:
                analysis = analyze_stock(
                    ticker=symbol,
                    df=window,
                    fundamentals=None,
                    config=cfg,
                    smart_money_version=smart_money_version,
                )
                fired = analysis.gates.all_passed
            except Exception:
                continue

            if fired:
                signals += 1
                if label:
                    tp += 1
                else:
                    fp += 1
            else:
                if label:
                    fn += 1

    precision = tp / signals if signals else 0.0
    recall = tp / opportunities if opportunities else 0.0
    return EvalResult(cfg, precision, recall, f1_score(precision, recall), signals, opportunities)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune gate thresholds for Smart Money v2.")
    parser.add_argument("--symbols", default="IDX30", help="IDX30 or comma-separated symbols")
    parser.add_argument("--period", default="6mo", help="History period to fetch (e.g., 6mo, 1y)")
    parser.add_argument("--horizon", type=int, default=10, help="Forward return horizon (days)")
    parser.add_argument("--buy-thresh", type=float, default=0.04, help="Forward return threshold for BUY label")
    parser.add_argument("--smart-money-version", default="v2", help="Smart Money version (v1|v2)")
    parser.add_argument("--max-symbols", type=int, default=10, help="Limit number of symbols for speed")
    args = parser.parse_args()

    symbols = get_symbols(args.symbols, args.max_symbols)
    yahoo = YahooFinanceSource()

    dfs: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = yahoo.get_price_history(sym, period=args.period)
        if df is not None and not df.empty:
            dfs[sym] = df

    # Grids
    smart_money_mins = [0.0, 0.5, 1.0]
    technical_mins = [30.0, 40.0]
    near_support_pcts = [10.0, 20.0, 30.0]
    adx_mins = [5.0, 12.0]
    overall_mins = [40.0, 50.0, 55.0]

    results: List[EvalResult] = []
    for sm_min, tech_min, sup_pct, adx_min, overall_min in itertools.product(
        smart_money_mins, technical_mins, near_support_pcts, adx_mins, overall_mins
    ):
        cfg = GateConfig(
            overall_min=overall_min,
            technical_min=tech_min,
            smart_money_min=sm_min,
            near_support_pct=sup_pct,
            adx_min=adx_min,
            fundamental_min=50.0,
        )
        res = evaluate_cfg(cfg, dfs, args.horizon, args.buy_thresh, args.smart_money_version)
        results.append(res)

    results = sorted(results, key=lambda r: r.f1, reverse=True)
    top = results[:5]
    print("Top 5 configs by F1 (BUY):")
    for r in top:
        cfg = r.cfg
        print(
            f"F1={r.f1:.3f} P={r.precision:.3f} R={r.recall:.3f} "
            f"signals={r.signals} opp={r.opportunities} | "
            f"overall>={cfg.overall_min}, tech>={cfg.technical_min}, "
            f"sm>={cfg.smart_money_min}, sup<={cfg.near_support_pct}%, adx>={cfg.adx_min}"
        )


if __name__ == "__main__":
    main()
