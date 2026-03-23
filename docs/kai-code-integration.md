# StockAI + Kai-Code Integration

This document describes the integration of **kai-code** (agent layer library) into **StockAI** for intelligent stock trading assistance.

## Overview

StockAI now includes kai-code agents that provide AI-powered assistance for:
- **Stock Analysis**: Comprehensive 6-gate quality filter analysis
- **Trading Decisions**: Buy/sell recommendations with position sizing
- **Portfolio Management**: Paper trading with risk controls
- **Risk Management**: Professional 2% risk rule enforcement

## Agent Architecture

```
stockai (Main Agent)
├── stockai-analyst (Subagent)
│   └── Deep fundamental & technical analysis
├── stockai-trader (Subagent)
│   └── Execution & position management
└── stockai-risk (Subagent)
    └── Risk management & portfolio protection
```

## Installation

Kai-code is integrated as a local dependency in `pyproject.toml`:

```toml
dependencies = [
    "kai-code @ file:///Users/fitrakacamarga/project/self/bmad-new/kai-code-1",
    ...
]
```

## Available Agents

### 1. stockai (Main Agent)

**Purpose**: AI-powered Indonesian stock trading specialist

**Use for**:
- General trading guidance
- Daily workflow recommendations
- Coordinating specialist subagents
- Portfolio overview

**Example**:
```python
from kai_code.agent_loader import load_agent

agent = load_agent('stockai')
agent.run("What should I buy today?")
```

### 2. stockai-analyst (Specialist)

**Purpose**: Deep analysis using 6-gate quality filter

**Use for**:
- Comprehensive stock analysis
- Multi-factor scoring breakdown
- Technical & fundamental assessment
- Investment thesis development

**Example**:
```python
agent = load_agent('stockai-analyst')
agent.run("Analyze BBCA in detail")
```

**Output Includes**:
- Overall score (0-100)
- 6-gate status (all must pass)
- Technical indicators
- Fundamental metrics
- Smart money analysis
- Clear recommendation with levels

### 3. stockai-trader (Specialist)

**Purpose**: Trading execution and position management

**Use for**:
- Buy/sell decisions
- Position sizing (2% risk rule)
- Portfolio management
- Trade execution planning

**Example**:
```python
agent = load_agent('stockai-trader')
agent.run("Should I buy BBCA at 9500?")
```

**Output Includes**:
- Trade recommendation (BUY/SELL/HOLD)
- Exact position size
- Entry, stop-loss, take-profit levels
- Risk validation
- Execution command

### 4. stockai-risk (Specialist)

**Purpose**: Risk management and portfolio protection

**Use for**:
- Portfolio risk assessment
- Position size validation
- Sector exposure analysis
- Stress testing scenarios

**Example**:
```python
agent = load_agent('stockai-risk')
agent.run("Check my portfolio risk")
```

**Output Includes**:
- Portfolio risk metrics (beta, volatility, drawdown)
- Concentration analysis
- Correlation assessment
- Risk warnings
- Mitigation recommendations

## Available Tools

All agents have access to 15 StockAI tools:

### Analysis Tools
- `stockai_quality SYMBOL` - Full 6-gate analysis
- `stockai_analyze SYMBOL` - Quick technical/fundamental check
- `stockai_risk_position SYMBOL` - Position-specific risk

### Trading Tools
- `stockai_autopilot` - Full trading workflow
- `stockai_portfolio_buy` - Buy shares
- `stockai_portfolio_sell` - Sell shares
- `stockai_portfolio_view` - View positions

### Risk Tools
- `stockai_risk_diversification` - Sector allocation check
- `stockai_risk_portfolio` - Overall portfolio risk

### AI Agent Tools
- `stockai_agents_scan` - Discover opportunities
- `stockai_agents_recommend` - AI-validated picks
- `stockai_agents_daily` - Daily AI insights

### Briefing Tools
- `stockai_briefing_morning` - Pre-market prep
- `stockai_briefing_evening` - Daily review
- `stockai_briefing_weekly` - Weekly performance

## Usage Examples

### Example 1: Daily Trading Workflow

```python
from kai_code.agent_loader import load_agent

# Load main agent
agent = load_agent('stockai')

# Morning routine
agent.run("What's my morning briefing?")

# Market scan
agent.run("Run autopilot to find opportunities")

# Analyze specific stock
agent.run("Should I buy BBCA?")

# Evening review
agent.run("What's my evening briefing?")
```

### Example 2: Deep Stock Analysis

```python
from kai_code.agent_loader import load_agent

# Load analyst agent
agent = load_agent('stockai-analyst')

# Comprehensive analysis
agent.run("Analyze BBCA and give me a full report")
agent.run("Compare BBCA vs BMRI")
agent.run("Is TLKM a buy right now?")
```

