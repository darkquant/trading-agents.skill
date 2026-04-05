"""Multi-agent trading workflow orchestrated via claude-agent-sdk.

Replicates the TradingAgents pipeline:
  Stage 1 — Four analysts gather data using tools
  Stage 2 — Bull / Bear debate → Research Manager judges
  Stage 3 — Trader proposes a specific trade
  Stage 4 — Three-way risk debate → Portfolio Manager makes final decision
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from tradingagents.config import DEFAULT_CONFIG
from tradingagents.prompts import (
    AGGRESSIVE_ANALYST,
    BEAR_RESEARCHER,
    BULL_RESEARCHER,
    CONSERVATIVE_ANALYST,
    FUNDAMENTALS_ANALYST,
    MARKET_ANALYST,
    NEUTRAL_ANALYST,
    NEWS_ANALYST,
    PORTFOLIO_MANAGER,
    RESEARCH_MANAGER,
    SOCIAL_ANALYST,
    TRADER,
)
from tradingagents.tools import create_trading_mcp_server


# ---------------------------------------------------------------------------
# Workflow state — accumulates outputs across stages
# ---------------------------------------------------------------------------

@dataclass
class WorkflowState:
    company: str
    trade_date: str

    # Stage 1 outputs
    market_report: str = ""
    sentiment_report: str = ""
    news_report: str = ""
    fundamentals_report: str = ""

    # Stage 2 outputs
    debate_history: str = ""
    investment_plan: str = ""

    # Stage 3 output
    trade_proposal: str = ""

    # Stage 4 outputs
    risk_debate_history: str = ""
    final_decision: str = ""


# ---------------------------------------------------------------------------
# Helper: run a single agent query and extract the text result
# ---------------------------------------------------------------------------

async def _run_agent(
    prompt: str,
    *,
    system_prompt: str,
    model: str | None = None,
    max_turns: int | None = None,
    max_budget_usd: float | None = None,
    mcp_servers: dict[str, Any] | None = None,
    allowed_tools: list[str] | None = None,
) -> str:
    """Run a single Claude agent and return its text result."""
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        mcp_servers=mcp_servers or {},
        allowed_tools=allowed_tools or [],
        permission_mode="auto",
    )
    result_text = ""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_text = message.result or ""
    return result_text


# ---------------------------------------------------------------------------
# Main Workflow
# ---------------------------------------------------------------------------

class TradingWorkflow:
    """Orchestrates the full multi-agent trading analysis pipeline."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._mcp_server = create_trading_mcp_server()
        self._mcp_servers = {"trading": self._mcp_server}
        self._tool_names = [
            "mcp__trading__get_stock_data",
            "mcp__trading__get_technical_indicators",
            "mcp__trading__get_fundamentals",
            "mcp__trading__get_financial_statements",
            "mcp__trading__get_news",
            "mcp__trading__get_insider_transactions",
        ]

    async def run(self, company: str, trade_date: str) -> WorkflowState:
        """Execute the full pipeline and return the final state."""
        state = WorkflowState(company=company, trade_date=trade_date)

        _log(f"Starting analysis for {company} as of {trade_date}")

        # ---- Stage 1: Analysts (run in parallel) ----
        await self._run_analysts(state)

        # ---- Stage 2: Bull/Bear Debate → Research Manager ----
        await self._run_investment_debate(state)

        # ---- Stage 3: Trader ----
        await self._run_trader(state)

        # ---- Stage 4: Risk Debate → Portfolio Manager ----
        await self._run_risk_debate(state)

        return state

    # ------------------------------------------------------------------
    # Stage 1: Analysts
    # ------------------------------------------------------------------

    async def _run_analysts(self, state: WorkflowState) -> None:
        _log("Stage 1: Running analysts...")

        context = f"Company: {state.company}\nTrade Date: {state.trade_date}"
        model = self.config["quick_think_model"]
        max_turns = self.config["analyst_max_turns"]
        budget = self.config["max_budget_usd"]

        async def run_analyst(system_prompt: str, label: str) -> str:
            _log(f"  -> {label} analyst working...")
            result = await _run_agent(
                prompt=context,
                system_prompt=system_prompt,
                model=model,
                max_turns=max_turns,
                max_budget_usd=budget,
                mcp_servers=self._mcp_servers,
                allowed_tools=self._tool_names,
            )
            _log(f"  <- {label} analyst done ({len(result)} chars)")
            return result

        # Run all four analysts in parallel
        market, sentiment, news, fundamentals = await asyncio.gather(
            run_analyst(MARKET_ANALYST, "Market"),
            run_analyst(SOCIAL_ANALYST, "Sentiment"),
            run_analyst(NEWS_ANALYST, "News"),
            run_analyst(FUNDAMENTALS_ANALYST, "Fundamentals"),
        )

        state.market_report = market
        state.sentiment_report = sentiment
        state.news_report = news
        state.fundamentals_report = fundamentals

    # ------------------------------------------------------------------
    # Stage 2: Investment Debate
    # ------------------------------------------------------------------

    async def _run_investment_debate(self, state: WorkflowState) -> None:
        _log("Stage 2: Investment debate...")

        reports_context = self._format_reports(state)
        model = self.config["deep_think_model"]
        max_turns = self.config["debate_max_turns"]
        budget = self.config["max_budget_usd"]
        rounds = self.config["max_debate_rounds"]

        debate_history = ""

        for round_num in range(1, rounds + 1):
            _log(f"  Debate round {round_num}/{rounds}")

            # Bull argues
            bull_prompt = (
                f"{reports_context}\n\n"
                f"--- DEBATE HISTORY ---\n{debate_history}\n\n"
                f"Present your BULLISH argument (round {round_num})."
            )
            bull_arg = await _run_agent(
                prompt=bull_prompt,
                system_prompt=BULL_RESEARCHER,
                model=model,
                max_turns=max_turns,
                max_budget_usd=budget,
            )
            debate_history += f"\n\n**BULL (Round {round_num}):**\n{bull_arg}"
            _log(f"    Bull argued ({len(bull_arg)} chars)")

            # Bear argues
            bear_prompt = (
                f"{reports_context}\n\n"
                f"--- DEBATE HISTORY ---\n{debate_history}\n\n"
                f"Present your BEARISH argument (round {round_num})."
            )
            bear_arg = await _run_agent(
                prompt=bear_prompt,
                system_prompt=BEAR_RESEARCHER,
                model=model,
                max_turns=max_turns,
                max_budget_usd=budget,
            )
            debate_history += f"\n\n**BEAR (Round {round_num}):**\n{bear_arg}"
            _log(f"    Bear argued ({len(bear_arg)} chars)")

        state.debate_history = debate_history

        # Research Manager judges
        _log("  Research Manager judging...")
        judge_prompt = (
            f"{reports_context}\n\n"
            f"--- COMPLETE DEBATE ---\n{debate_history}\n\n"
            f"Please evaluate both sides and deliver your recommendation."
        )
        state.investment_plan = await _run_agent(
            prompt=judge_prompt,
            system_prompt=RESEARCH_MANAGER,
            model=model,
            max_turns=self.config["manager_max_turns"],
            max_budget_usd=budget,
        )
        _log(f"  Research Manager decided ({len(state.investment_plan)} chars)")

    # ------------------------------------------------------------------
    # Stage 3: Trader
    # ------------------------------------------------------------------

    async def _run_trader(self, state: WorkflowState) -> None:
        _log("Stage 3: Trader proposing trade...")

        reports_context = self._format_reports(state)
        model = self.config["deep_think_model"]

        trader_prompt = (
            f"{reports_context}\n\n"
            f"--- INVESTMENT PLAN ---\n{state.investment_plan}\n\n"
            f"Based on the above, propose a specific trade."
        )
        state.trade_proposal = await _run_agent(
            prompt=trader_prompt,
            system_prompt=TRADER,
            model=model,
            max_turns=self.config["manager_max_turns"],
            max_budget_usd=self.config["max_budget_usd"],
        )
        _log(f"  Trader proposed ({len(state.trade_proposal)} chars)")

    # ------------------------------------------------------------------
    # Stage 4: Risk Debate
    # ------------------------------------------------------------------

    async def _run_risk_debate(self, state: WorkflowState) -> None:
        _log("Stage 4: Risk analysis debate...")

        model = self.config["deep_think_model"]
        max_turns = self.config["debate_max_turns"]
        budget = self.config["max_budget_usd"]
        rounds = self.config["max_risk_discuss_rounds"]

        trade_context = (
            f"--- TRADE PROPOSAL ---\n{state.trade_proposal}\n\n"
            f"--- INVESTMENT PLAN ---\n{state.investment_plan}"
        )

        risk_history = ""
        speakers = [
            ("Aggressive", AGGRESSIVE_ANALYST),
            ("Conservative", CONSERVATIVE_ANALYST),
            ("Neutral", NEUTRAL_ANALYST),
        ]

        for round_num in range(1, rounds + 1):
            _log(f"  Risk debate round {round_num}/{rounds}")
            for label, system_prompt in speakers:
                prompt = (
                    f"{trade_context}\n\n"
                    f"--- RISK DEBATE HISTORY ---\n{risk_history}\n\n"
                    f"Present your {label.lower()} perspective (round {round_num})."
                )
                arg = await _run_agent(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=model,
                    max_turns=max_turns,
                    max_budget_usd=budget,
                )
                risk_history += f"\n\n**{label.upper()} (Round {round_num}):**\n{arg}"
                _log(f"    {label} analyst argued ({len(arg)} chars)")

        state.risk_debate_history = risk_history

        # Portfolio Manager makes final decision
        _log("  Portfolio Manager deciding...")
        pm_prompt = (
            f"{trade_context}\n\n"
            f"--- COMPLETE RISK DEBATE ---\n{risk_history}\n\n"
            f"Make your final portfolio decision."
        )
        state.final_decision = await _run_agent(
            prompt=pm_prompt,
            system_prompt=PORTFOLIO_MANAGER,
            model=self.config["deep_think_model"],
            max_turns=self.config["manager_max_turns"],
            max_budget_usd=budget,
        )
        _log(f"  Portfolio Manager decided ({len(state.final_decision)} chars)")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_reports(self, state: WorkflowState) -> str:
        return (
            f"=== ANALYST REPORTS FOR {state.company} (as of {state.trade_date}) ===\n\n"
            f"--- MARKET REPORT ---\n{state.market_report}\n\n"
            f"--- SENTIMENT REPORT ---\n{state.sentiment_report}\n\n"
            f"--- NEWS REPORT ---\n{state.news_report}\n\n"
            f"--- FUNDAMENTALS REPORT ---\n{state.fundamentals_report}"
        )


def _log(msg: str) -> None:
    print(f"[TradingAgents] {msg}", file=sys.stderr)
