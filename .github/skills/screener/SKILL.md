---
name: screener
description: Fetch company financials, key ratios, existing screen ideas, and sector-wise browse data from Screener.in for Indian stocks.
user-invocable: true
metadata:
  moltbot:
    emoji: "📊"
    requires:
      bins: ["python3"]
    homepage: https://www.screener.in/
---

# Screener – Company + Explore + Financial Data Fetcher

Fetch company fundamentals plus Explore page intelligence from Screener.in:

- Company summary, key ratios, sales/P&L table rows, and page section anchors
- Existing/public stock screens from https://www.screener.in/explore/
- Sector-wise browsing links and sector company listings from Screener market pages

## Prerequisites

Install required Python packages in the project venv:

```bash
cd <project-root> && source .venv/bin/activate && pip install -r .github/skills/screener/requirements.txt
```

## Command

```bash
python3 index.py RELIANCE                              # company mode (default)
python3 index.py TCS --standalone
python3 index.py --mode explore                        # list existing screens + sectors
python3 index.py --mode explore --sector Banks         # filter sectors by keyword
python3 index.py --mode sector --sector Banks          # sector-wise browse using keyword
python3 index.py --mode sector --sector-url https://www.screener.in/market/IN05/IN0501/IN050102/
```

## Input

- `--mode`: `company` (default), `explore`, or `sector`
- `symbol`: NSE/BSE company code used on Screener URLs (e.g., `RELIANCE`, `TCS`) in `company` mode
- `--standalone`: Optional flag to fetch standalone financials instead of consolidated in `company` mode
- `--sector`: Optional sector keyword for `explore` filtering or `sector` selection (e.g., `Banks`, `Defense`)
- `--sector-url`: Optional direct Screener sector page URL for `sector` mode
- `--limit`: Optional max records returned per section/output block

## Output

Returns structured JSON depending on mode.

### Company mode

Includes:

- `symbol`
- `source_url`
- `summary`
- `ratios`
- `sales_data`
- `sitemap`

### Explore mode

Includes:

- `source_url` (Screener Explore URL)
- `screens_total`
- `screens_by_category` (existing/public screens grouped by page section)
- `sectors_total`
- `sectors` (sector-wise browsing links from Explore)

### Sector mode

Includes:

- `source_url` (resolved sector market URL)
- `sector`
- `companies_count`
- `companies` (tabular sector listing with company-level Screener links when available)

### Example output (truncated)

```json
{
  "query_id": "RELIANCE",
  "source_url": "https://www.screener.in/company/RELIANCE/consolidated/",
  "summary": "...",
  "ratios": {
    "Market Cap": "...",
    "ROCE": "..."
  },
  "sales_data": [
    { "Sales": "..." }
  ],
  "sitemap_sections": [
    { "section": "Quarters", "anchor": "#quarters" }
  ]
}
```
