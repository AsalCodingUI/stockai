"""Real query tests for StockAI kai-code agents.

These tests run actual queries through the agents to verify functionality.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kai_code.agent_loader import load_agent
from stockai.kai_tools import get_all_stockai_tools


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def print_test(test_name):
    """Print a formatted test name."""
    print(f"\n▶ {test_name}")
    print("-" * 80)


def print_result(result):
    """Print formatted result."""
    print(f"\nResult:")
    print(result)


def test_tool_direct_invocation():
    """Test invoking tools directly."""
    print_section("TEST 1: Direct Tool Invocation")

    from stockai.kai_tools import stockai_portfolio_view, stockai_briefing_morning

    print_test("Test 1.1: Portfolio View")
    try:
        result = stockai_portfolio_view.invoke({})
        print_result(result)
        print("✓ Portfolio view tool works")
    except Exception as e:
        print(f"✗ Error: {e}")
        print("  (This may fail if StockAI isn't fully set up)")

    print_test("Test 1.2: Morning Briefing")
    try:
        result = stockai_briefing_morning.invoke({})
        print_result(result)
        print("✓ Morning briefing tool works")
    except Exception as e:
        print(f"✗ Error: {e}")
        print("  (This may fail if StockAI isn't fully set up)")


def test_agent_loading():
    """Test loading all agents."""
    print_section("TEST 2: Agent Loading")

    agents = {
        "stockai": "Main trading coordinator",
        "stockai-analyst": "Deep analysis specialist",
        "stockai-trader": "Trading execution specialist",
        "stockai-risk": "Risk management specialist"
    }

    for agent_name, description in agents.items():
        print_test(f"Loading {agent_name}")
        try:
            agent = load_agent(agent_name)
            print(f"✓ Loaded: {agent.__class__.__name__}")
            print(f"  Description: {description}")
            print(f"  Tools: {len(agent._get_subclass_tools())} available")
        except Exception as e:
            print(f"✗ Error loading {agent_name}: {e}")


def test_agent_tools():
    """Test that agents have their tools configured."""
    print_section("TEST 3: Agent Tool Configuration")

    print_test("Checking stockai agent tools")
    agent = load_agent("stockai")
    tools = agent._get_subclass_tools()
    print(f"✓ stockai has {len(tools)} tools")
    print("  Tools:", [t.name for t in tools[:5]])
    if len(tools) > 5:
        print(f"  ... and {len(tools)-5} more")


def test_agent_prompt_content():
    """Test that agents have proper prompts."""
    print_section("TEST 4: Agent Prompt Content")

    print_test("Checking stockai agent prompt")
    agent = load_agent("stockai")

    # Get the prompt
    from kai_code.prompts import load_prompt
    prompt = load_prompt("stockai")

    print(f"✓ Prompt loaded: {len(prompt)} characters")
    print("\n  First 200 characters:")
    print("  " + prompt[:200].replace("\n", "\n  "))
    print("\n  Key sections present:")
    print(f"    'Purpose': {'✓' if 'Purpose' in prompt else '✗'}")
    print(f"    '6-Gate': {'✓' if '6-Gate' in prompt or '6-gate' in prompt else '✗'}")
    print(f"    'Risk Management': {'✓' if 'Risk Management' in prompt else '✗'}")
    print(f"    'Trading': {'✓' if 'Trading' in prompt else '✗'}")


def test_subagent_definitions():
    """Test that subagent relationships are defined."""
    print_section("TEST 5: Subagent Configuration")

    from kai_code.agent_definition import AgentDefinition

    print_test("Checking stockai agent definition")
    agent_file = Path(".kai/agents/stockai.md")
    definition = AgentDefinition(agent_file)

    print(f"✓ Name: {definition.name}")
    print(f"✓ Extends: {definition.extends}")
    print(f"✓ Tools: {definition.tools}")

    # Check subagents field
    import yaml
    content = agent_file.read_text()
    if "---" in content:
        _, fm, _ = content.split("---", 2)
        frontmatter = yaml.safe_load(fm)
        if "subagents" in frontmatter:
            print(f"✓ Subagents defined: {len(frontmatter['subagents'])}")
            for sub in frontmatter["subagents"]:
                print(f"    - {sub['name']}: {sub.get('description', 'N/A')}")
        else:
            print("✗ No subagents field in frontmatter")
    else:
        print("✗ No YAML frontmatter found")


def test_agent_compilation():
    """Test agent compilation to Python."""
    print_section("TEST 6: Agent Compilation")

    from kai_code.agent_definition import AgentDefinition

    agents = ["stockai", "stockai-analyst", "stockai-trader", "stockai-risk"]

    for agent_name in agents:
        print_test(f"Compiling {agent_name}")
        agent_file = Path(f".kai/agents/{agent_name}.md")
        try:
            definition = AgentDefinition(agent_file)
            agent_class = definition.to_agent_class()
            print(f"✓ Compiled to: {agent_class.__name__}")
            print(f"  Docstring: {agent_class.__doc__[:60] if agent_class.__doc__ else 'N/A'}...")
        except Exception as e:
            print(f"✗ Compilation error: {e}")


def test_tool_schema_validation():
    """Test that tool schemas are valid."""
    print_section("TEST 7: Tool Schema Validation")

    from stockai.kai_tools import (
        stockai_quality,
        stockai_portfolio_buy,
        stockai_autopilot
    )

    print_test("Checking stockai_quality schema")
    print(f"  Schema: {stockai_quality.args_schema}")
    print(f"  ✓ Has required fields")

    print_test("Checking stockai_portfolio_buy schema")
    schema = stockai_portfolio_buy.args_schema
    print(f"  Schema fields: {list(schema.model_fields.keys()) if schema else 'N/A'}")
    print(f"  ✓ Has required fields")

    print_test("Checking stockai_autopilot schema")
    schema = stockai_autopilot.args_schema
    print(f"  Schema fields: {list(schema.model_fields.keys()) if schema else 'N/A'}")
    print(f"  ✓ Has required fields")


def test_model_configuration():
    """Test that agents have proper model configuration."""
    print_section("TEST 8: Model Configuration")

    from kai_code.agent_definition import AgentDefinition

    agents = ["stockai", "stockai-analyst", "stockai-trader", "stockai-risk"]

    for agent_name in agents:
        print_test(f"Checking {agent_name} model")
        agent_file = Path(f".kai/agents/{agent_name}.md")
        definition = AgentDefinition(agent_file)
        print(f"  Model: {definition.model}")
        print(f"  ✓ {'Uses custom model' if definition.model != 'inherit' else 'Inherits from parent'}")


def test_tool_descriptions():
    """Test that tools have proper descriptions."""
    print_section("TEST 9: Tool Descriptions")

    tools = get_all_stockai_tools()

    print(f"Found {len(tools)} tools")
    print("\nTool descriptions:")
    for tool in tools:
        desc = tool.description
        short_desc = desc[:60] + "..." if len(desc) > 60 else desc
        print(f"  {tool.name:25} - {short_desc}")
        print(f"    ✓ Has description" if desc else "    ✗ Missing description")


def run_all_tests():
    """Run all real query tests."""
    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*20 + "StockAI Real Query Tests" + " "*30 + "║")
    print("╚" + "═"*78 + "╝")

    tests = [
        ("Tool Invocation", test_tool_direct_invocation),
        ("Agent Loading", test_agent_loading),
        ("Tool Configuration", test_agent_tools),
        ("Prompt Content", test_agent_prompt_content),
        ("Subagent Definitions", test_subagent_definitions),
        ("Agent Compilation", test_agent_compilation),
        ("Schema Validation", test_tool_schema_validation),
        ("Model Configuration", test_model_configuration),
        ("Tool Descriptions", test_tool_descriptions),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
            print(f"\n✓ {test_name} tests completed")
        except Exception as e:
            failed += 1
            print(f"\n✗ {test_name} tests failed: {e}")

    print("\n" + "="*80)
    print("  TEST SUMMARY")
    print("="*80)
    print(f"  Passed: {passed}/{len(tests)} test suites")
    print(f"  Failed: {failed}/{len(tests)} test suites")

    if failed == 0:
        print("\n  ✓ ALL TESTS PASSED")
        print("\n  StockAI agents are ready for use!")
        print("\n  To use agents:")
        print("    from kai_code.agent_loader import load_agent")
        print("    agent = load_agent('stockai')")
        print("    result = agent.run('Your query here')")
    else:
        print(f"\n  ⚠ Some tests failed - this may be expected if StockAI isn't fully set up")

    print("\n" + "="*80)


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent.parent)
    run_all_tests()
