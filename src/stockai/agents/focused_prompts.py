"""Focused Agent Prompts for Efficient Validation.

Loads simplified prompts for the 3-agent validation pipeline from YAML files.
Each agent has a specific, narrow focus and returns a simple APPROVE/REJECT decision.
"""

import re
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).parent / "prompts"

IDX_QUICK_CONTEXT = """Konteks: Saham IDX (Indonesia). Harga dalam IDR, lot=100 lembar, jam trading 09:00-16:00 WIB.
Sektor: Banking (BBCA/BBRI/BMRI), Consumer (UNVR/ICBP), Mining (ADRO/ITMG), Telco (TLKM/EXCL).
Foreign flow asing = sinyal penting. Waspadai saham gorengan (volume anomali, free float kecil)."""


def _load_prompt(name: str) -> str:
    """Load a system_prompt template string from a YAML file."""
    yaml_path = _PROMPTS_DIR / f"{name}.yaml"
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["system_prompt"].rstrip()


TECHNICAL_ANALYST_PROMPT = _load_prompt("focused_technical_analyst")
FUNDAMENTAL_ANALYST_PROMPT = _load_prompt("focused_fundamental_analyst")
RISK_MANAGER_PROMPT = _load_prompt("focused_risk_manager")


# =============================================================================
# Response Parsing Helper
# =============================================================================

def parse_agent_response(response: str) -> tuple[str, str]:
    """Parse agent response to extract decision and reason.

    Args:
        response: Raw response from the agent

    Returns:
        Tuple of (decision, reason) where decision is "APPROVE" or "REJECT"

    Raises:
        ValueError: If response cannot be parsed
    """
    # Normalize response
    response = response.strip()

    # Try to find DECISION line
    decision_match = re.search(
        r"DECISION:\s*(APPROVE|REJECT)",
        response,
        re.IGNORECASE
    )

    if not decision_match:
        # Fallback: look for the words anywhere
        if "APPROVE" in response.upper():
            decision = "APPROVE"
        elif "REJECT" in response.upper():
            decision = "REJECT"
        else:
            raise ValueError(f"Could not parse decision from response: {response[:100]}")
    else:
        decision = decision_match.group(1).upper()

    # Try to find REASON line
    reason_match = re.search(
        r"REASON:\s*(.+?)(?:\n|$)",
        response,
        re.IGNORECASE
    )

    if reason_match:
        reason = reason_match.group(1).strip()
    else:
        # Fallback: use the last non-empty line
        lines = [l.strip() for l in response.split("\n") if l.strip()]
        reason = lines[-1] if lines else "No reason provided"

    return decision, reason


# =============================================================================
# Prompt Formatters
# =============================================================================

def format_technical_prompt(
    ticker: str,
    tech_score: float,
    rsi: float,
    macd_signal: str,
    adx: float,
    trend_strength: str,
    pct_above_sma20: float,
    support_distance: float,
    resistance_distance: float,
    current_price: float,
) -> str:
    """Format the technical analyst prompt with data."""
    return TECHNICAL_ANALYST_PROMPT.format(
        ticker=ticker,
        tech_score=tech_score,
        rsi=rsi,
        macd_signal=macd_signal,
        adx=adx,
        trend_strength=trend_strength,
        pct_above_sma20=pct_above_sma20,
        support_distance=support_distance,
        resistance_distance=resistance_distance,
        current_price=current_price,
    )


def format_fundamental_prompt(
    ticker: str,
    fund_score: float,
    pe_ratio: float | None,
    pb_ratio: float | None,
    roe: float | None,
    debt_to_equity: float | None,
    profit_margin: float | None,
    sector: str,
) -> str:
    """Format the fundamental analyst prompt with data."""
    return FUNDAMENTAL_ANALYST_PROMPT.format(
        ticker=ticker,
        fund_score=fund_score,
        pe_ratio=f"{pe_ratio:.1f}" if pe_ratio else "N/A",
        pb_ratio=f"{pb_ratio:.1f}" if pb_ratio else "N/A",
        roe=f"{roe:.1f}" if roe else "N/A",
        debt_to_equity=f"{debt_to_equity:.2f}" if debt_to_equity else "N/A",
        profit_margin=f"{profit_margin:.1f}" if profit_margin else "N/A",
        sector=sector or "Unknown",
    )


def format_risk_manager_prompt(
    ticker: str,
    entry_low: float,
    entry_high: float,
    stop_loss: float,
    stop_loss_pct: float,
    tp1: float,
    tp1_pct: float,
    tp2: float,
    tp2_pct: float,
    tp3: float,
    tp3_pct: float,
    rr_ratio: float,
    lots: int,
    position_value: float,
    max_loss: float,
    smart_money: float,
    smart_money_interpretation: str,
    adx: float,
    trend_strength: str,
    gates_passed: int,
) -> str:
    """Format the risk manager prompt with data."""
    return RISK_MANAGER_PROMPT.format(
        ticker=ticker,
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        stop_loss_pct=stop_loss_pct,
        tp1=tp1,
        tp1_pct=tp1_pct,
        tp2=tp2,
        tp2_pct=tp2_pct,
        tp3=tp3,
        tp3_pct=tp3_pct,
        rr_ratio=rr_ratio,
        lots=lots,
        position_value=position_value,
        max_loss=max_loss,
        smart_money=smart_money,
        smart_money_interpretation=smart_money_interpretation,
        adx=adx,
        trend_strength=trend_strength,
        gates_passed=gates_passed,
    )
