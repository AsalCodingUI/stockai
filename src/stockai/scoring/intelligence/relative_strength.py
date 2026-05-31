"""Relative strength versus IHSG."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class RelativeStrengthResult:
    """Relative strength output."""

    value: float
    score: float


def calculate_relative_strength(
    stock_history: pd.DataFrame,
    index_history: pd.DataFrame,
) -> RelativeStrengthResult:
    if (
        stock_history is None
        or index_history is None
        or stock_history.empty
        or index_history.empty
        or len(stock_history) < 21
        or len(index_history) < 21
    ):
        return RelativeStrengthResult(value=1.0, score=2.0)

    stock_closes = stock_history["close"].astype(float).reset_index(drop=True)
    index_closes = index_history["close"].astype(float).reset_index(drop=True)

    stock_return = (stock_closes.iloc[-1] - stock_closes.iloc[-21]) / stock_closes.iloc[-21]
    index_return = (index_closes.iloc[-1] - index_closes.iloc[-21]) / index_closes.iloc[-21]
    if index_return == 0:
        rs = 1.0
    else:
        rs = stock_return / index_return

    if rs > 1.5:
        score = 10.0
    elif rs >= 1.0:
        score = 6.0
    elif rs >= 0.5:
        score = 2.0
    else:
        score = 0.0

    return RelativeStrengthResult(value=float(rs), score=score)
