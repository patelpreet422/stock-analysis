# Stock Analysis - Copilot Instructions

## Project Overview

This is an Indian stock analysis system powered by a multi-agent orchestration pipeline. When a user asks to analyze a stock, sector, or market opportunity, follow the orchestration flow below.

## Orchestration Flow

When the user asks to **analyze a stock** (or uses phrases like "what do you think about X", "should I buy X", "analyze X", "review X stock"):

1. **Delegate to the `portfolio-manager` agent.** It is the master orchestrator responsible for coordinating the full analysis.
2. The `portfolio-manager` will invoke the following sub-agents in order:
   - **`macro-agent`** — Scans global and Indian macroeconomic conditions using the `news-summary` skill.
   - **`fundamental-agent`** — Deep-dives into company financials, valuation, and business health using the `screener-skill` skill.
   - **`sentiment-agent`** — Gauges retail and public sentiment using the `youtube-watcher` and `news-summary` skills.
   - **`technical-agent`** — Analyzes price action, volume, and key levels using the `yahoo-data-fetcher` skill.
3. The `portfolio-manager` synthesizes all sub-agent reports and delivers:
   - A **Long-Term Investor Plan** (buy-and-hold thesis)
   - A **Swing Trader Plan** (short-term entry, stop-loss, targets)
   - A **Final Verdict**: STRONG BUY, BUY, HOLD, SELL, or STRONG SELL

## Ticker Conventions

- For NSE-listed stocks, append `.NS` (e.g., `RELIANCE.NS`)
- For BSE-listed stocks, append `.BO` (e.g., `RELIANCE.BO`)
- Default to `.NS` unless the user specifies otherwise

## Available Skills

- `news-summary` — Fetches latest news from trusted RSS feeds
- `yahoo-data-fetcher` — Fetches real-time stock quotes and historical data from Yahoo Finance
- `youtube-watcher` — Fetches and reads YouTube video transcripts

## Guidelines

- Always present a balanced view covering both risks and opportunities
- Clearly flag when data is insufficient or unavailable
- Never present analysis as guaranteed financial advice — include a disclaimer that this is AI-generated research, not professional financial advice
