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
   - **`sentiment-agent`** — Gauges retail and public sentiment using the `news-summary` skill plus social/forum scraping.
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
   - A **Sentiment & Positioning** section with news headlines, Reddit/forum sentiment, and institutional data
   - A **Technical Analysis** with price history, key levels, and indicator readings
   - A **Risk Assessment** detailing every material risk with likelihood and impact ratings
   - A **Company Skeletons** section with past failures, controversies, regulatory actions uncovered by the critic
   - A **Sector Peers Comparison** with alternative stock suggestions and why they may be better/worse
   - A **Long-Term Investor Plan** and **Swing Trader Plan** with specific entry/exit levels
   - A **Management Quality Rating** (1-5 stars) with data-backed justification and source citations
   - A **Final Verdict** (STRONG BUY / BUY / HOLD / SELL / STRONG SELL) with a data-driven explanation of why — including what would change the rating up or down
   - **Every data point, claim, and conclusion must include a source reference** (article URL, Screener.in page, Yahoo Finance data, etc.)

## Ticker Conventions

- For NSE-listed stocks, append `.NS` (e.g., `RELIANCE.NS`)
- For BSE-listed stocks, append `.BO` (e.g., `RELIANCE.BO`)
- Default to `.NS` unless the user specifies otherwise

## Available Skills

- `news-summary` — Fetches latest news from trusted RSS feeds
- `pdf` — Reads and extracts content from PDF source documents linked via Screener (annual reports, concalls, ratings, etc.); do not use it to generate reports, keep report artifacts in Markdown `.md`
- `screener` — Fetches company financials, key ratios, existing/public screens from https://www.screener.in/explore/, and sector-wise browse data from Screener.in
- `yahoo-data-fetcher` — Fetches real-time stock quotes, historical OHLCV data, and symbol search from Yahoo Finance (via yfinance)

## Report Output

- Save final reports to `reports/<SYMBOL>-<YYYY-MM-DD>.md` (e.g., `reports/RELIANCE-2026-04-12.md`)
- Reports are always Markdown (`.md`), never PDF
- If a report for the same symbol and date already exists, append a numeric suffix (e.g., `-2`)

## Glossary Reference

- A shared glossary of financial terms, acronyms, and interpretation guides is maintained at `reports/GLOSSARY.md`
- **Do NOT embed inline glossaries in individual reports.** Instead, add a footer link: `📖 *Unfamiliar with a term? See the [Glossary](GLOSSARY.md) for definitions and interpretation guides.*`
- When a report introduces a new term not yet in the glossary, **append it to `reports/GLOSSARY.md`** under the appropriate category using the heading-based anchor format (`### slug-name` followed by the definition). Use lowercase kebab-case slugs.
- All agents (macro, micro, fundamental, sentiment, technical, portfolio-manager) must follow this rule — no duplicated glossaries across reports

### Key Terms Section & Inline Linking

Each report should include a **"Key Terms Used"** section (near the end, before the disclaimer) listing the most important technical terms with direct glossary links. This helps readers quickly look up unfamiliar concepts.

**Linking priority rule:**
1. **Source link first** — if a term appears alongside a live data citation (Yahoo Finance, Screener.in, news article), the source link takes priority. Do NOT replace source citations with glossary links.
2. **Glossary link for definitions** — when a term is used without an accompanying source (e.g., "VIX dropped below 18" with no Yahoo URL nearby), link it to the glossary: `[VIX](GLOSSARY.md#vix)`.
3. **Key Terms section always uses glossary links** — the dedicated section at the bottom always links to glossary anchors regardless of whether sources exist elsewhere in the report.

**Example "Key Terms Used" section:**
```markdown
## Key Terms Used
[VIX](GLOSSARY.md#vix) · [FII](GLOSSARY.md#fii) · [DII](GLOSSARY.md#dii) · [200 DMA](GLOSSARY.md#200-dma) · [PCR](GLOSSARY.md#pcr) · [CPI](GLOSSARY.md#cpi) · [CAD](GLOSSARY.md#cad) · [DXY](GLOSSARY.md#dxy) · [bps](GLOSSARY.md#bps)
```

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

**Bypass signal (machine flag — not freeform interpretation):** the orchestrator MUST prepend the following banner to every sub-agent dispatch prompt, and sub-agents MUST key off it:

```
RUN_CONTEXT: ORCHESTRATED_SUBAGENT
PARENT_AGENT: portfolio-manager
APPROVAL_REQUIRED: false
SNAPSHOT_ID: <see MarketSnapshot below>
```

