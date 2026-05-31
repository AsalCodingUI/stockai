# Codex Instructions

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

The file `design.md` (located at the project root) defines the canonical design language for StockAI's web UI. It is a Miro-inspired design system adapted for dark mode. Key rules:

- **Color tokens**: Use CSS variables from `design-system.css` (e.g. `--miro-yellow`, `--miro-canvas`, `--miro-ink`)
- **Buttons**: All buttons and pill tabs MUST use `border-radius: 9999px` (pill shape) — never square corners
- **Cards**: Standard cards use `border-radius: 16px`; pastel feature cards use `border-radius: 28px`
- **Brand yellow** (`#FFD02F`): Reserved ONLY for wordmark/logo, promo banners, and yellow-tag chips — NEVER as a primary CTA background
- **Typography**: Follow the hierarchy defined in `design.md` (hero-display → micro-uppercase)
- **Dark mode**: Background stays dark (`#010102` canvas), all Miro tokens adapted for dark surfaces
- **Spacing**: Use the spacing scale from `design.md` (xxs=4px → hero=120px)

See `design.md` for full token reference, component specs, and do's/don'ts.
