# TradingAgents: Multi-Agent Trading Analysis Skill

A [Claude Code](https://claude.ai/code) skill that orchestrates 10+ specialized AI agents to simulate a professional trading firm. Inspired by the [TradingAgents](https://arxiv.org/abs/2412.20138) research framework, it produces comprehensive stock analysis through structured collaboration, adversarial debate, and sequential review.

> **Disclaimer**: This is an AI research tool for educational purposes only. It is not financial advice. Always consult a qualified financial advisor before making investment decisions.

## How It Works

When you ask Claude Code to analyze a stock, the skill deploys a swarm of subagents that mirror the roles of a real trading desk:

```
                          User: "Analyze NVDA"
                                 |
                    +------------+------------+
                    |            |            |            Stage 1
              Fundamental   Technical   Sentiment   News   (parallel)
               Analyst       Analyst     Analyst   Analyst
                    |            |            |            |
                    +------------+-----+------+------------+
                                       |
                              +--------+--------+
                              |                 |          Stage 2
                         Bull Researcher   Bear Researcher (debate)
                              |                 |
                              +--------+--------+
                                       |
                              Research Manager
                                       |
                                    Trader                 Stage 3
                                       |
                                 Risk Manager              Stage 4
                                       |
                              Portfolio Manager            Stage 5
                                       |
                              Final Recommendation
```

### The Five Stages

| Stage                     | Agents                                             | What Happens                                                                                                                                 |
| ------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Analysis**           | Fundamental, Technical, Sentiment, News Analysts   | Four analysts run **in parallel**, each gathering data through MCP data sources, web search, and yfinance, producing structured reports.                        |
| **2. Research Debate**    | Bull Researcher, Bear Researcher, Research Manager | Bull and bear researchers argue in configurable rounds (default: 1). A research manager then synthesizes the debate into a balanced summary. |
| **3. Trading Decision**   | Trader                                             | Synthesizes all reports into a concrete BUY / SELL / HOLD recommendation with entry/exit points and position sizing.                         |
| **4. Risk Review**        | Risk Manager                                       | Evaluates position risk, volatility, event risk, concentration risk, and downside scenarios.                                                 |
| **5. Portfolio Approval** | Portfolio Manager                                  | Makes the final APPROVE / MODIFY / REJECT decision, considering the full picture.                                                            |

## Installation

### Prerequisites

- [Claude Code](https://claude.ai/code) (CLI, desktop app, or IDE extension)
- Python 3.9+ (for the helper scripts)

### Install the Skill

Add this skill to your Claude Code configuration. In your project's `.claude/settings.json`:

```json
{
  "skills": ["/path/to/trading-agents.skill"]
}
```

Or add it to your user-level settings at `~/.claude/settings.json` to make it available globally.

The helper scripts auto-install their Python dependencies (`yfinance`, `numpy`) on first run.

## Usage

Just ask Claude Code to analyze a stock. The skill triggers automatically when you mention stock analysis, trading decisions, or investment recommendations.

### Example Prompts

**Basic analysis:**

```
Analyze NVDA for me. Is now a good time to buy?
```

**With debate rounds:**

```
Run a full analysis on TSLA with 3 rounds of bull/bear debate.
```

**With investor context:**

```
Analyze AAPL. I'm a conservative investor with a long-term horizon
and I already hold several tech stocks.
```

**In Chinese:**

```
帮我分析一下特斯拉（TSLA）的股票，我想知道现在该买入还是卖出。
```

### What You Get

1. **Individual analyst reports** saved to your workspace:
   - `fundamental_analysis.md` — Valuation, financial health, earnings quality
   - `technical_analysis.md` — Price action, indicators (RSI, MACD, Bollinger Bands), support/resistance
   - `sentiment_analysis.md` — Social media mood, analyst ratings, institutional sentiment
   - `news_analysis.md` — Recent developments, macro context, upcoming catalysts

2. **Debate record** (`debate_record.md`) — The full bull vs. bear adversarial debate

3. **Research summary** (`research_summary.md`) — Balanced synthesis by the research manager

4. **Trading recommendation** (`trading_recommendation.md`) — BUY/SELL/HOLD with entry/exit strategy

5. **Risk assessment** (`risk_assessment.md`) — Risk rating with downside scenarios

6. **Portfolio decision** (`portfolio_decision.md`) — Final go/no-go from the portfolio manager

7. **A conversational summary** in the chat with the final recommendation, top reasons, key risks, and confidence level

## Agents

| Agent                   | Role                                                                           | Data Sources                                                  |
| ----------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| **Fundamental Analyst** | Evaluates financial health, valuation, earnings quality, competitive position  | MCP data sources (S&P Global, FactSet, Daloopa, Morningstar, LSEG), SEC filings, company IR pages |
| **Technical Analyst**   | Analyzes price patterns, momentum indicators, volume, volatility               | yfinance, technical indicators script, chart pattern analysis |
| **Sentiment Analyst**   | Gauges market mood from social media, analyst ratings, institutional flows     | Reddit, Twitter/X, StockTwits, analyst reports, 13F filings   |
| **News Analyst**        | Evaluates recent news, macro events, industry developments, upcoming catalysts | Reuters, Bloomberg, FT, WSJ, company announcements            |
| **Bull Researcher**     | Builds the strongest possible case FOR the investment                          | All analyst reports + previous debate rounds                  |
| **Bear Researcher**     | Builds the strongest possible case AGAINST the investment                      | All analyst reports + previous debate rounds                  |
| **Research Manager**    | Objectively synthesizes the bull/bear debate                                   | Debate transcripts + analyst reports                          |
| **Trader**              | Produces actionable BUY/SELL/HOLD with position sizing                         | All reports + research summary                                |
| **Risk Manager**        | Evaluates risk: position size, volatility, events, tail risk                   | Trading recommendation + all reports                          |
| **Portfolio Manager**   | Final decision maker: APPROVE / MODIFY / REJECT                                | Everything above                                              |

## Helper Scripts

One Python script supports the technical analyst agent:

```bash
# Compute RSI, MACD, Bollinger Bands, moving averages, and more
python scripts/technical_indicators.py TICKER [-o OUTPUT_DIR]
```

The script auto-installs `yfinance` (and `numpy`) if not present. Output is JSON.

## Project Structure

```
trading-agents.skill/
├── SKILL.md                          # Skill definition and orchestration logic
├── CLAUDE.md                         # Claude Code project instructions
├── agents/
│   ├── fundamental_analyst.md        # Financial health & valuation
│   ├── technical_analyst.md          # Price action & indicators
│   ├── sentiment_analyst.md          # Market mood & sentiment
│   ├── news_analyst.md               # News & macro events
│   ├── bull_researcher.md            # Bullish advocate
│   ├── bear_researcher.md            # Bearish skeptic
│   ├── research_manager.md           # Debate synthesizer
│   ├── trader.md                     # Trading decision maker
│   ├── risk_manager.md               # Risk evaluator
│   └── portfolio_manager.md          # Final approver
├── scripts/
│   └── technical_indicators.py       # Technical indicator calculator (includes price fetching)
└── evals/
    └── evals.json                    # Evaluation test prompts
```

## Data Quality Standards

All reports follow strict citation requirements:

- **Primary sources first**: Company filings, exchange announcements, official earnings releases
- **Every data point cites its source** with a clickable URL, reporting period, and currency/unit
- **News from authoritative media**: Reuters, Bloomberg, FT, WSJ, Caixin, Yicai (prioritized over blogs/social media)
- **Sentiment claims are attributed** to specific sources, not vague generalizations
- **Technical indicators include plain-language explanations** for non-expert readers

## Cost Awareness

Each full analysis spawns **8-12+ subagents**, each making multiple tool calls (web searches, script executions, file writes). For multi-ticker requests, consider analyzing one at a time.

## Based On

This skill is inspired by the TradingAgents framework described in:

> **TradingAgents: Multi-Agents LLM Financial Trading Framework**
> Li, Y., Peng, G., et al. (2024). arXiv:2412.20138
> [https://arxiv.org/abs/2412.20138](https://arxiv.org/abs/2412.20138)

## License

This project is provided as-is for educational and research purposes.