### Example 3: Portfolio Risk Check

```python
from kai_code.agent_loader import load_agent

# Load risk manager agent
agent = load_agent('stockai-risk')

# Risk assessment
agent.run("Check my portfolio risk")
agent.run("Am I too concentrated in banking?")
agent.run("Is my portfolio properly diversified?")
```

### Example 4: Trade Execution

```python
from kai_code.agent_loader import load_agent

# Load trader agent
agent = load_agent('stockai-trader')

# Trading decisions
agent.run("Should I buy BBCA at 9500 with 2% risk?")
agent.run("Should I sell my TLKM position?")
agent.run("How's my portfolio doing today?")
```

## CLI Integration

You can also use agents via the kai-code CLI (if available):

```bash
# List available agents
kai-code list-agents

# Compile agent to Python
kai-code compile-agent .kai/agents/stockai.md

# Validate agent definition
kai-code validate-agent .kai/agents/stockai.md
```

## Agent Delegation

The main `stockai` agent automatically delegates to specialists:

1. **User asks**: "Analyze BBCA for investment"
2. **stockai** recognizes need for deep analysis
3. **Delegates to stockai-analyst**
4. **stockai-analyst** provides comprehensive report
5. **stockai** synthesizes and presents to user

## Trading Methodology

All agents follow StockAI's proven methodology:

### 6-Gate Quality Filter

All BUY recommendations must pass:
1. Overall Score ≥ 70
2. Technical Score ≥ 60
3. Smart Money Score ≥ 3.0
4. Distance to Support ≤ 5%
5. ADX Trend Strength ≥ 20
6. Fundamental Score ≥ 60

### Risk Management

- **2% Risk Rule**: Never risk more than 2% per trade
- **Position Limits**: Max 20% per stock, 40% per sector
- **Stop-Losses**: ATR-based (2x multiplier) or 8% fallback
- **Take-Profit**: 1.5x stop distance (1:1.5 risk/reward)

### Daily Workflow

1. **Morning** (5 min): Pre-market alerts and watchlist
2. **Scan** (15 min): Find opportunities with autopilot
3. **Analyze** (5 min/stock): Deep dive into candidates
4. **Evening** (5 min): Daily P&L and position review
5. **Weekly** (30 min): Performance analysis and learning

## Important Notes

### Paper Trading Only
- All agents use paper trading (no real money)
- Great for learning and testing strategies
- Verify strategies before real trading

### Indonesian Market Context
- All stocks use `.JK` suffix (e.g., BBCA.JK)
- Default index: IDX30
- Trading hours: 08:30-15:00 WIB
- Currency: Indonesian Rupiah (IDR)

### Risk Disclaimer
- ⚠️ **Past performance ≠ future results**
- 📊 **Scores are indicators, not guarantees**
- 💼 **Do your own research** before real trading
- 📉 **Markets can go down** as well as up

## File Structure

```
stockai/
├── .kai/
│   └── agents/
│       ├── stockai.md              # Main agent
│       ├── stockai-analyst.md      # Analysis specialist
│       ├── stockai-trader.md       # Trading specialist
│       └── stockai-risk.md         # Risk management specialist
├── src/stockai/
│   └── kai_tools/
│       └── __init__.py            # StockAI tools for kai-code
├── pyproject.toml                  # Kai-code dependency
└── docs/
    └── kai-code-integration.md     # This file
```

## Development

### Adding New Tools

Add new tools in `src/stockai/kai_tools/__init__.py`:

```python
from langchain_core.tools import tool

@tool("stockai_new_tool")
def stockai_new_tool(param: str) -> str:
    """Tool description for agent."""
    # Implementation
    return result
```

### Creating New Agents

Create new agent in `.kai/agents/`:

```markdown
---
name: stockai-specialist
description: Specialist description
extends: stockai
tools:
  - stockai.kai_tools
model: gemini-3-flash-preview
---

# Purpose
[Agent instructions...]
```

### Testing Agents

```python
from kai_code.agent_loader import load_agent

# Load and test
agent = load_agent('stockai-specialist')
result = agent.run("Test prompt")
print(result)
```

## Support

For issues or questions:
1. Check kai-code documentation: `kai-code/docs/`
2. Review agent definitions: `.kai/agents/*.md`
3. Test tools: `from stockai.kai_tools import *`
4. Check StockAI docs: `stockai/README.md`

## Roadmap

Future enhancements:
- [ ] Real-time market data integration
- [ ] Multi-timeframe analysis
- [ ] Backtesting integration
- [ ] Strategy optimization
- [ ] Real trading mode (with safeguards)

---

**Built with Kai-Code** - Agent Layer Library for Python

StockAI leverages kai-code's agent system to provide intelligent, context-aware assistance for Indonesian stock trading.