If `RUN_CONTEXT: ORCHESTRATED_SUBAGENT` is present, the sub-agent does NOT prompt the user — it executes autonomously and returns. If absent, the agent assumes direct-user invocation and the approval gate applies.

### MarketSnapshot Contract (Shared Price State)

To eliminate timestamp drift and duplicate Yahoo calls when multiple agents run in parallel, the orchestrator publishes one canonical price snapshot per run:

```
SNAPSHOT_ID:   <ticker>-<unix_ts>
TICKER:        PIDILITIND.NS
PULLED_AT:     2026-04-22T12:30:14+05:30
PRICE:         1393.40
HIGH_52W:      1574.95
LOW_52W:       1259.00
TTL_SECONDS:   300
SOURCE:        yahoo-data-fetcher quote
```

Rules:
- The portfolio-manager (Phase 0) creates the snapshot and embeds it in every sub-agent's dispatch prompt.
- Sub-agents MUST consume the snapshot's price/52w levels as the canonical reference. Their own Data Integrity Gate becomes a **sanity check only**: confirm the snapshot's price falls inside the 52w window from a fresh quote, but do NOT replace the snapshot's headline price with their own pull (prevents 3+ inconsistent prices in one report).
- A sub-agent may refresh the snapshot ONLY if `TTL_SECONDS` has elapsed — in which case it pulls a new quote, emits a new `SNAPSHOT_ID` in its output, and the orchestrator re-broadcasts to peers.
- For derivative data (RSI, MACD, indicator series, intraday OHLCV) sub-agents pull what they need — the snapshot is for the headline price + 52w range only.

### Normalized Score Field (Output Schema Addendum)

Every worker agent's "Output Schema" must include — alongside its native label — a normalized numeric score so the portfolio-manager can synthesize deterministically:

```
### N. Score
- label:            <agent-native enum, e.g. STRONG TAILWIND / BULLISH / BUY>
- normalized_score: <-2 | -1 | 0 | +1 | +2>   # +2 strongest bullish, -2 strongest bearish
- confidence:       <LOW | MEDIUM | HIGH>
- time_horizon:     <intraday | swing | positional | long-term>   # optional
```

Mapping convention:
- `+2` = STRONG BUY / STRONG TAILWIND / EXTREME BULLISH
- `+1` = BUY / TAILWIND / BULLISH
- ` 0` = NEUTRAL / HOLD
- `-1` = SELL / HEADWIND / BEARISH
- `-2` = STRONG SELL / STRONG HEADWIND / EXTREME BEARISH

The portfolio-manager synthesizes the final verdict from the **normalized_score + confidence** fields, not from the prose labels.

### Phase 1 Failure / Timeout / Degradation Policy

The portfolio-manager's parallel sub-agent dispatch (Phase 1) and any later `write_agent` follow-ups MUST follow this policy — there is no "wait forever" branch:

- **Per-agent timeout:** 300 seconds (5 min) for initial dispatch; 180 seconds for follow-ups.
- **Retry budget:** one cold respawn on timeout or malformed schema.
- **Degraded path:** if an agent still fails after retry, mark its dimension `DEGRADED — INSUFFICIENT DATA` in the synthesis, downgrade overall confidence by one step, and proceed.
- **Required vs optional workers:** `technical-agent` and `fundamental-agent` are REQUIRED — if either fails after retry, abort the run with a clear terminal message. `macro-agent`, `micro-agent`, `sentiment-agent` are OPTIONAL — degrade gracefully.
- **Critic must respect degradation:** treat `DEGRADED` sections as known gaps, not infinite-loop triggers; do not flag them as 🔄 re-analysis targets.

### Critic Issue Ledger (Closure Semantics)

To prevent the critic loop from cycling on rephrased concerns, the critic-agent emits findings as a structured ledger (one row per issue):

```
| issue_id | severity              | owner_agent      | claim                       | status   |
|----------|-----------------------|------------------|-----------------------------|----------|
| C-001    | BLOCKER / MAJOR / MINOR | fundamental    | "order book ₹1.2L Cr"       | OPEN     |
| C-002    | MAJOR                 | technical        | "RSI 58 cited stale"         | OPEN     |
```

Loop rules:
- The portfolio-manager maintains the ledger across iterations. On each revision pass, it sets `status = RESOLVED / PERSISTENT / DEFERRED` per row.
- The critic on iteration N+1 may add new rows but MUST reference existing `issue_id`s when raising the same concern in different words (no silent re-numbering).
- Exit condition: ship when no `BLOCKER` is OPEN. Otherwise loop, capped at 3 iterations.
- After 3 iterations with unresolved BLOCKERs: ship with a top-of-report banner `⚠️ Unresolved critic concerns: <list of issue_ids>`.

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
