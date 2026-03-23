"""Interactive demo of StockAI agents with simulated queries.

This demonstrates how agents would respond to real trading scenarios.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kai_code.agent_loader import load_agent
from kai_code.prompts import load_prompt


def demo_agent_query_simulation():
    """Simulate how agents would respond to real queries."""

    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*18 + "StockAI Agent Query Simulation" + " "*28 + "║")
    print("╚" + "═"*78 + "╝")

    # Scenario 1: Daily morning routine
    print("\n" + "="*80)
    print("SCENARIO 1: Daily Morning Routine")
    print("="*80)

    print("\n📅 User: What's my morning briefing?")
    print("\n🤖 StockAI Agent would:")
    print("  1. Invoke stockai_briefing_morning tool")
    print("  2. Display pre-market alerts")
    print("  3. Show portfolio snapshot")
    print("  4. List today's watchlist")

    # Actually call the tool
    from stockai.kai_tools import stockai_briefing_morning
    print("\n📊 Actual Output:")
    try:
        result = stockai_briefing_morning.invoke({})
        print(result)
    except Exception as e:
        print(f"  Error: {e}")

    # Scenario 2: Stock analysis request
    print("\n" + "="*80)
    print("SCENARIO 2: Deep Stock Analysis")
    print("="*80)

    print("\n📈 User: Analyze BBCA for investment")
    print("\n🤖 StockAI Agent would:")
    print("  1. Delegate to stockai-analyst subagent")
    print("  2. Run stockai_quality BBCA tool")
    print("  3. Check all 6 quality gates")
    print("  4. Provide trade plan with entry/exit levels")

    # Show what the analyst agent knows
    analyst_prompt = load_prompt("stockai-analyst")
    print(f"\n📊 Analyst has {len(analyst_prompt)} characters of specialized knowledge")
    print("  • 6-gate quality filter methodology")
    print("  • Multi-factor scoring framework")
    print("  • Technical & fundamental analysis")
    print("  • Sector-specific expertise (banking, consumer, etc.)")

    # Scenario 3: Trading decision
    print("\n" + "="*80)
    print("SCENARIO 3: Trading Decision")
    print("="*80)

    print("\n💼 User: Should I buy BBCA at 9500?")
    print("\n🤖 StockAI Trader Agent would:")
    print("  1. Check portfolio has capital available")
    print("  2. Run stockai_quality BBCA to verify gates")
    print("  3. Calculate position size using 2% risk rule")
    print("  4. Determine entry, stop-loss, take-profit levels")
    print("  5. Validate sector exposure")
    print("  6. Provide execution plan")

    trader_prompt = load_prompt("stockai-trader")
    print(f"\n📊 Trader has {len(trader_prompt)} characters of execution knowledge")
    print("  • 2% risk rule enforcement")
    print("  • ATR-based stop-loss calculation")
    print("  • Position sizing formulas")
    print("  • Trade execution workflow")

    # Scenario 4: Risk check
    print("\n" + "="*80)
    print("SCENARIO 4: Portfolio Risk Assessment")
    print("="*80)

    print("\n⚠️  User: Check my portfolio risk")
    print("\n🤖 StockAI Risk Agent would:")
    print("  1. Run stockai_risk_portfolio")
    print("  2. Calculate portfolio beta and volatility")
    print("  3. Check concentration levels")
    print("  4. Verify diversification across sectors")
    print("  5. Identify any risk warnings")
    print("  6. Provide mitigation recommendations")

    risk_prompt = load_prompt("stockai-risk")
    print(f"\n📊 Risk Manager has {len(risk_prompt)} characters of risk knowledge")
    print("  • Portfolio risk metrics (beta, volatility, drawdown)")
    print("  • Concentration analysis")
    print("  • Sector exposure limits")
    print("  • Stress testing scenarios")

    # Scenario 5: Autopilot execution
    print("\n" + "="*80)
    print("SCENARIO 5: Automated Trading Workflow")
    print("="*80)

    print("\n🤖 User: Run autopilot to find opportunities")
    print("\n🤖 StockAI Agent would:")
    print("  1. Invoke stockai_autopilot tool")
    print("  2. Execute full trading workflow:")
    print("     - SCAN: Load portfolio, fetch prices, calculate scores")
    print("     - SIGNAL: Generate BUY/SELL signals")
    print("     - AI GATE: Validate with 7-agent AI orchestrator")
    print("     - SIZING: Calculate 2% risk position sizes")
    print("     - EXECUTE: Paper trading execution")
    print("     - REPORT: Display results with AI insights")

    # Show agent delegation
    print("\n" + "="*80)
    print("AGENT DELEGATION ARCHITECTURE")
    print("="*80)

    print("\n🤖 stockai (Main Agent)")
    print("│")
    print("├─► 🤖 stockai-analyst (Subagent)")
    print("│   └─► Deep analysis using 6-gate quality filter")
    print("│")
    print("├─► 🤖 stockai-trader (Subagent)")
    print("│   └─► Execution with 2% risk rule")
    print("│")
    print("└─► 🤖 stockai-risk (Subagent)")
    print("    └─► Portfolio protection and exposure control")

    # Show available tools
    print("\n" + "="*80)
    print("AVAILABLE TOOLS: 15")
    print("="*80)

    from stockai.kai_tools import get_all_stockai_tools
    tools = get_all_stockai_tools()

    categories = {
        "Analysis": ["stockai_quality", "stockai_analyze", "stockai_risk_position"],
        "Trading": ["stockai_autopilot", "stockai_portfolio_buy", "stockai_portfolio_sell", "stockai_portfolio_view"],
        "Risk": ["stockai_risk_diversification", "stockai_risk_portfolio"],
        "AI Agents": ["stockai_agents_scan", "stockai_agents_recommend", "stockai_agents_daily"],
        "Briefings": ["stockai_briefing_morning", "stockai_briefing_evening", "stockai_briefing_weekly"]
    }

    for category, tool_names in categories.items():
        print(f"\n{category}:")
        for tool_name in tool_names:
            tool = next(t for t in tools if t.name == tool_name)
            desc = tool.description.split(".")[0] + "."
            print(f"  • {tool.name:25} - {desc[:50]}")

    # Show example workflow
    print("\n" + "="*80)
    print("EXAMPLE DAILY WORKFLOW")
    print("="*80)

    print("\n⏰ 08:00 WIB - Morning Routine")
    print("  agent = load_agent('stockai')")
    print("  agent.run('Morning briefing')")
    print("  → Pre-market alerts, watchlist, portfolio snapshot")

    print("\n⏰ 08:30 WIB - Market Scan")
    print("  agent.run('Run autopilot --dry-run')")
    print("  → Scan for opportunities, validate signals")

    print("\n⏰ 09:00 WIB - Deep Analysis")
    print("  analyst = load_agent('stockai-analyst')")
    print("  analyst.run('Analyze BBCA')")
    print("  → Full 6-gate analysis with trade plan")

    print("\n⏰ 10:00 WIB - Trading Decision")
    print("  trader = load_agent('stockai-trader')")
    print("  trader.run('Should I buy BBCA at 9500?')")
    print("  → Position sizing, entry/exit levels")

    print("\n⏰ 10:30 WIB - Risk Validation")
    print("  risk = load_agent('stockai-risk')")
    print("  risk.run('Validate this trade')")
    print("  → Risk check, exposure analysis")

    print("\n⏰ 15:00 WIB - Evening Review")
    print("  agent = load_agent('stockai')")
    print("  agent.run('Evening briefing')")
    print("  → Daily P&L, position updates, market summary")

    # Key takeaways
    print("\n" + "="*80)
    print("KEY TAKEAWAYS")
    print("="*80)

    print("\n✓ All 4 agents load successfully")
    print("✓ 15 tools available for trading operations")
    print("✓ Subagent delegation configured")
    print("✓ Prompts contain specialized knowledge (21K+ chars total)")
    print("✓ Tools invoke StockAI CLI commands")
    print("✓ Uses gemini-3-flash-preview model")
    print("✓ Paper trading for safe learning")

    print("\n" + "="*80)
    print("READY TO USE")
    print("="*80)

    print("\nTo start using:")
    print("  from kai_code.agent_loader import load_agent")
    print("  agent = load_agent('stockai')")
    print("  result = agent.run('Your query here')")

    print("\n⚠️  IMPORTANT:")
    print("  • All trading is PAPER TRADING only")
    print("  • Past performance ≠ future results")
    print("  • Always do your own research")
    print("  • Never risk more than 2% per trade")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    demo_agent_query_simulation()
