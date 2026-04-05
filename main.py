"""Entry point for the TradingAgentsClaude multi-agent workflow.

Usage:
    python main.py                     # defaults: NVDA, 2025-04-01
    python main.py AAPL 2025-03-15     # custom ticker and date
"""

from __future__ import annotations

import asyncio
import sys

from tradingagents.config import DEFAULT_CONFIG
from tradingagents.workflow import TradingWorkflow


async def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    trade_date = sys.argv[2] if len(sys.argv) > 2 else "2025-04-01"

    config = DEFAULT_CONFIG.copy()
    # Adjust as needed:
    # config["max_debate_rounds"] = 2
    # config["deep_think_model"] = "claude-sonnet-4-20250514"

    wf = TradingWorkflow(config=config)
    state = await wf.run(company=ticker, trade_date=trade_date)

    # Print final results
    print("\n" + "=" * 70)
    print(f"TRADING ANALYSIS COMPLETE: {ticker} ({trade_date})")
    print("=" * 70)

    print("\n--- MARKET REPORT ---")
    print(state.market_report[:500] + "..." if len(state.market_report) > 500 else state.market_report)

    print("\n--- SENTIMENT REPORT ---")
    print(state.sentiment_report[:500] + "..." if len(state.sentiment_report) > 500 else state.sentiment_report)

    print("\n--- NEWS REPORT ---")
    print(state.news_report[:500] + "..." if len(state.news_report) > 500 else state.news_report)

    print("\n--- FUNDAMENTALS REPORT ---")
    print(state.fundamentals_report[:500] + "..." if len(state.fundamentals_report) > 500 else state.fundamentals_report)

    print("\n--- INVESTMENT PLAN ---")
    print(state.investment_plan)

    print("\n--- TRADE PROPOSAL ---")
    print(state.trade_proposal)

    print("\n" + "=" * 70)
    print("FINAL PORTFOLIO DECISION")
    print("=" * 70)
    print(state.final_decision)


if __name__ == "__main__":
    asyncio.run(main())
