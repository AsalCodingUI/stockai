"""StockAI Agent Demo

This script demonstrates how to use the kai-code agents for stock trading.
"""

from kai_code.agent_loader import load_agent


def demo_stockai_agent():
    """Demonstrate the main stockai agent."""
    print("="*70)
    print("StockAI Agent Demo")
    print("="*70)

    print("\n1. Loading stockai agent...")
    agent = load_agent("stockai")
    print(f"   ✓ Agent loaded: {agent.__class__.__name__}")

    print("\n2. Checking agent configuration...")
    print(f"   ✓ Model: {agent.config.model if hasattr(agent.config, 'model') else 'inherit'}")
    print(f"   ✓ Tools: {len(agent._get_subclass_tools())} tools available")

    print("\n3. Available subagents:")
    print("   - stockai-analyst (deep analysis)")
    print("   - stockai-trader (execution)")
    print("   - stockai-risk (risk management)")

    print("\n4. Example queries you can ask:")
    print("   'What should I buy today?'")
    print("   'Analyze BBCA in detail'")
    print("   'Should I sell my TLKM position?'")
    print("   'Check my portfolio risk'")
    print("   'Run morning briefing'")

    print("\n5. To use the agent:")
    print("   result = agent.run('Your query here')")
    print("   print(result)")


def demo_stockai_analyst():
    """Demonstrate the stockai-analyst agent."""
    print("\n" + "="*70)
    print("StockAI Analyst Agent Demo")
    print("="*70)

    print("\n1. Loading stockai-analyst agent...")
    agent = load_agent("stockai-analyst")
    print(f"   ✓ Agent loaded: {agent.__class__.__name__}")

    print("\n2. Analyst capabilities:")
    print("   - 6-gate quality filter analysis")
    print("   - Multi-factor scoring (value, quality, momentum, volatility)")
    print("   - Technical analysis (RSI, MACD, Bollinger, ADX)")
    print("   - Fundamental analysis (P/E, P/B, ROE, debt ratios)")
    print("   - Smart money analysis (OBV, MFI, volume)")

    print("\n3. Example queries:")
    print("   'Analyze BBCA'")
    print("   'Compare BBCA vs BMRI'")
    print("   'Is TLKM a buy right now?'")
    print("   'What's the 6-gate filter for BBCA?'")


def demo_stockai_trader():
    """Demonstrate the stockai-trader agent."""
    print("\n" + "="*70)
    print("StockAI Trader Agent Demo")
    print("="*70)

    print("\n1. Loading stockai-trader agent...")
    agent = load_agent("stockai-trader")
    print(f"   ✓ Agent loaded: {agent.__class__.__name__}")

    print("\n2. Trader capabilities:")
    print("   - BUY/SELL decision framework")
    print("   - 2% risk rule position sizing")
    print("   - ATR-based stop-losses")
    print("   - Take-profit calculation (1:1.5 risk/reward)")
    print("   - Portfolio management")

    print("\n3. Example queries:")
    print("   'Should I buy BBCA at 9500?'")
    print("   'Calculate position size for BBCA with 2% risk'")
    print("   'Should I sell my TLKM position?'")
    print("   'How's my portfolio doing today?'")


def demo_stockai_risk():
    """Demonstrate the stockai-risk agent."""
    print("\n" + "="*70)
    print("StockAI Risk Manager Agent Demo")
    print("="*70)

    print("\n1. Loading stockai-risk agent...")
    agent = load_agent("stockai-risk")
    print(f"   ✓ Agent loaded: {agent.__class__.__name__}")

    print("\n2. Risk manager capabilities:")
    print("   - Portfolio risk assessment (beta, volatility, drawdown)")
    print("   - Position sizing validation")
    print("   - Sector exposure control (40% max)")
    print("   - Concentration analysis")
    print("   - Stress testing scenarios")

    print("\n3. Example queries:")
    print("   'Check my portfolio risk'")
    print("   'Am I too concentrated in banking?'")
    print("   'Validate this trade: buy BBCA at 9500'")
    print("   'What's my portfolio drawdown?'")


def demo_tools():
    """Demonstrate available tools."""
    print("\n" + "="*70)
    print("StockAI Tools Demo")
    print("="*70)

    from stockai.kai_tools import get_all_stockai_tools

    print("\n1. Loading tools...")
    tools = get_all_stockai_tools()
    print(f"   ✓ {len(tools)} tools available")

    print("\n2. Analysis Tools:")
    print("   - stockai_quality: Full 6-gate analysis")
    print("   - stockai_analyze: Quick technical/fundamental check")
    print("   - stockai_risk_position: Position-specific risk")

    print("\n3. Trading Tools:")
    print("   - stockai_autopilot: Full trading workflow")
    print("   - stockai_portfolio_buy: Buy shares")
    print("   - stockai_portfolio_sell: Sell shares")
    print("   - stockai_portfolio_view: View positions")

    print("\n4. Risk Tools:")
    print("   - stockai_risk_diversification: Sector allocation")
    print("   - stockai_risk_portfolio: Overall portfolio risk")

    print("\n5. AI Agent Tools:")
    print("   - stockai_agents_scan: Discover opportunities")
    print("   - stockai_agents_recommend: AI-validated picks")
    print("   - stockai_agents_daily: Daily AI insights")

    print("\n6. Briefing Tools:")
    print("   - stockai_briefing_morning: Pre-market prep")
    print("   - stockai_briefing_evening: Daily review")
    print("   - stockai_briefing_weekly: Weekly performance")


def demo_workflow():
    """Demonstrate typical daily workflow."""
    print("\n" + "="*70)
    print("Daily Trading Workflow Demo")
    print("="*70)

    print("\n1. Morning Routine (5 min)")
    print("   agent = load_agent('stockai')")
    print("   agent.run('What\\'s my morning briefing?')")

    print("\n2. Market Scan (15 min)")
    print("   agent.run('Run autopilot to find opportunities')")

    print("\n3. Deep Analysis (5 min per stock)")
    print("   analyst = load_agent('stockai-analyst')")
    print("   analyst.run('Analyze BBCA')")

    print("\n4. Trade Execution")
    print("   trader = load_agent('stockai-trader')")
    print("   trader.run('Should I buy BBCA at 9500?')")

    print("\n5. Risk Check")
    print("   risk = load_agent('stockai-risk')")
    print("   risk.run('Validate this trade')")

    print("\n6. Evening Review (5 min)")
    print("   agent = load_agent('stockai')")
    print("   agent.run('What\\'s my evening briefing?')")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*15 + "StockAI Kai-Code Agent Demo" + " "*21 + "║")
    print("╚" + "═"*68 + "╝")

    demo_stockai_agent()
    demo_stockai_analyst()
    demo_stockai_trader()
    demo_stockai_risk()
    demo_tools()
    demo_workflow()

    print("\n" + "="*70)
    print("Demo Complete!")
    print("="*70)

    print("\nTo use these agents:")
    print("  from kai_code.agent_loader import load_agent")
    print("  agent = load_agent('stockai')")
    print("  result = agent.run('Your query here')")

    print("\nDocumentation:")
    print("  - stockai/docs/kai-code-integration.md")
    print("  - stockai/.kai/agents/*.md")

    print("\n⚠️  Remember:")
    print("  - All trading is PAPER TRADING only")
    print("  - Past performance ≠ future results")
    print("  - Always do your own research")
    print("  - Never risk more than 2% per trade")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
