#!/usr/bin/env python3
"""
Compute technical indicators for a given stock ticker.
Primary source: yfinance. Fallback: akshare (for HK, US, and A-share stocks).
Outputs a JSON file with RSI, MACD, Bollinger Bands, moving averages, and more.

Usage: uv run scripts/technical_indicators.py TICKER [--output OUTPUT_DIR]
"""

import argparse
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

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
# Ticker format detection & conversion (for akshare fallback)
# ---------------------------------------------------------------------------

def _detect_market(ticker: str) -> str:
    """Detect which market a ticker belongs to.
    Returns one of: 'hk', 'us', 'cn_sh', 'cn_sz'.
    Unrecognized formats default to 'us'.
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


# Column name mapping: akshare Chinese column names → English
_AK_HIST_COLS = {
    "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "amount", "振幅": "amplitude",
    "涨跌幅": "change_pct", "涨跌额": "change_amount", "换手率": "turnover_rate",
}


def _fetch_akshare_hist_raw(ticker: str, market: str, days: int = 365) -> pd.DataFrame:
    """Fetch historical price data from akshare. Returns a DataFrame with English column names."""
    import akshare as ak

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


# ---------------------------------------------------------------------------
# Technical indicator functions
# ---------------------------------------------------------------------------

def sma(data, period):
    """Simple Moving Average."""
    return data.rolling(window=period).mean()


def ema(data, period):
    """Exponential Moving Average."""
    return data.ewm(span=period, adjust=False).mean()


def rsi(data, period=14):
    """Relative Strength Index."""
    delta = data.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(data, fast=12, slow=26, signal=9):
    """MACD indicator."""
    fast_ema = ema(data, fast)
    slow_ema = ema(data, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(data, period=20, std_dev=2):
    """Bollinger Bands."""
    middle = sma(data, period)
    std = data.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower


def stochastic(high, low, close, k_period=14, d_period=3):
    """Stochastic Oscillator."""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(window=d_period).mean()
    return k, d


# ---------------------------------------------------------------------------
# Price data fetching: yfinance (primary) → akshare (fallback)
# ---------------------------------------------------------------------------

def _fetch_hist_yfinance(ticker: str) -> pd.DataFrame:
    """Fetch 1-year daily history via yfinance. Returns DataFrame with Close/High/Low/Volume."""
    import yfinance as yf
    stock = yf.Ticker(ticker)
    hist = _retry(lambda: stock.history(period="1y", interval="1d"), "yfinance price history")
    if hist is None or hist.empty:
        raise ValueError("yfinance returned empty data (likely blocked by network)")
    return hist


def _fetch_hist_akshare(ticker: str) -> pd.DataFrame:
    """Fetch ~1 year daily history via akshare. Returns DataFrame normalized to Close/High/Low/Volume columns."""
    market = _detect_market(ticker)
    df = _fetch_akshare_hist_raw(ticker, market, days=365)
    if df is None or df.empty:
        raise ValueError("akshare returned empty data")

    # Normalize to match yfinance column names (capitalized)
    rename_map = {}
    for col in ["close", "high", "low", "open", "volume"]:
        if col in df.columns:
            rename_map[col] = col.capitalize()
    df = df.rename(columns=rename_map)

    # Set date as index if present
    if "date" in df.columns:
        df = df.set_index("date")
    elif "Date" in df.columns:
        df = df.set_index("Date")

    return df


def fetch_price_history(ticker: str) -> tuple:
    """Try yfinance first, fall back to akshare. Returns (DataFrame, source_name)."""
    # Try yfinance
    try:
        print(f"[yfinance] Fetching price history for {ticker}...")
        hist = _fetch_hist_yfinance(ticker)
        print(f"[yfinance] Got {len(hist)} days of data.")
        return hist, "yfinance"
    except Exception as e:
        print(f"[yfinance] Failed: {e}")

    # Try akshare
    try:
        print(f"[akshare] Trying fallback for {ticker}...")
        hist = _fetch_hist_akshare(ticker)
        print(f"[akshare] Got {len(hist)} days of data.")
        return hist, "akshare"
    except Exception as e:
        print(f"[akshare] Also failed: {e}")

    return None, "none"


# ---------------------------------------------------------------------------
# Compute indicators from a DataFrame
# ---------------------------------------------------------------------------

def compute_indicators(hist: pd.DataFrame, ticker: str, source: str) -> dict:
    """Compute all technical indicators from a price history DataFrame."""
    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"] if "Volume" in hist.columns else None

    result = {
        "ticker": ticker,
        "source": source,
        "computed_at": datetime.now().isoformat(),
        "data_range": {
            "start": hist.index[0].strftime("%Y-%m-%d") if hasattr(hist.index[0], "strftime") else str(hist.index[0]),
            "end": hist.index[-1].strftime("%Y-%m-%d") if hasattr(hist.index[-1], "strftime") else str(hist.index[-1]),
            "trading_days": len(hist),
        },
        "current": {
            "price": round(float(close.iloc[-1]), 2),
            "date": hist.index[-1].strftime("%Y-%m-%d") if hasattr(hist.index[-1], "strftime") else str(hist.index[-1]),
        },
    }

    # Moving Averages
    ma_periods = [5, 10, 20, 50, 100, 200]
    result["moving_averages"] = {}
    for p in ma_periods:
        if len(close) >= p:
            sma_val = float(sma(close, p).iloc[-1])
            ema_val = float(ema(close, p).iloc[-1])
            current = float(close.iloc[-1])
            result["moving_averages"][f"SMA_{p}"] = {
                "value": round(sma_val, 2),
                "price_vs_sma": "above" if current > sma_val else "below",
                "distance_pct": round((current / sma_val - 1) * 100, 2),
            }
            result["moving_averages"][f"EMA_{p}"] = {
                "value": round(ema_val, 2),
                "price_vs_ema": "above" if current > ema_val else "below",
                "distance_pct": round((current / ema_val - 1) * 100, 2),
            }

    # MA Alignment (trend indicator)
    if len(close) >= 200:
        sma_20 = float(sma(close, 20).iloc[-1])
        sma_50 = float(sma(close, 50).iloc[-1])
        sma_200 = float(sma(close, 200).iloc[-1])
        if sma_20 > sma_50 > sma_200:
            alignment = "STRONGLY_BULLISH"
        elif sma_20 > sma_50:
            alignment = "BULLISH"
        elif sma_20 < sma_50 < sma_200:
            alignment = "STRONGLY_BEARISH"
        elif sma_20 < sma_50:
            alignment = "BEARISH"
        else:
            alignment = "NEUTRAL"
        result["ma_alignment"] = alignment

    # RSI
    rsi_val = rsi(close)
    current_rsi = float(rsi_val.iloc[-1])
    result["rsi"] = {
        "value": round(current_rsi, 2),
        "signal": "OVERBOUGHT" if current_rsi > 70 else "OVERSOLD" if current_rsi < 30 else "NEUTRAL",
        "recent_values": [round(float(v), 2) for v in rsi_val.tail(5).values],
    }

    # MACD
    macd_line, signal_line, histogram = macd(close)
    result["macd"] = {
        "macd_line": round(float(macd_line.iloc[-1]), 4),
        "signal_line": round(float(signal_line.iloc[-1]), 4),
        "histogram": round(float(histogram.iloc[-1]), 4),
        "signal": "BULLISH" if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) else "BEARISH",
        "histogram_direction": (
            "EXPANDING"
            if abs(float(histogram.iloc[-1])) > abs(float(histogram.iloc[-2]))
            else "CONTRACTING"
        )
        if len(histogram) >= 2
        else "UNKNOWN",
    }

    # Check for MACD crossover
    if len(macd_line) >= 2:
        prev_diff = float(macd_line.iloc[-2]) - float(signal_line.iloc[-2])
        curr_diff = float(macd_line.iloc[-1]) - float(signal_line.iloc[-1])
        if prev_diff < 0 and curr_diff > 0:
            result["macd"]["crossover"] = "BULLISH_CROSSOVER"
        elif prev_diff > 0 and curr_diff < 0:
            result["macd"]["crossover"] = "BEARISH_CROSSOVER"
        else:
            result["macd"]["crossover"] = "NONE"

    # Bollinger Bands
    upper, middle, lower = bollinger_bands(close)
    current_price = float(close.iloc[-1])
    bb_upper = float(upper.iloc[-1])
    bb_lower = float(lower.iloc[-1])
    bb_width = (bb_upper - bb_lower) / float(middle.iloc[-1]) * 100
    result["bollinger_bands"] = {
        "upper": round(bb_upper, 2),
        "middle": round(float(middle.iloc[-1]), 2),
        "lower": round(bb_lower, 2),
        "width_pct": round(bb_width, 2),
        "position": "ABOVE_UPPER" if current_price > bb_upper else "BELOW_LOWER" if current_price < bb_lower else "WITHIN",
        "percent_b": round((current_price - bb_lower) / (bb_upper - bb_lower) * 100, 2) if bb_upper != bb_lower else 50,
    }

    # ATR
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_val = tr.rolling(window=14).mean()
    result["atr"] = {
        "value": round(float(atr_val.iloc[-1]), 2),
        "pct_of_price": round(float(atr_val.iloc[-1]) / current_price * 100, 2),
    }

    # Stochastic
    k, d = stochastic(high, low, close)
    result["stochastic"] = {
        "k": round(float(k.iloc[-1]), 2),
        "d": round(float(d.iloc[-1]), 2),
        "signal": "OVERBOUGHT" if float(k.iloc[-1]) > 80 else "OVERSOLD" if float(k.iloc[-1]) < 20 else "NEUTRAL",
    }

    # Volume analysis
    if volume is not None and len(volume) > 0:
        avg_vol_20 = float(volume.tail(20).mean())
        last_vol = float(volume.iloc[-1])
        result["volume"] = {
            "last": int(last_vol),
            "avg_20d": int(avg_vol_20),
            "ratio_vs_avg": round(last_vol / avg_vol_20, 2) if avg_vol_20 > 0 else None,
            "trend": "ABOVE_AVERAGE" if last_vol > avg_vol_20 * 1.2 else "BELOW_AVERAGE" if last_vol < avg_vol_20 * 0.8 else "NORMAL",
        }

    # Support & Resistance (simple pivot points)
    last_high = float(high.iloc[-1])
    last_low = float(low.iloc[-1])
    last_close = float(close.iloc[-1])
    pivot = (last_high + last_low + last_close) / 3
    result["pivot_points"] = {
        "pivot": round(pivot, 2),
        "r1": round(2 * pivot - last_low, 2),
        "r2": round(pivot + (last_high - last_low), 2),
        "s1": round(2 * pivot - last_high, 2),
        "s2": round(pivot - (last_high - last_low), 2),
    }

    # Overall technical summary
    bullish_signals = 0
    bearish_signals = 0
    if result["rsi"]["signal"] == "OVERSOLD":
        bullish_signals += 1
    elif result["rsi"]["signal"] == "OVERBOUGHT":
        bearish_signals += 1
    if result["macd"]["signal"] == "BULLISH":
        bullish_signals += 1
    else:
        bearish_signals += 1
    if result.get("ma_alignment") in ["STRONGLY_BULLISH", "BULLISH"]:
        bullish_signals += 1
    elif result.get("ma_alignment") in ["STRONGLY_BEARISH", "BEARISH"]:
        bearish_signals += 1
    if result["stochastic"]["signal"] == "OVERSOLD":
        bullish_signals += 1
    elif result["stochastic"]["signal"] == "OVERBOUGHT":
        bearish_signals += 1

    result["overall_technical_signal"] = {
        "bullish_indicators": bullish_signals,
        "bearish_indicators": bearish_signals,
        "summary": "BULLISH" if bullish_signals > bearish_signals else "BEARISH" if bearish_signals > bullish_signals else "NEUTRAL",
    }

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compute technical indicators for a stock")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., NVDA, AAPL, 1810.HK, 0883.HK)")
    parser.add_argument("--output", "-o", default=".", help="Output directory")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{ticker}_technical_indicators.json"

    print(f"Computing technical indicators for {ticker}...")
    hist, source = fetch_price_history(ticker)

    if hist is None or hist.empty:
        data = {
            "ticker": ticker,
            "computed_at": datetime.now().isoformat(),
            "error": "No price data available from yfinance or akshare (network may be blocked)",
            "fallback_required": True,
        }
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"ERROR: Could not get price data for {ticker} from any source.")
        print(f"Partial result saved to {output_file}")
        print("FALLBACK: Use web search to obtain price data and compute indicators manually.")
        return

    try:
        data = compute_indicators(hist, ticker, source)
    except Exception as e:
        data = {
            "ticker": ticker,
            "source": source,
            "computed_at": datetime.now().isoformat(),
            "error": f"Failed to compute indicators: {e}",
            "fallback_required": True,
        }
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"ERROR: Got price data from {source} but failed to compute indicators: {e}")
        print("FALLBACK: Use web search to obtain price data and compute indicators manually.")
        return

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Indicators saved to {output_file}")

    # Print summary
    print(f"\nSource: {source}")
    print(f"Current Price: {data['current']['price']}")
    print(f"RSI(14): {data['rsi']['value']} ({data['rsi']['signal']})")
    print(f"MACD Signal: {data['macd']['signal']}")
    if "ma_alignment" in data:
        print(f"MA Alignment: {data['ma_alignment']}")
    print(f"Overall: {data['overall_technical_signal']['summary']}")


if __name__ == "__main__":
    main()
