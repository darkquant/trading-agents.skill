# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TradingAgentsClaude is a multi-agent trading analysis system built on `claude-agent-sdk`. It replicates the TradingAgents (LangGraph-based) pipeline using Claude's native agent SDK instead.

## Commands

```bash
# Run the workflow (defaults to NVDA, 2025-04-01)
python main.py

# Run with custom ticker and date
python main.py AAPL 2025-03-15

# Run tests
pytest

# Install dependencies
uv sync
```

## Architecture

The system is a 4-stage sequential pipeline where each stage's output feeds into the next, managed by `TradingWorkflow` in `tradingagents/workflow.py`:

**Stage 1 — Analysts (parallel):** Four analyst agents run concurrently via `asyncio.gather`, each using MCP tools to fetch yfinance data. They produce independent reports (market, sentiment, news, fundamentals).

**Stage 2 — Investment Debate (sequential):** Bull and Bear researchers argue in alternating rounds using the analyst reports. A Research Manager judges the debate and outputs an investment plan (BUY/SELL/HOLD).

**Stage 3 — Trader:** Translates the investment plan into a concrete trade proposal with conviction level and time horizon.

**Stage 4 — Risk Debate (sequential):** Three risk analysts (Aggressive, Conservative, Neutral) debate the trade proposal in rotating rounds. A Portfolio Manager synthesizes all inputs into a final rated decision (BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL).

### Key patterns

- **State passing:** `WorkflowState` dataclass accumulates outputs across stages. Each agent receives relevant prior state as text in its prompt — there is no shared memory or message history between agents.
- **Agent calls:** Each agent is a one-shot `claude_agent_sdk.query()` call with a system prompt and formatted context. No `ClaudeSDKClient` sessions are used.
- **Tools:** Six yfinance data tools are packaged as an in-process MCP server (`create_sdk_mcp_server`). Only Stage 1 analyst agents have tool access; all other agents are pure reasoning.
- **Models:** Config uses `deep_think_model` for debate/reasoning agents and `quick_think_model` for data-gathering analysts.
