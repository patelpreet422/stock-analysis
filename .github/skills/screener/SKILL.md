---
name: screener
description: Fetch company financials and key ratios from Screener.in for Indian stocks.
user-invocable: true
metadata:
  moltbot:
    emoji: "📊"
    requires:
      bins: ["python3"]
    homepage: https://www.screener.in/
---

# Screener – Company Financial Data Fetcher

Fetch company summary, key ratios, sales/P&L table rows, and page section anchors from Screener.in.

## Prerequisites

Install required Python packages in the project venv:

```bash
cd <project-root> && source .venv/bin/activate && pip install -r .github/skills/screener/requirements.txt
```

## Command

```bash
python3 index.py RELIANCE
python3 index.py TCS --standalone
```

## Input

- `symbol`: NSE/BSE company code used on Screener URLs (e.g., `RELIANCE`, `TCS`)
- `--standalone`: Optional flag to fetch standalone financials instead of consolidated

## Output

Returns structured JSON with:

- `symbol`
- `source_url`
- `summary`
- `ratios`
- `sales_data`
- `sitemap`

### Example output (truncated)

```json
{
  "symbol": "RELIANCE",
  "source_url": "https://www.screener.in/company/RELIANCE/consolidated/",
  "summary": "...",
  "ratios": {
    "Market Cap": "...",
    "ROCE": "..."
  },
  "sales_data": [
    { "Sales": "..." }
  ],
  "sitemap": [
    { "section": "Quarters", "anchor": "#quarters" }
  ]
}
```
