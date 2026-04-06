# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

This is a **Claude Code Skill** (not a standalone application). The `SKILL.md` file defines a multi-agent trading analysis pipeline that orchestrates 10+ Claude subagents to simulate a professional trading firm. It is triggered when users ask about stock analysis, trading decisions, or investment recommendations.

## Architecture

The skill runs a **five-stage sequential pipeline** where each stage spawns subagents via the Agent tool:

1. **Analysis** (parallel) — 4 analyst agents run simultaneously: fundamental, technical, sentiment, news
2. **Research debate** — Bull and bear researchers argue in configurable rounds (default: 1), then a research manager synthesizes
3. **Trading decision** — Trader agent produces BUY/SELL/HOLD with position sizing
4. **Risk review** — Risk manager evaluates the proposed trade
5. **Portfolio approval** — Portfolio manager makes final go/no-go call

Agent prompts use `{TICKER}`, `{DATE}`, `{SKILL_PATH}`, and `{OUTPUT_DIR}` as template placeholders.

## Key Files

- `SKILL.md` — The skill definition and orchestration instructions (the "main" file)
- `agents/*.md` — Individual agent prompts (10 agents total)
- `scripts/technical_indicators.py` — Fetches price history via yfinance (with akshare fallback) and computes RSI, MACD, Bollinger Bands, moving averages, etc.
- `evals/evals.json` — Test prompts for evaluating the skill

## Data Sources

The fundamental analyst uses **MCP data sources** from the [financial-analysis](https://github.com/anthropics/financial-services-plugins/tree/main/financial-analysis) plugin as its primary data source. When available, the following MCP servers provide institutional-grade financial data:

- **S&P Global (Kensho)**, **FactSet**, **Daloopa**, **Morningstar**, **Moody's**, **LSEG**, **Aiera**, **MT Newswires**

The technical analyst uses `scripts/technical_indicators.py` for price history and indicator computation.

## Prerequisites

This skill requires **Python**, **pip**, and **uv** preinstalled. Before running any analysis:

```bash
pip install -U uv  # Install/upgrade uv
uv sync            # Install project dependencies from pyproject.toml
```

## Running the Helper Scripts

All Python scripts must be executed with `uv run` to use the managed virtual environment:

```bash
uv run scripts/technical_indicators.py TICKER [-o OUTPUT_DIR]
```

It outputs a JSON file named `{TICKER}_technical_indicators.json`.

## Git Conventions

- Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) format (e.g., `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`)
- Always commit with `--signoff` (`-s`) flag to add a `Signed-off-by` trailer

## Important Conventions

- All analyst reports must cite sources with clickable URLs, reporting periods, and currency/units
- Reports must never contain internal file system paths — reference other reports by filename only
- The final output always includes a disclaimer that this is AI-generated analysis, not financial advice
- The skill supports both English and Chinese language requests
- Each full analysis spawns 8-12+ subagents; warn users about computational cost for multi-ticker requests
