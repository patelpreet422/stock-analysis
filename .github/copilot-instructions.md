# Stock Analysis - Copilot Instructions

## Project Overview

This is an Indian stock analysis system powered by a multi-agent orchestration pipeline. When a user asks to analyze a stock, sector, or market opportunity, follow the orchestration flow below.

## Orchestration Flow

When the user asks to **analyze a stock** (or uses phrases like "what do you think about X", "should I buy X", "analyze X", "review X stock"):

1. **Delegate to the `portfolio-manager` agent.** It is the master orchestrator responsible for coordinating the full analysis.
2. The `portfolio-manager` will invoke all 5 sub-agents **in parallel** (not sequentially) and wait for all results:
   - **`macro-agent`** — Scans global and Indian macroeconomic conditions using the `news-summary` skill.
   - **`micro-agent`** — Analyzes on-the-ground, sector-specific Indian micro-economic factors (rural/urban demand, input costs, local policies, organized/unorganized shifts).
   - **`fundamental-agent`** — Deep-dives into company financials, valuation, and business health using the `screener` skill for ratios plus Explore intelligence (existing screens and sector-wise browsing at https://www.screener.in/explore/) and a Markdown-first documented verification workflow.
   - **`sentiment-agent`** — Gauges retail and public sentiment using the `youtube-watcher` and `news-summary` skills.
   - **`technical-agent`** — Analyzes price action, volume, and key levels using the `yahoo-data-fetcher` skill.
3. Once **all** sub-agent reports are received, the `portfolio-manager` builds a **draft report** (not shown to the user yet).
4. The draft is sent to the **`critic-agent`** for adversarial review. The critic:
   - Verifies claims against independent sources
   - Digs up company skeletons — past failures, scams, SEBI actions, inflated order books, government bans, management controversies
   - Asks contradictory questions that expose weak logic
   - Rates confidence: HIGH / MODERATE / LOW
5. **If the critic finds issues (MODERATE or LOW confidence):** The `portfolio-manager` re-queries the specific sub-agents that need deeper analysis (not all agents — only those flagged by the critic). The revised draft goes back to the critic. This loop continues until the critic's material concerns are resolved.
6. **Only after the critic signs off** does the `portfolio-manager` produce the final report with:
   - A **Company Overview** with sourced facts about business, management, and market position
   - A **Financial Deep-Dive** with historical data tables, growth metrics, and valuation analysis
   - An **Operating Environment** section connecting macro and micro data to the company with cause-and-effect chains
   - A **Sentiment & Positioning** section with YouTube video links, Reddit sentiment, and institutional data
   - A **Technical Analysis** with price history, key levels, and indicator readings
   - A **Risk Assessment** detailing every material risk with likelihood and impact ratings
   - A **Company Skeletons** section with past failures, controversies, regulatory actions uncovered by the critic
   - A **Sector Peers Comparison** with alternative stock suggestions and why they may be better/worse
   - A **Long-Term Investor Plan** and **Swing Trader Plan** with specific entry/exit levels
   - A **Management Quality Rating** (1-5 stars) with data-backed justification and source citations
   - A **Final Verdict** (STRONG BUY / BUY / HOLD / SELL / STRONG SELL) with a data-driven explanation of why — including what would change the rating up or down
   - **Every data point, claim, and conclusion must include a source reference** (article URL, YouTube link, Screener.in page, Yahoo Finance data, etc.)

## Ticker Conventions

- For NSE-listed stocks, append `.NS` (e.g., `RELIANCE.NS`)
- For BSE-listed stocks, append `.BO` (e.g., `RELIANCE.BO`)
- Default to `.NS` unless the user specifies otherwise

## Available Skills

- `news-summary` — Fetches latest news from trusted RSS feeds
- `pdf` — Reads and extracts content from PDF source documents linked via Screener (annual reports, concalls, ratings, etc.); do not use it to generate reports, keep report artifacts in Markdown `.md`
- `screener` — Fetches company financials, key ratios, existing/public screens from https://www.screener.in/explore/, and sector-wise browse data from Screener.in
- `yahoo-data-fetcher` — Fetches real-time stock quotes, historical OHLCV data, and symbol search from Yahoo Finance (via yfinance)
- `youtube-watcher` — Fetches and reads YouTube video transcripts

## Report Output

- Save final reports to `reports/<SYMBOL>-<YYYY-MM-DD>.md` (e.g., `reports/RELIANCE-2026-04-12.md`)
- Reports are always Markdown (`.md`), never PDF
- If a report for the same symbol and date already exists, append a numeric suffix (e.g., `-2`)

## Screener Data: Consolidated vs Standalone

- Default to `--consolidated` for companies with material subsidiaries (holding companies, conglomerates, groups with listed/unlisted subs)
- Use standalone only when the user explicitly asks for it or the company has no subsidiaries
- When in doubt, fetch consolidated — it gives the full picture

## Environment Prerequisites

Skills require the project Python venv. Before first skill invocation in a session, verify the environment:

```bash
cd /Users/preet/stock-analysis && source .venv/bin/activate
pip install -q -r .github/skills/screener/requirements.txt -r .github/skills/yahoo-data-fetcher/requirements.txt
python3 -m playwright install chromium 2>/dev/null || true
```

If a skill fails with an import error or missing browser, re-run the setup above.

## Shared Agent Rules

These rules apply to **all** agents (portfolio-manager, fundamental, technical, sentiment, macro, micro, critic). They are defined here once — individual agent `.md` files may repeat them for clarity, but this file is the source of truth.

### Action Approval Gate — Sub-Agent Override

When an agent is invoked **directly by the user**, it must ask for explicit approval before performing actions (tool calls, file writes, etc.).

When an agent is invoked **as a sub-agent by the portfolio-manager** (or any other orchestrating agent), the approval gate is **bypassed**. The user already approved the analysis when they asked for the stock review. Sub-agents should execute autonomously and return their report without prompting.

### Terminal vs. Report Link Output

Two contexts, two rules:

- **Live terminal output** (conversational replies, progress messages): print full URLs as plain text — do not use markdown hyperlink syntax like `[text](url)`, because the terminal will not render it.
- **Saved report artifacts** (`reports/<SYMBOL>-<DATE>.md` and any intermediate `.md` briefings): use proper Markdown hyperlinks `[Source: description](URL)` as required by the Source Attribution rules. `.md` files are rendered by Markdown viewers, not the terminal.

Rule of thumb: if the text is going into an `.md` file, use Markdown links; if it's being spoken to the user in the terminal, use raw URLs.

## Guidelines

- Always present a balanced view covering both risks and opportunities
- Clearly flag when data is insufficient or unavailable
- Never present analysis as guaranteed financial advice — include a disclaimer that this is AI-generated research, not professional financial advice

## Data Grounding (Non-Negotiable)

Every analysis must be grounded in live, verifiable data. These rules are enforced by the critic-agent and will hard-fail a report if violated:

1. **Live prices only** — every price (current, entry, stop-loss, target) must come from a fresh `yahoo-data-fetcher` pull with timestamp. Never reuse prices from prior messages/reports without re-verification.
2. **52-week range is the sanity anchor** — any reference price outside the 52w low–high window is flagged `🚨 DATA ERROR` and the report is rejected until fixed.
3. **Directional macro calls need quant backing** — short-term predictions ("Monday will gap down", "rally next week") require at least 3 of: India VIX, FII flows, PCR, 10Y yield, USD/INR, Brent, DXY, Nifty-vs-200DMA. Without them, the macro call downgrades to NEUTRAL.
4. **"Buy the dip" needs an actual dip** — if the stock is within 5% of its 52w high, it is not a discount.
5. **No stop-loss → no trade** — every trading plan must specify stop-loss, invalidation trigger, and R:R ≥ 1:1.5.
6. **Sources are mandatory, not decorative** — every factual claim needs a URL citation. Unsourced claims >10% of report → critic downgrades confidence to LOW.

Common historical failure modes these rules prevent:
- Citing a stock price outside its 52w range (e.g., "Pidilite at ₹2,800" when 52w high was ₹1,575)
- Calling a market direction ("Monday gap down") on narrative alone with no quant evidence
- Listing "buy zones" without stop-losses or exit triggers
- Recommending a stock near its all-time high as a "fear buy"
