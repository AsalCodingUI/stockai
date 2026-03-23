"""Integration tests for StockAI kai-code agents.

These tests verify that the kai-code agent integration works correctly.
"""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestStockAIAgents:
    """Test StockAI agent loading and basic functionality."""

    def test_import_kai_code(self):
        """Test that kai-code can be imported."""
        from kai_code.agent_loader import load_agent, list_agents
        assert load_agent is not None
        assert list_agents is not None

    def test_import_stockai_tools(self):
        """Test that StockAI tools can be imported."""
        from stockai.kai_tools import get_all_stockai_tools
        tools = get_all_stockai_tools()
        assert len(tools) == 15
        tool_names = [t.name for t in tools]
        assert "stockai_quality" in tool_names
        assert "stockai_autopilot" in tool_names
        assert "stockai_portfolio_view" in tool_names

    def test_list_agents(self):
        """Test that stockai agents are available."""
        from kai_code.agent_loader import list_agents
        agents = list_agents()
        assert "stockai" in agents
        assert "stockai-analyst" in agents
        assert "stockai-trader" in agents
        assert "stockai-risk" in agents

    def test_load_stockai_agent(self):
        """Test loading the main stockai agent."""
        from kai_code.agent_loader import load_agent
        agent = load_agent("stockai")
        assert agent is not None
        assert agent.__class__.__name__ == "Stockai"

    def test_load_stockai_analyst(self):
        """Test loading the stockai-analyst agent."""
        from kai_code.agent_loader import load_agent
        agent = load_agent("stockai-analyst")
        assert agent is not None
        assert agent.__class__.__name__ == "Stockai_analyst"

    def test_load_stockai_trader(self):
        """Test loading the stockai-trader agent."""
        from kai_code.agent_loader import load_agent
        agent = load_agent("stockai-trader")
        assert agent is not None
        assert agent.__class__.__name__ == "Stockai_trader"

    def test_load_stockai_risk(self):
        """Test loading the stockai-risk agent."""
        from kai_code.agent_loader import load_agent
        agent = load_agent("stockai-risk")
        assert agent is not None
        assert agent.__class__.__name__ == "Stockai_risk"

    def test_agent_tools(self):
        """Test that agents have access to tools."""
        from kai_code.agent_loader import load_agent
        agent = load_agent("stockai")
        # Agent should have _get_subclass_tools method
        assert hasattr(agent, "_get_subclass_tools")
        tools = agent._get_subclass_tools()
        assert len(tools) > 0


class TestStockAITools:
    """Test StockAI tool definitions."""

    def test_tool_definitions(self):
        """Test that all tools are properly defined."""
        from stockai.kai_tools import (
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
        )

        # Verify tool names
        assert stockai_quality.name == "stockai_quality"
        assert stockai_autopilot.name == "stockai_autopilot"

        # Verify tool descriptions
        assert stockai_quality.description is not None
        assert len(stockai_quality.description) > 0

    def test_tool_schemas(self):
        """Test that tools have proper schemas."""
        from stockai.kai_tools import stockai_quality, stockai_portfolio_buy
        # Tools should have args_schema
        assert stockai_quality.args_schema is not None
        assert stockai_portfolio_buy.args_schema is not None


class TestAgentDefinitions:
    """Test agent definition files."""

    def test_stockai_agent_file_exists(self):
        """Test that stockai.md exists."""
        agent_file = Path(".kai/agents/stockai.md")
        assert agent_file.exists()

    def test_stockai_analyst_file_exists(self):
        """Test that stockai-analyst.md exists."""
        agent_file = Path(".kai/agents/stockai-analyst.md")
        assert agent_file.exists()

    def test_stockai_trader_file_exists(self):
        """Test that stockai-trader.md exists."""
        agent_file = Path(".kai/agents/stockai-trader.md")
        assert agent_file.exists()

    def test_stockai_risk_file_exists(self):
        """Test that stockai-risk.md exists."""
        agent_file = Path(".kai/agents/stockai-risk.md")
        assert agent_file.exists()

    def test_agent_file_content(self):
        """Test that agent files have required content."""
        import yaml

        agent_file = Path(".kai/agents/stockai.md")
        content = agent_file.read_text()

        # Check YAML frontmatter
        assert content.startswith("---")
        assert "name: stockai" in content
        assert "description:" in content
        assert "extends: kai-code" in content
        assert "tools:" in content
        assert "subagents:" in content


