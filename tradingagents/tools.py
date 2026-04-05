"""YFinance-based market data tools exposed as an in-process MCP server."""

from __future__ import annotations

from typing import Annotated, Any

import yfinance as yf

from claude_agent_sdk import create_sdk_mcp_server, tool


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

@tool(
    "get_stock_data",
    "Get OHLCV (Open, High, Low, Close, Volume) stock price data for a ticker symbol over a date range.",
    {
        "ticker": Annotated[str, "Stock ticker symbol, e.g. AAPL"],
        "start_date": Annotated[str, "Start date in YYYY-MM-DD format"],
        "end_date": Annotated[str, "End date in YYYY-MM-DD format"],
    },
)
async def get_stock_data(args: dict[str, Any]) -> dict[str, Any]:
    ticker = yf.Ticker(args["ticker"])
    df = ticker.history(start=args["start_date"], end=args["end_date"])
    if df.empty:
        return _text(f"No price data found for {args['ticker']} in the given range.")
    # Return last 30 rows max to keep context manageable
    return _text(df.tail(30).to_string())


@tool(
    "get_technical_indicators",
    "Calculate common technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands) for a stock.",
    {
        "ticker": Annotated[str, "Stock ticker symbol"],
        "start_date": Annotated[str, "Start date YYYY-MM-DD"],
        "end_date": Annotated[str, "End date YYYY-MM-DD"],
    },
)
async def get_technical_indicators(args: dict[str, Any]) -> dict[str, Any]:
    ticker = yf.Ticker(args["ticker"])
    df = ticker.history(start=args["start_date"], end=args["end_date"])
    if df.empty:
        return _text(f"No data for {args['ticker']}.")

    close = df["Close"]
    lines: list[str] = []

    # SMA
    for window in (20, 50, 200):
        sma = close.rolling(window).mean()
        if sma.dropna().empty:
            continue
        lines.append(f"SMA-{window}: {sma.iloc[-1]:.2f}")

    # EMA
    for span in (12, 26):
        ema = close.ewm(span=span, adjust=False).mean()
        lines.append(f"EMA-{span}: {ema.iloc[-1]:.2f}")

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    lines.append(f"MACD: {macd.iloc[-1]:.2f}, Signal: {signal.iloc[-1]:.2f}")

    # RSI (14-period)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    if not rsi.dropna().empty:
        lines.append(f"RSI-14: {rsi.iloc[-1]:.2f}")

    # Bollinger Bands (20-period)
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    if not sma20.dropna().empty:
        lines.append(
            f"Bollinger Bands (20): Upper={sma20.iloc[-1] + 2 * std20.iloc[-1]:.2f}, "
            f"Mid={sma20.iloc[-1]:.2f}, Lower={sma20.iloc[-1] - 2 * std20.iloc[-1]:.2f}"
        )

    lines.append(f"\nLatest Close: {close.iloc[-1]:.2f}")
    return _text("\n".join(lines))


@tool(
    "get_fundamentals",
    "Get fundamental financial data (P/E, market cap, revenue, margins, etc.) for a stock.",
    {"ticker": Annotated[str, "Stock ticker symbol"]},
)
async def get_fundamentals(args: dict[str, Any]) -> dict[str, Any]:
    ticker = yf.Ticker(args["ticker"])
    info = ticker.info
    keys = [
        "marketCap", "trailingPE", "forwardPE", "priceToBook",
        "revenueGrowth", "earningsGrowth", "profitMargins",
        "returnOnEquity", "debtToEquity", "currentRatio",
        "totalRevenue", "totalDebt", "freeCashflow",
        "dividendYield", "beta", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    ]
    lines = [f"{k}: {info.get(k, 'N/A')}" for k in keys]
    return _text("\n".join(lines))


@tool(
    "get_financial_statements",
    "Get income statement, balance sheet, and cash flow statement for a stock.",
    {
        "ticker": Annotated[str, "Stock ticker symbol"],
        "statement": Annotated[str, "One of: income, balance, cashflow"],
    },
)
async def get_financial_statements(args: dict[str, Any]) -> dict[str, Any]:
    ticker = yf.Ticker(args["ticker"])
    stmt_type = args["statement"].lower()
    if stmt_type == "income":
        df = ticker.income_stmt
    elif stmt_type == "balance":
        df = ticker.balance_sheet
    elif stmt_type == "cashflow":
        df = ticker.cashflow
    else:
        return _text(f"Unknown statement type: {stmt_type}. Use income, balance, or cashflow.")
    if df.empty:
        return _text(f"No {stmt_type} data for {args['ticker']}.")
    return _text(df.to_string())


@tool(
    "get_news",
    "Get recent news articles for a stock ticker.",
    {"ticker": Annotated[str, "Stock ticker symbol"]},
)
async def get_news(args: dict[str, Any]) -> dict[str, Any]:
    ticker = yf.Ticker(args["ticker"])
    news = ticker.news or []
    if not news:
        return _text(f"No recent news for {args['ticker']}.")
    lines: list[str] = []
    for item in news[:10]:
        content = item.get("content", {})
        title = content.get("title", "N/A")
        provider = content.get("provider", {}).get("displayName", "Unknown")
        pub_date = content.get("pubDate", "N/A")
        summary = content.get("summary", "")
        lines.append(f"- [{pub_date}] ({provider}) {title}")
        if summary:
            lines.append(f"  {summary[:200]}")
    return _text("\n".join(lines))


@tool(
    "get_insider_transactions",
    "Get recent insider transactions (buys/sells) for a stock.",
    {"ticker": Annotated[str, "Stock ticker symbol"]},
)
async def get_insider_transactions(args: dict[str, Any]) -> dict[str, Any]:
    ticker = yf.Ticker(args["ticker"])
    df = ticker.insider_transactions
    if df is None or df.empty:
        return _text(f"No insider transaction data for {args['ticker']}.")
    return _text(df.head(20).to_string())


# ---------------------------------------------------------------------------
# MCP Server factory
# ---------------------------------------------------------------------------

def create_trading_mcp_server():
    """Create the in-process MCP server with all trading data tools."""
    return create_sdk_mcp_server(
        name="trading",
        version="1.0.0",
        tools=[
            get_stock_data,
            get_technical_indicators,
            get_fundamentals,
            get_financial_statements,
            get_news,
            get_insider_transactions,
        ],
    )


# Helper
def _text(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}
