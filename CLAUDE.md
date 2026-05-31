# Claude Code Instructions

## Running the CLI

This project uses `uv` for dependency management and running the CLI.

### Command Format

**Preferred (with uv):**
```bash
uv run stockai <command>
```

**Alternative (if uv not available):**
```bash
python -m stockai.cli.main <command>
```

### Available Commands

- `uv run stockai evening` - Run the evening briefing
- `uv run stockai morning` - Run the morning briefing
- `uv run stockai autopilot` - Run autopilot mode
- `uv run stockai backtest` - Run backtesting
- `uv run stockai monitor` - Monitor portfolio
- `uv run stockai portfolio summary` - Show portfolio P&L summary

### Important

- Prefer `uv run stockai` for proper dependency resolution
- If uv is unavailable, use `python -m stockai.cli.main` from the project root

## Design System

**ALWAYS read `design.md` before making any UI/CSS/HTML changes.**

The file `design.md` (at the project root) defines the canonical design language for StockAI's web UI — a Miro-inspired design system adapted for dark mode. Key rules:

- All buttons & pill tabs MUST use `border-radius: 9999px` (pill shape)
- Brand yellow `#FFD02F` → wordmark/logo ONLY, never CTA backgrounds
- Cards: `border-radius: 16px` standard; pastel cards `28px`
- Color tokens from `design-system.css` (e.g. `--miro-yellow`, `--miro-blue`, `--color-hairline`)
- Dark mode always: canvas `#010102`, surface `#0F1011`