class TestAgentCompilation:
    """Test agent compilation to Python."""

    def test_compile_stockai_agent(self):
        """Test compiling stockai agent to Python."""
        from kai_code.agent_definition import AgentDefinition
        from pathlib import Path

        agent_file = Path(".kai/agents/stockai.md")
        definition = AgentDefinition(agent_file)

        # Check metadata
        assert definition.name == "stockai"
        assert definition.description is not None
        assert definition.extends == "kai-code"

        # Check compilation
        agent_class = definition.to_agent_class()
        assert agent_class is not None
        assert agent_class.__name__ == "Stockai"


@pytest.mark.slow
class TestAgentExecution:
    """Slow tests that actually run agents (may require LLM)."""

    @pytest.mark.skip(reason="Requires LLM API key")
    def test_stockai_agent_query(self):
        """Test running a query with stockai agent."""
        from kai_code.agent_loader import load_agent

        agent = load_agent("stockai")
        # This would require an actual LLM API key
        # result = agent.run("What is stockai?")
        # assert result is not None

    @pytest.mark.skip(reason="Requires LLM API key")
    def test_tool_invocation(self):
        """Test that tools can be invoked."""
        from stockai.kai_tools import stockai_portfolio_view

        # This would require StockAI to be set up
        # result = stockai_portfolio_view.invoke({})
        # assert result is not None


if __name__ == "__main__":
    # Run tests quickly without pytest
    print("Running StockAI Agent Integration Tests...\n")

    suite1 = TestStockAIAgents()
    suite2 = TestStockAITools()
    suite3 = TestAgentDefinitions()
    suite4 = TestAgentCompilation()

    print("Testing kai-code import...")
    suite1.test_import_kai_code()
    print("✓ kai-code imports successfully")

    print("\nTesting StockAI tools import...")
    suite1.test_import_stockai_tools()
    print("✓ StockAI tools imported (15 tools)")

    print("\nTesting agent listing...")
    suite1.test_list_agents()
    print("✓ Found 4 agents: stockai, stockai-analyst, stockai-trader, stockai-risk")

    print("\nTesting agent loading...")
    suite1.test_load_stockai_agent()
    print("✓ stockai agent loaded")
    suite1.test_load_stockai_analyst()
    print("✓ stockai-analyst agent loaded")
    suite1.test_load_stockai_trader()
    print("✓ stockai-trader agent loaded")
    suite1.test_load_stockai_risk()
    print("✓ stockai-risk agent loaded")

    print("\nTesting agent tools...")
    suite1.test_agent_tools()
    print("✓ Agents have tools available")

    print("\nTesting tool definitions...")
    suite2.test_tool_definitions()
    print("✓ All tools properly defined")

    print("\nTesting tool schemas...")
    suite2.test_tool_schemas()
    print("✓ Tools have proper schemas")

    print("\nTesting agent files...")
    suite3.test_stockai_agent_file_exists()
    print("✓ stockai.md exists")
    suite3.test_stockai_analyst_file_exists()
    print("✓ stockai-analyst.md exists")
    suite3.test_stockai_trader_file_exists()
    print("✓ stockai-trader.md exists")
    suite3.test_stockai_risk_file_exists()
    print("✓ stockai-risk.md exists")

    print("\nTesting agent file content...")
    suite3.test_agent_file_content()
    print("✓ Agent files have required YAML frontmatter")

    print("\nTesting agent compilation...")
    suite4.test_compile_stockai_agent()
    print("✓ Agent compiles to Python class")

    print("\n" + "="*60)
    print("✓ ALL TESTS PASSED")
    print("="*60)
    print("\nStockAI kai-code integration is working correctly!")
    print("\nAvailable agents:")
    print("  - stockai (main)")
    print("  - stockai-analyst (specialist)")
    print("  - stockai-trader (specialist)")
    print("  - stockai-risk (specialist)")
    print("\nAvailable tools: 15")
    print("  - Analysis: quality, analyze, risk_position")
    print("  - Trading: autopilot, portfolio_buy/sell/view")
    print("  - Risk: risk_diversification, risk_portfolio")
    print("  - AI Agents: scan, recommend, daily")
    print("  - Briefings: morning, evening, weekly")
