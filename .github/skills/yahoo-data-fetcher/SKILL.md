---
name: yahoo-data-fetcher
description: Fetch real-time stock quotes from Yahoo Finance.
user-invocable: true
metadata:
  moltbot:
    emoji: "📈"
    requires:
      bins: ["python3"]
    homepage: https://pypi.org/project/yfinance/
---

# Yahoo Data Fetcher – Stock Quote & History

Get current stock price data and historical OHLCV from Yahoo Finance using the `yfinance` Python library.

## Prerequisites

The project venv must have `yfinance` installed:

```bash
cd <project-root> && source .venv/bin/activate && pip install -r .github/skills/yahoo-data-fetcher/requirements.txt
```

---

## Commands

### Quote (default)

Fetch the latest quote for one or more stock symbols.

```bash
python3 index.py quote AAPL MSFT
python3 index.py AAPL              # "quote" is the default mode
```

### History

Fetch historical OHLCV data.

```bash
python3 index.py history AAPL --period 6mo --interval 1d
python3 index.py history RELIANCE.NS --period 1y --interval 1wk
```

### Search

Search for a ticker symbol by company name.

```bash
python3 index.py search "tata motors"
```

### JSON input

All modes also accept JSON via the first argument:

```bash
python3 index.py '{"mode":"history","symbols":["AAPL","MSFT"],"period":"1y","interval":"1wk"}'
python3 index.py '["AAPL","MSFT"]'
python3 index.py '{"symbols":["AAPL"]}'
```

---

## Input

- `symbols` (string, comma-separated string, or array of strings)
- `mode` – `quote` (default), `history`, or `search`
- `period` – history period (default `6mo`). Values: `1d`,`5d`,`1mo`,`3mo`,`6mo`,`1y`,`2y`,`5y`,`max`
- `interval` – history interval (default `1d`). Values: `1m`,`5m`,`15m`,`1h`,`1d`,`1wk`,`1mo`

---

## Output

### Quote mode

```json
[
  {
    "symbol": "AAPL",
    "price": 189.12,
    "change": 1.23,
    "changePercent": 0.65,
    "open": 188.50,
    "dayHigh": 190.00,
    "dayLow": 187.80,
    "previousClose": 187.89,
    "fiftyTwoWeekHigh": 199.62,
    "fiftyTwoWeekLow": 143.90,
    "marketCap": 2950000000000,
    "currency": "USD",
    "marketState": null
  }
]
```

### History mode

```json
[
  {
    "symbol": "AAPL",
    "period": "6mo",
    "interval": "1d",
    "data": [
      { "date": "2024-01-02", "open": 187.15, "high": 188.44, "low": 185.83, "close": 186.86, "volume": 42628800 }
    ]
  }
]
```

### Search mode

```json
[
  { "symbol": "TMCV.NS", "name": "TATA MOTORS LIMITED", "exchange": "NSE", "type": "EQUITY" }
]
```