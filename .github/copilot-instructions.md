# Stock Analysis - Copilot Instructions

## Project Overview

This is an Indian stock analysis system powered by a multi-agent orchestration pipeline. When a user asks to analyze a stock, sector, or market opportunity, follow the orchestration flow below.

## Orchestration Flow

When the user asks to **analyze a stock** (or uses phrases like "what do you think about X", "should I buy X", "analyze X", "review X stock"):

1. **Delegate to the `portfolio-manager` agent.** It is the master orchestrator responsible for coordinating the full analysis.
2. The `portfolio-manager` will invoke all 5 sub-agents **in parallel** (not sequentially) and wait for all results:
   - **`macro-agent`** — Scans global and Indian macroeconomic conditions using the `news-summary` skill.
   - **`micro-agent`** — Analyzes on-the-ground, sector-specific Indian micro-economic factors (rural/urban demand, input costs, local policies, organized/unorganized shifts).
   - **`fundamental-agent`** — Deep-dives into company financials, valuation, and business health using the `screener` skill for ratios and the `pdf` skill for documented verification.
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
- `pdf` — Reads, extracts, and creates PDF documents for structured reporting and verification
- `screener` — Fetches company financials, key ratios, and structured data from Screener.in
- `yahoo-data-fetcher` — Fetches real-time stock quotes, historical OHLCV data, and symbol search from Yahoo Finance (via yfinance)
- `youtube-watcher` — Fetches and reads YouTube video transcripts

## Guidelines

- Always present a balanced view covering both risks and opportunities
- Clearly flag when data is insufficient or unavailable
- Never present analysis as guaranteed financial advice — include a disclaimer that this is AI-generated research, not professional financial advice
