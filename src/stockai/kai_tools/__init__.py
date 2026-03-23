"""StockAI tools for kai-code agent integration.

These tools wrap StockAI's core functionality for use with kai-code agents.
"""

from langchain_core.tools import tool
from typing import Optional, Literal
import subprocess
import sys
from pathlib import Path


def _run_stockai_command(args: list[str]) -> str:
    """Run a stockai CLI command and return output.

    Args:
        args: Command arguments to pass to stockai

    Returns:
        Command output as string
    """
    cmd = [sys.executable, "-m", "stockai.cli.main"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minute timeout
    )

    if result.returncode != 0:
        return f"Error: {result.stderr}"

    return result.stdout


@tool("stockai_quality")
def stockai_quality(
    symbol: str,
) -> str:
    """Run comprehensive quality analysis on a stock.

    Analyzes stock through 6-gate quality filter:
    - Overall Score (>=70 to pass)
    - Technical Score (>=60 to pass)
    - Smart Money Score (>=3.0 to pass)
    - Distance to Support (<=5% to pass)
    - ADX Trend Strength (>=20 to pass)
    - Fundamental Score (>=60 to pass)

    Args:
        symbol: Stock symbol (e.g., BBCA, TLKM)

    Returns:
        Complete quality analysis with trade plan
    """
    return _run_stockai_command(["quality", symbol.upper()])


@tool("stockai_analyze")
def stockai_analyze(
    symbol: str,
) -> str:
    """Quick analysis of stock technical and fundamental indicators.

    Args:
        symbol: Stock symbol (e.g., BBCA, TLKM)

    Returns:
        Technical and fundamental analysis summary
    """
    return _run_stockai_command(["analyze", symbol.upper()])


@tool("stockai_autopilot")
def stockai_autopilot(
    dry_run: bool = True,
) -> str:
    """Run automated trading system with AI-powered analysis.

    Executes the full trading workflow:
    1. SCAN: Load portfolio, fetch prices, calculate scores
    2. SIGNAL: Generate BUY/SELL signals
    3. AI GATE: Validate signals with 7-agent AI orchestrator
    4. SIZING: Calculate position sizes (2% risk rule)
    5. EXECUTE: Paper trading execution
    6. REPORT: Display results with AI insights

    Args:
        dry_run: If True, scan without executing trades

    Returns:
        Autopilot execution report with recommendations
    """
    args = ["autopilot"]
    if dry_run:
        args.append("--dry-run")
    return _run_stockai_command(args)


@tool("stockai_portfolio_view")
def stockai_portfolio_view() -> str:
    """View current paper trading portfolio.

    Returns:
        Portfolio summary with positions, P&L, and performance
    """
    return _run_stockai_command(["paper", "view"])


@tool("stockai_portfolio_buy")
def stockai_portfolio_buy(
    symbol: str,
    shares: int,
    price: Optional[float] = None,
) -> str:
    """Buy shares in paper trading portfolio.

    Args:
        symbol: Stock symbol to buy
        shares: Number of shares to buy
        price: Optional price (uses market price if not provided)

    Returns:
        Trade execution confirmation
    """
    args = ["paper", "buy", symbol.upper(), str(shares)]
    if price:
        args.extend(["--price", str(price)])
    return _run_stockai_command(args)


@tool("stockai_portfolio_sell")
def stockai_portfolio_sell(
    symbol: str,
    shares: int,
    price: Optional[float] = None,
) -> str:
    """Sell shares in paper trading portfolio.

    Args:
        symbol: Stock symbol to sell
        shares: Number of shares to sell
        price: Optional price (uses market price if not provided)

    Returns:
        Trade execution confirmation
    """
    args = ["paper", "sell", symbol.upper(), str(shares)]
    if price:
        args.extend(["--price", str(price)])
    return _run_stockai_command(args)


@tool("stockai_risk_position")
def stockai_risk_position(
    symbol: str,
) -> str:
    """Analyze risk for a specific position.

    Args:
        symbol: Stock symbol to analyze

    Returns:
        Risk analysis including ATR, stop-loss, take-profit levels
    """
    return _run_stockai_command(["risk", "position", symbol.upper()])


@tool("stockai_risk_diversification")
def stockai_risk_diversification() -> str:
    """Check portfolio diversification across sectors.

    Returns:
        Diversification analysis with sector allocation and warnings
    """
    return _run_stockai_command(["risk", "diversification"])


@tool("stockai_risk_portfolio")
def stockai_risk_portfolio() -> str:
    """Analyze overall portfolio risk.

    Returns:
        Portfolio risk metrics including concentration, volatility, correlation
    """
    return _run_stockai_command(["risk", "portfolio"])


@tool("stockai_briefing_morning")
def stockai_briefing_morning() -> str:
    """Get morning briefing for pre-market preparation.

    Returns:
        Pre-market alerts, watchlist, and trading setup
    """
    return _run_stockai_command(["morning"])


@tool("stockai_briefing_evening")
def stockai_briefing_evening() -> str:
    """Get evening briefing for daily review.

    Returns:
        Daily P&L tracking, position updates, market summary
    """
    return _run_stockai_command(["evening"])


@tool("stockai_briefing_weekly")
def stockai_briefing_weekly() -> str:
    """Get weekly performance review.

    Returns:
        Weekly performance analysis, win rate, lessons learned
    """
    return _run_stockai_command(["weekly"])


@tool("stockai_agents_scan")
def stockai_agents_scan() -> str:
    """Run AI market scan to discover trading opportunities.

    Uses multi-agent system to analyze market:
    - Market Scanner: Finds opportunities
    - Technical Analyst: Chart patterns
    - Fundamental Analyst: Company analysis
    - Sentiment Analyst: News sentiment

    Returns:
        List of potential trading opportunities with AI reasoning
    """
    return _run_stockai_command(["agents", "scan"])


@tool("stockai_agents_recommend")
def stockai_agents_recommend() -> str:
    """Get AI-powered stock recommendations.

    Returns:
        Curated list of BUY/SELL recommendations with detailed analysis
    """
    return _run_stockai_command(["agents", "recommend"])


@tool("stockai_agents_daily")
def stockai_agents_daily() -> str:
    """Get daily AI analysis summary.

    Returns:
        Daily market insights and stock analysis from AI agents
    """
    return _run_stockai_command(["agents", "daily"])


def get_all_stockai_tools() -> list:
    """Get all stockai tools for kai-code agent.

    Returns:
        List of all stockai tool functions
    """
    return [
        stockai_quality,
        stockai_analyze,
        stockai_autopilot,
        stockai_portfolio_view,
        stockai_portfolio_buy,
        stockai_portfolio_sell,
        stockai_risk_position,
        stockai_risk_diversification,
        stockai_risk_portfolio,
        stockai_briefing_morning,
        stockai_briefing_evening,
        stockai_briefing_weekly,
        stockai_agents_scan,
        stockai_agents_recommend,
        stockai_agents_daily,
    ]


__all__ = [
    "stockai_quality",
    "stockai_analyze",
    "stockai_autopilot",
    "stockai_portfolio_view",
    "stockai_portfolio_buy",
    "stockai_portfolio_sell",
    "stockai_risk_position",
    "stockai_risk_diversification",
    "stockai_risk_portfolio",
    "stockai_briefing_morning",
    "stockai_briefing_evening",
    "stockai_briefing_weekly",
    "stockai_agents_scan",
    "stockai_agents_recommend",
    "stockai_agents_daily",
    "get_all_stockai_tools",
]
