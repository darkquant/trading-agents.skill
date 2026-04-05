#!/usr/bin/env python3
"""
Fetch market data for a given stock ticker.
Primary source: yfinance. Fallback: akshare (for HK, US, and A-share stocks).
Outputs a comprehensive JSON file with price history, financial statements, and key metrics.

Usage: python fetch_market_data.py TICKER [--output OUTPUT_DIR]
"""

import argparse
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


def _retry(func, description: str, retries: int = MAX_RETRIES):
    """Retry a callable with exponential backoff. Returns result or raises last exception."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < retries:
                delay = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                print(f"  Retry {attempt}/{retries} for {description} (waiting {delay}s): {e}")
                time.sleep(delay)
    raise last_error


# ---------------------------------------------------------------------------
# Ticker format detection & conversion
# ---------------------------------------------------------------------------

def _detect_market(ticker: str) -> str:
    """Detect which market a ticker belongs to.
    Returns one of: 'hk', 'us', 'cn_sh', 'cn_sz', 'unknown'.
    """
    t = ticker.upper().strip()
    # Hong Kong: 0883.HK, 1810.HK, 00700.HK
    if t.endswith(".HK"):
        return "hk"
    # Shanghai: 600xxx.SS / 601xxx.SS / 603xxx.SS / 688xxx.SS
    if t.endswith(".SS") or t.endswith(".SH"):
        return "cn_sh"
    # Shenzhen: 000xxx.SZ / 002xxx.SZ / 300xxx.SZ
    if t.endswith(".SZ"):
        return "cn_sz"
    # Pure digits — Chinese stock codes
    if re.match(r"^\d{6}$", t):
        if t.startswith(("6", "9")):
            return "cn_sh"
        else:
            return "cn_sz"
    # HK pure digits (4-5 digits)
    if re.match(r"^\d{4,5}$", t):
        return "hk"
    # Default to US
    return "us"


def _to_akshare_symbol(ticker: str, market: str) -> str:
    """Convert a standard ticker to akshare's expected format."""
    t = ticker.upper().strip()
    if market == "hk":
        # akshare expects 5-digit zero-padded code, e.g. "01810"
        code = re.sub(r"\.HK$", "", t)
        return code.zfill(5)
    elif market in ("cn_sh", "cn_sz"):
        # akshare expects pure 6-digit code, e.g. "000001"
        code = re.sub(r"\.(SS|SH|SZ)$", "", t)
        return code.zfill(6)
    else:
        # US stocks: akshare stock_us_daily uses simple symbol like "AAPL"
        return re.sub(r"\.(US|O|N|OQ)$", "", t)


# ---------------------------------------------------------------------------
# yfinance data fetcher (primary)
# ---------------------------------------------------------------------------

