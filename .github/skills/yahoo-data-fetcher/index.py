#!/usr/bin/env python3
"""
Yahoo Data Fetcher – Stock Quote & History skill
Uses yfinance library for reliable Yahoo Finance data access.
"""

import json
import sys
import os

# Resolve the project venv so the skill works regardless of cwd
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", ".."))
VENV_SITE = os.path.join(
    PROJECT_ROOT, ".venv", "lib",
    f"python{sys.version_info.major}.{sys.version_info.minor}",
    "site-packages",
)
if os.path.isdir(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

import yfinance as yf  # noqa: E402


def parse_args(argv: list[str]) -> dict:
    """Parse CLI arguments into a command dict with 'mode' and 'symbols'."""
    if not argv:
        return {}

    first = argv[0].strip()

    # JSON input mode
    if first.startswith("{") or first.startswith("["):
        parsed = json.loads(first)
        if isinstance(parsed, list):
            return {"mode": "quote", "symbols": [str(s) for s in parsed]}
        if isinstance(parsed, dict):
            symbols = parsed.get("symbols", [])
            if isinstance(symbols, str):
                symbols = [symbols]
            return {
                "mode": parsed.get("mode", "quote"),
                "symbols": [str(s) for s in symbols],
                "period": parsed.get("period", "6mo"),
                "interval": parsed.get("interval", "1d"),
            }
        return {}

    # CLI args: first arg may be mode flag
    mode = "quote"
    rest = argv
    if argv[0] in ("quote", "history", "search"):
        mode = argv[0]
        rest = argv[1:]

    symbols = []
    period = "6mo"
    interval = "1d"
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg in ("--period", "-p") and i + 1 < len(rest):
            period = rest[i + 1]
            i += 2
            continue
        if arg in ("--interval", "-i") and i + 1 < len(rest):
            interval = rest[i + 1]
            i += 2
            continue
        symbols.extend(s.strip() for s in arg.split(",") if s.strip())
        i += 1

    return {"mode": mode, "symbols": symbols, "period": period, "interval": interval}


def num(x) -> float | None:
    """Return x if it's a finite number, else None."""
    if isinstance(x, (int, float)) and x == x:  # NaN check
        return float(x)
    return None


def fetch_quote(symbols: list[str]) -> list[dict]:
    """Fetch current quote data for a list of symbols."""
    output = []
    tickers = yf.Tickers(" ".join(symbols))

    for sym in symbols:
        try:
            tk = tickers.tickers.get(sym) or yf.Ticker(sym)
            fi = tk.fast_info

            price = num(fi.last_price)
            prev = num(fi.previous_close)
            change = None
            change_pct = None
            if price is not None and prev is not None and prev != 0:
                change = round(price - prev, 4)
                change_pct = round((change / prev) * 100, 4)

            output.append({
                "symbol": sym,
                "price": price,
                "change": change,
                "changePercent": change_pct,
                "open": num(fi.open),
                "dayHigh": num(fi.day_high),
                "dayLow": num(fi.day_low),
                "previousClose": prev,
                "fiftyTwoWeekHigh": num(fi.year_high),
                "fiftyTwoWeekLow": num(fi.year_low),
                "marketCap": num(fi.market_cap),
                "currency": getattr(fi, "currency", None),
                "marketState": None,
            })
        except Exception as e:
            output.append({
                "symbol": sym,
                "price": None,
                "change": None,
                "changePercent": None,
                "currency": None,
                "marketState": None,
                "error": str(e),
            })

    return output


def fetch_history(symbols: list[str], period: str = "6mo", interval: str = "1d") -> list[dict]:
    """Fetch historical OHLCV data for a list of symbols."""
    output = []

    for sym in symbols:
        try:
            tk = yf.Ticker(sym)
            hist = tk.history(period=period, interval=interval)

            if hist.empty:
                output.append({"symbol": sym, "data": [], "error": "No historical data found"})
                continue

            records = []
            for idx, row in hist.iterrows():
                records.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                })

            output.append({"symbol": sym, "period": period, "interval": interval, "data": records})
        except Exception as e:
            output.append({"symbol": sym, "data": [], "error": str(e)})

    return output


def search_symbol(query: str) -> list[dict]:
    """Search Yahoo Finance for matching symbols."""
    import urllib.request
    import urllib.parse

    url = (
        f"https://query2.finance.yahoo.com/v1/finance/search"
        f"?q={urllib.parse.quote(query)}&quotesCount=10&newsCount=0"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    return [
        {
            "symbol": q.get("symbol"),
            "name": q.get("shortname") or q.get("longname"),
            "exchange": q.get("exchDisp"),
            "type": q.get("quoteType"),
        }
        for q in data.get("quotes", [])
    ]


def main():
    args = parse_args(sys.argv[1:])
    mode = args.get("mode", "quote")
    symbols = args.get("symbols", [])

    if mode == "search":
        if not symbols:
            print(json.dumps({"error": "Missing search query"}, indent=2), file=sys.stderr)
            sys.exit(2)
        result = search_symbol(" ".join(symbols))
        print(json.dumps(result, indent=2))
        return

    if not symbols:
        print(json.dumps({
            "error": "Missing symbols",
            "usage": {
                "quote": "index.py quote AAPL MSFT",
                "history": "index.py history AAPL --period 6mo --interval 1d",
                "search": 'index.py search "tata motors"',
                "json": '\'{"mode":"history","symbols":["AAPL"],"period":"1y","interval":"1wk"}\'',
            },
        }, indent=2), file=sys.stderr)
        sys.exit(2)

    if mode == "history":
        result = fetch_history(symbols, args.get("period", "6mo"), args.get("interval", "1d"))
    else:
        result = fetch_quote(symbols)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
