"""StockAI Agent LLM Query Demo

This demonstrates how to use StockAI agents with LLM queries.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kai_code.agent_loader import load_agent


def demo_llm_usage():
    """Demonstrate LLM usage with StockAI agents."""

    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*15 + "StockAI Agent LLM Query Demo" + " "*30 + "║")
    print("╚" + "═"*78 + "╝")

    # Check API key status
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        print("\n✓ GOOGLE_API_KEY is set")
        print("  LLM queries will work with Gemini models")
    else:
        print("\n⚠️  GOOGLE_API_KEY not found in environment")
        print("  LLM queries will fail without API key")
        print("\n  To set up:")
        print("    export GOOGLE_API_KEY='your-api-key-here'")
        print("  Or use stockai .env file:")
        print("    cp .env.example .env")
        print("    # Edit .env and add your key")
        print("    source .env")

    print("\n" + "="*80)
    print("STOCKAI AGENT USAGE EXAMPLES")
    print("="*80)

    # Example 1: Main agent
    print("\n" + "-"*80)
    print("Example 1: Main StockAI Agent")
    print("-"*80)

    print("\nfrom kai_code.agent_loader import load_agent")
    print("\nagent = load_agent('stockai')")
    print("result = agent.run('What is StockAI?')")
    print("\nExpected behavior:")
    print("  1. Agent loads its prompt from .kai/agents/stockai.md")
    print("  2. Agent combines with kai-code base prompt")
    print("  3. LLM receives: 21K+ chars of trading knowledge")
    print("  4. Agent responds with StockAI overview")
    print("  5. Can delegate to subagents if needed")

    # Example 2: Analyst agent
    print("\n" + "-"*80)
    print("Example 2: StockAI Analyst Agent")
    print("-"*80)

    print("\nanalyst = load_agent('stockai-analyst')")
    print("result = analyst.run('Analyze BBCA for investment')")
    print("\nExpected behavior:")
    print("  1. Analyst loads 27K chars of analysis knowledge")
    print("  2. Invokes stockai_quality BBCA tool")
    print("  3. Analyzes 6-gate quality filter results")
    print("  4. Provides investment recommendation")
    print("  5. Includes entry/exit levels and reasoning")

    # Example 3: Tool invocation
    print("\n" + "-"*80)
    print("Example 3: Agent with Tool Invocation")
    print("-"*80)

    print("\nagent = load_agent('stockai')")
    print("result = agent.run('Show my morning briefing')")
    print("\nExpected behavior:")
    print("  1. Agent identifies need for briefing tool")
    print("  2. Invokes stockai_briefing_morning tool")
    print("  3. Gets real data from StockAI CLI")
    print("  4. Formats and presents to user")
    print("  5. Provides actionable insights")

    # Show actual agent capabilities
    print("\n" + "="*80)
    print("AGENT CAPABILITIES (No LLM Required)")
    print("="*80)

    from stockai.kai_tools import stockai_briefing_morning

    print("\n✓ Tools work independently of LLM:")
    print("  - Tools invoke StockAI CLI directly")
    print("  - Return real data from StockAI backend")
    print("  - Can be used programmatically")

    print("\n📊 Example: Get morning briefing (no LLM needed)")
    try:
        result = stockai_briefing_morning.invoke({})
        print("\n" + result)
    except Exception as e:
        print(f"\n  Tool error: {e}")

    # Show prompt content
    print("\n" + "="*80)
    print("AGENT PROMPT CONTENT")
    print("="*80)

    from kai_code.prompts import load_prompt

    print("\n📚 Main agent (stockai):")
    prompt = load_prompt("stockai")
    print(f"  - Prompt length: {len(prompt)} characters")
    print("  - Includes: Trading methodology, 6-gate filter, risk management")

    print("\n📚 Analyst agent (stockai-analyst):")
    prompt = load_prompt("stockai-analyst")
    print(f"  - Prompt length: {len(prompt)} characters")
    print("  - Includes: Analysis framework, quality gates, sector expertise")

    print("\n📚 Trader agent (stockai-trader):")
    prompt = load_prompt("stockai-trader")
    print(f"  - Prompt length: {len(prompt)} characters")
    print("  - Includes: 2% risk rule, position sizing, execution workflow")

    print("\n📚 Risk agent (stockai-risk):")
    prompt = load_prompt("stockai-risk")
    print(f"  - Prompt length: {len(prompt)} characters")
    print("  - Includes: Risk metrics, concentration limits, stress testing")

    print("\n" + "="*80)
    print("LLM QUERY SCENARIOS")
    print("="*80)

    scenarios = [
        ("Market Overview",
         "What's the market outlook today?",
         "Agent would provide market summary and opportunities"),

        ("Stock Analysis",
         "Should I buy BBCA at current price?",
         "Analyst would run quality check and provide recommendation"),

        ("Portfolio Review",
         "How's my portfolio doing?",
         "Agent would check portfolio and provide P&L summary"),

        ("Risk Check",
         "Am I taking too much risk?",
         "Risk manager would analyze exposure and provide warnings"),

        ("Trading Execution",
         "Calculate position size for BBCA with 2% risk",
         "Trader would calculate shares and stop-loss levels"),
    ]

    print("\n" + "Scenario: " + "Query" + "\n" + "─"*80)
    for title, query, expected in scenarios:
        print(f"\n{title}")
        print(f"  Query: {query}")
        print(f"  Expected: {expected}")

    print("\n" + "="*80)
    print("SETUP INSTRUCTIONS")
    print("="*80)

    print("\n1. Install kai-code (if not already done):")
    print("   cd /path/to/kai-code-1")
    print("   uv sync")

    print("\n2. Set up StockAI with kai-code:")
    print("   cd /path/to/stockai")
    print("   # kai-code is in pyproject.toml")
    print("   uv sync")

    print("\n3. Configure API key:")
    print("   cd /path/to/stockai")
    print("   cp .env.example .env")
    print("   # Edit .env and add: GOOGLE_API_KEY=your-key")
    print("   source .env")

    print("\n4. Run agents:")
    print("   python -c \"")
    print("   from kai_code.agent_loader import load_agent")
    print("   agent = load_agent('stockai')")
    print("   result = agent.run('What should I buy today?')")
    print("   print(result)")
    print("   \"")

    print("\n" + "="*80)
    print("KEY POINTS")
    print("="*80)

    print("\n✓ Agents work without LLM (tool invocation)")
    print("✓ LLM adds reasoning and coordination")
    print("✓ Subagents provide specialized expertise")
    print("✓ All trading uses paper trading (safe)")
    print("✓ Tools provide real StockAI data")

    print("\n⚠️  Remember:")
    print("  • Paper trading only (no real money)")
    print("  • API key needed for LLM queries")
    print("  • Tools work without API key")
    print("  • LLM provides intelligent coordination")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    import os
    # Change to stockai directory
    os.chdir(Path(__file__).parent.parent.parent)
    demo_llm_usage()