def fetch_data_yfinance(ticker: str) -> dict:
    """Fetch comprehensive market data via yfinance with retry logic."""
    import yfinance as yf

    stock = yf.Ticker(ticker)
    result = {"ticker": ticker, "source": "yfinance", "fetched_at": datetime.now().isoformat(), "errors": []}

    # Basic info
    try:
        info = _retry(lambda: stock.info, "basic info")
        if info is None:
            raise ValueError("yfinance returned None for stock info (likely blocked by network)")
        result["info"] = {
            "name": info.get("longName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", "N/A"),
            "website": info.get("website", "N/A"),
            "summary": info.get("longBusinessSummary", "N/A")[:500],
        }
        result["valuation"] = {
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "ev_to_revenue": info.get("enterpriseToRevenue"),
        }
        result["dividends"] = {
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            "ex_dividend_date": info.get("exDividendDate"),
        }
        result["profitability"] = {
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "gross_margin": info.get("grossMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
        }
        result["growth"] = {
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
        }
        result["financial_health"] = {
            "total_debt": info.get("totalDebt"),
            "total_cash": info.get("totalCash"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
        }
        result["targets"] = {
            "target_high": info.get("targetHighPrice"),
            "target_low": info.get("targetLowPrice"),
            "target_mean": info.get("targetMeanPrice"),
            "target_median": info.get("targetMedianPrice"),
            "recommendation": info.get("recommendationKey"),
            "recommendation_mean": info.get("recommendationMean"),
            "number_of_analysts": info.get("numberOfAnalystOpinions"),
        }
    except Exception as e:
        result["errors"].append(f"Failed to fetch info: {e}")

    # Price history (6 months daily)
    try:
        hist = _retry(lambda: stock.history(period="6mo", interval="1d"), "price history")
        if hist is None or hist.empty:
            raise ValueError("No price history returned (likely blocked by network)")
        recent = hist.tail(60)
        result["price_history"] = {
            "current_price": float(hist["Close"].iloc[-1]),
            "previous_close": float(hist["Close"].iloc[-2]) if len(hist) > 1 else None,
            "daily_change_pct": float((hist["Close"].iloc[-1] / hist["Close"].iloc[-2] - 1) * 100) if len(hist) > 1 else None,
            "week_high": float(recent.tail(5)["High"].max()),
            "week_low": float(recent.tail(5)["Low"].min()),
            "month_high": float(recent.tail(22)["High"].max()),
            "month_low": float(recent.tail(22)["Low"].min()),
            "avg_volume_20d": int(recent.tail(20)["Volume"].mean()),
            "last_volume": int(hist["Volume"].iloc[-1]),
            "price_data": [
                {
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                }
                for idx, row in recent.iterrows()
            ],
        }
        # 52-week data
        hist_1y = _retry(lambda: stock.history(period="1y", interval="1d"), "52-week history")
        if hist_1y is not None and not hist_1y.empty:
            result["price_history"]["week_52_high"] = float(hist_1y["High"].max())
            result["price_history"]["week_52_low"] = float(hist_1y["Low"].min())
    except Exception as e:
        result["errors"].append(f"Failed to fetch price history: {e}")

    # Income statement
    try:
        income = _retry(lambda: stock.income_stmt, "income statement")
        if income is not None and not income.empty:
            result["income_statement"] = {}
            for col in income.columns[:4]:
                period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                result["income_statement"][period] = {
                    k: float(v) if v == v else None for k, v in income[col].items()
                }
    except Exception as e:
        result["errors"].append(f"Failed to fetch income statement: {e}")

    # Balance sheet
    try:
        balance = _retry(lambda: stock.balance_sheet, "balance sheet")
        if balance is not None and not balance.empty:
            result["balance_sheet"] = {}
            for col in balance.columns[:4]:
                period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                result["balance_sheet"][period] = {
                    k: float(v) if v == v else None for k, v in balance[col].items()
                }
    except Exception as e:
        result["errors"].append(f"Failed to fetch balance sheet: {e}")

    # Cash flow
    try:
        cashflow = _retry(lambda: stock.cashflow, "cash flow")
        if cashflow is not None and not cashflow.empty:
            result["cash_flow"] = {}
            for col in cashflow.columns[:4]:
                period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                result["cash_flow"][period] = {
                    k: float(v) if v == v else None for k, v in cashflow[col].items()
                }
    except Exception as e:
        result["errors"].append(f"Failed to fetch cash flow: {e}")

    # Institutional holders
    try:
        holders = stock.institutional_holders
        if holders is not None and not holders.empty:
            result["top_institutional_holders"] = holders.head(10).to_dict(orient="records")
    except Exception:
        pass

    # Insider transactions
    try:
        insiders = stock.insider_transactions
        if insiders is not None and not insiders.empty:
            result["recent_insider_transactions"] = insiders.head(10).to_dict(orient="records")
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# akshare data fetcher (fallback)
# ---------------------------------------------------------------------------

# Column name mapping: akshare Chinese column names → English
_AK_HIST_COLS = {
    "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "amount", "振幅": "amplitude",
    "涨跌幅": "change_pct", "涨跌额": "change_amount", "换手率": "turnover_rate",
}


def _fetch_akshare_hist(ticker: str, market: str, days: int = 365) -> "pd.DataFrame":
    """Fetch historical price data from akshare. Returns a DataFrame with English column names."""
    import akshare as ak
    import pandas as pd

    sym = _to_akshare_symbol(ticker, market)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    if market == "hk":
        df = _retry(lambda: ak.stock_hk_hist(symbol=sym, period="daily", start_date=start_date, end_date=end_date, adjust=""), "akshare HK hist")
    elif market in ("cn_sh", "cn_sz"):
        df = _retry(lambda: ak.stock_zh_a_hist(symbol=sym, period="daily", start_date=start_date, end_date=end_date, adjust=""), "akshare A-share hist")
    elif market == "us":
        df = _retry(lambda: ak.stock_us_daily(symbol=sym, adjust=""), "akshare US daily")
    else:
        raise ValueError(f"Unsupported market: {market}")

    if df is None or df.empty:
        raise ValueError(f"akshare returned no data for {ticker} (market={market}, symbol={sym})")

    # Normalize column names
    df = df.rename(columns=_AK_HIST_COLS)
    # Ensure standard columns exist (US daily from sina has different column names)
    col_map_us = {"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}
    for std_col in ["date", "open", "high", "low", "close", "volume"]:
        if std_col not in df.columns:
            # Try case-insensitive match
            for c in df.columns:
                if c.lower() == std_col:
                    df = df.rename(columns={c: std_col})
                    break

    # Ensure date column is present and sorted
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

    return df


def fetch_data_akshare(ticker: str) -> dict:
    """Fetch market data via akshare as fallback. Returns the same dict structure as yfinance version."""
    import akshare as ak

    market = _detect_market(ticker)
    sym = _to_akshare_symbol(ticker, market)
    result = {
        "ticker": ticker,
        "source": "akshare",
        "market": market,
        "akshare_symbol": sym,
        "fetched_at": datetime.now().isoformat(),
        "errors": [],
    }

    # Price history
    try:
        df = _fetch_akshare_hist(ticker, market, days=365)
        recent_60 = df.tail(60)
        recent_5 = df.tail(5)
        recent_22 = df.tail(22)

        current_price = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else None

        result["price_history"] = {
            "current_price": current_price,
            "previous_close": prev_close,
            "daily_change_pct": round((current_price / prev_close - 1) * 100, 4) if prev_close else None,
            "week_high": float(recent_5["high"].max()),
            "week_low": float(recent_5["low"].min()),
            "month_high": float(recent_22["high"].max()),
            "month_low": float(recent_22["low"].min()),
            "week_52_high": float(df["high"].max()),
            "week_52_low": float(df["low"].min()),
            "avg_volume_20d": int(df.tail(20)["volume"].mean()) if "volume" in df.columns else None,
            "last_volume": int(df["volume"].iloc[-1]) if "volume" in df.columns else None,
            "price_data": [
                {
                    "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
                    "open": round(float(row["open"]), 2),
                    "high": round(float(row["high"]), 2),
                    "low": round(float(row["low"]), 2),
                    "close": round(float(row["close"]), 2),
                    "volume": int(row["volume"]) if "volume" in row and row["volume"] == row["volume"] else 0,
                }
                for _, row in recent_60.iterrows()
            ],
        }
    except Exception as e:
        result["errors"].append(f"Failed to fetch price history via akshare: {e}")

    # Financial indicators (HK stocks only — akshare has stock_hk_financial_indicator_em)
    if market == "hk":
        try:
            fin = _retry(lambda: ak.stock_hk_financial_indicator_em(symbol=sym), "akshare HK financial indicators")
            if fin is not None and not fin.empty:
                # Convert the first row (most recent) to a dict
                latest = fin.iloc[0].to_dict()
                result["financial_indicators_akshare"] = {
                    k: (float(v) if isinstance(v, (int, float)) and v == v else str(v))
                    for k, v in latest.items()
                }
        except Exception as e:
            result["errors"].append(f"Failed to fetch HK financial indicators via akshare: {e}")

    # Valuation data (HK stocks — from Baidu)
    if market == "hk":
        try:
            for indicator in ["总市值", "市盈率(TTM)", "市净率"]:
                val_df = _retry(
                    lambda ind=indicator: ak.stock_hk_valuation_baidu(symbol=sym, indicator=ind, period="近一年"),
                    f"akshare HK valuation ({indicator})",
                )
                if val_df is not None and not val_df.empty:
                    if "valuation" not in result:
                        result["valuation"] = {}
                    latest_val = float(val_df.iloc[-1].iloc[-1])
                    key = {"总市值": "market_cap", "市盈率(TTM)": "pe_trailing", "市净率": "price_to_book"}.get(indicator, indicator)
                    result["valuation"][key] = latest_val
        except Exception as e:
            result["errors"].append(f"Failed to fetch HK valuation via akshare: {e}")

    return result


# ---------------------------------------------------------------------------
# Main: try yfinance first, fall back to akshare
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch market data for a stock ticker")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., NVDA, AAPL, 1810.HK, 0883.HK, 000001.SZ)")
    parser.add_argument("--output", "-o", default=".", help="Output directory")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{ticker}_market_data.json"

    # --- Attempt 1: yfinance ---
    print(f"[yfinance] Fetching market data for {ticker}...")
    yf_failed = False
    try:
        data = fetch_data_yfinance(ticker)
        if data.get("errors"):
            print(f"[yfinance] Partial failure: {', '.join(data['errors'])}")
            # Check if we got the critical data (price history)
            if "price_history" not in data:
                print("[yfinance] Missing price history — switching to akshare fallback.")
                yf_failed = True
    except Exception as e:
        print(f"[yfinance] Failed completely: {e}")
        yf_failed = True
        data = None

    # --- Attempt 2: akshare fallback ---
    if yf_failed:
        print(f"\n[akshare] Trying fallback for {ticker}...")
        try:
            data = fetch_data_akshare(ticker)
            if data.get("errors"):
                print(f"[akshare] Partial warnings: {', '.join(data['errors'])}")
            if "price_history" in data:
                print(f"[akshare] Successfully fetched price data.")
            else:
                print(f"[akshare] Also failed to get price history.")
                data["fallback_required"] = True
        except Exception as e:
            print(f"[akshare] Also failed: {e}")
            data = {
                "ticker": ticker,
                "source": "none",
                "fetched_at": datetime.now().isoformat(),
                "errors": [
                    f"yfinance failed, akshare also failed: {e}",
                ],
                "fallback_required": True,
            }

    # Set fallback_required if we have errors and no price data
    if data and data.get("errors") and "price_history" not in data:
        data["fallback_required"] = True

    # Write output
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2, default=str)

    print(f"\nData saved to {output_file}")

    # Print summary
    if data and "price_history" in data:
        ph = data["price_history"]
        print(f"Source: {data.get('source', 'unknown')}")
        print(f"Current Price: {ph.get('current_price', 'N/A')}")
        if ph.get("daily_change_pct") is not None:
            print(f"Daily Change: {ph['daily_change_pct']:.2f}%")
        if ph.get("week_52_high"):
            print(f"52-Week Range: {ph.get('week_52_low', 'N/A')} - {ph.get('week_52_high', 'N/A')}")
    else:
        print("\nWARNING: No price data from either source. Use web search for current price.")
        print("FALLBACK: Use web search to obtain market data for this ticker.")

    if data and "valuation" in data:
        v = data["valuation"]
        if v.get("pe_trailing"):
            print(f"P/E (trailing): {v['pe_trailing']}")


if __name__ == "__main__":
    main()
