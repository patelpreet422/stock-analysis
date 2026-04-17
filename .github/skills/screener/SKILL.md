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
python3 -m playwright install chromium
```

Note: The skill uses Playwright as the first-line page loader (headless Chromium) so JavaScript-rendered data is available before parsing.

## Command

```bash
python3 index.py RELIANCE                              # company mode (default)
python3 index.py TCS --consolidated
python3 index.py --mode explore                        # list existing screens + sectors
python3 index.py --mode explore --sector Banks         # filter sectors by keyword
python3 index.py --mode sector --sector Banks          # sector-wise browse using keyword
python3 index.py --mode sector --sector-url https://www.screener.in/market/IN05/IN0501/IN050102/
```

## Input

- `--mode`: `company` (default), `explore`, or `sector`
- `symbol`: NSE/BSE company code used on Screener URLs (e.g., `RELIANCE`, `TCS`) in `company` mode
- `--consolidated`: Optional flag to use consolidated company page (`/consolidated/`) in `company` mode
- `--standalone`: Backward-compatible no-op for standalone mode (standalone URL is now default)
- `--sector`: Optional sector keyword for `explore` filtering or `sector` selection (e.g., `Banks`, `Defense`)
- `--sector-url`: Optional direct Screener sector page URL for `sector` mode
- `--limit`: Optional max records returned per section/output block

## Output

Returns structured JSON depending on mode.

### Company mode

Includes:

- `query_id` — uppercased ticker that was requested
- `source_url` — final Screener URL resolved (standalone or consolidated)
- `summary` — About blurb from Screener's description block
- `ratios` — Top ratio bar (Market Cap, Current Price, High/Low, Stock P/E, Book Value, Dividend Yield, ROCE, ROE, Face Value)
- `derived_ratios` — Computed valuations not shown explicitly on the top bar: `Price to Book`, `Market Cap / Sales`, `EV / EBITDA (approx)` (skipped gracefully when inputs aren't available, e.g. banks)
- `sitemap_sections` — Every `<section id=...>` on the page with its heading and anchor
- `sales_data` — Legacy field: only the Sales row of P&L (kept for backward compatibility)
- `quarterly_results` — `{ headers, rows }` for the full Quarterly Results table (Sales/Revenue, Expenses, Operating Profit, OPM %, Other Income, Interest, Depreciation, PBT, Tax %, Net Profit, EPS…)
- `profit_loss` — `{ headers, rows }` for the complete annual Profit & Loss table (Mar 20xx … TTM)
- `balance_sheet` — `{ headers, rows }` for the Balance Sheet table (Equity, Reserves, Borrowings, Fixed Assets, CWIP, Investments, Total Assets, …)
- `cash_flow` — `{ headers, rows }` for the Cash Flows table (Operating / Investing / Financing, Net Cash Flow, Free Cash Flow, CFO/OP)
- `ratios_history` — `{ headers, rows }` for the yearly Ratios table (Debtor Days, Inventory Days, Cash Conversion Cycle, Working Capital Days, ROCE %; banks only expose ROE % here)
- `growth_metrics` — The four Screener summary tables: `compounded_sales_growth`, `compounded_profit_growth`, `stock_price_cagr`, `return_on_equity` (each with `{label, values: {"10 Years": "…", "5 Years": "…", "3 Years": "…", "TTM"/"1 Year"/"Last Year": "…"}}`)
- `shareholding.quarterly` / `shareholding.yearly` — `{ headers, rows }` for the two Shareholding Pattern tabs (Promoters, FIIs, DIIs, Government, Public, No. of Shareholders)
- `documents.announcements` — list of `{title, url}` (recent BSE disclosures)
- `documents.annual_reports` — list of `{title, url}`
- `documents.credit_ratings` — list of `{title, url}` (CRISIL / ICRA / CARE)
- `documents.concalls` — list of `{period, files: [{type, url}]}` where type is Transcript / PPT / Notes / REC / AI Summary. `url` may be `null` for AI Summary (client-side only).

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
    "Market Cap": "₹ 18,47,111 Cr.",
    "Current Price": "₹ 1,365",
    "Stock P/E": "24.1",
    "ROCE": "9.69 %",
    "ROE": "8.40 %"
  },
  "derived_ratios": {
    "Price to Book": 2.11,
    "Market Cap / Sales": 1.8,
    "EV / EBITDA (approx)": 12.44
  },
  "profit_loss": {
    "headers": ["", "Mar 2014", "...", "Mar 2025", "TTM"],
    "rows": [
      {"metric": "Sales +", "Mar 2014": "433,521", "...": "...", "TTM": "1,024,548"},
      {"metric": "Net Profit +", "...": "..."}
    ]
  },
  "growth_metrics": {
    "compounded_sales_growth": {"label": "Compounded Sales Growth", "values": {"10 Years": "10%", "5 Years": "10%", "3 Years": "11%", "TTM": "9%"}}
  },
  "shareholding": {
    "quarterly": { "headers": ["...", "Dec 2025"], "rows": [{"metric": "Promoters +", "Dec 2025": "50.00%"}] }
  },
  "documents": {
    "concalls": [{"period": "Jan 2026", "files": [{"type": "Transcript", "url": "https://..."}, {"type": "PPT", "url": "https://..."}]}]
  },
  "sitemap_sections": [
    {"section": "Quarterly Results", "anchor": "#quarters"}
  ]
}
```
