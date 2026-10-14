# QuantEdge 2.0: Local-First Streamlit Master Plan

This document supersedes the earlier suggested Next.js/FastAPI/PostgreSQL rebuild. The authoritative specification is the user-provided **Free, Local-First, Streamlit-Based Edition**.

## Nonnegotiable constraints
- Python + Streamlit UI, SQLAlchemy + local SQLite. Run with: streamlit run app.py
- Zero mandatory subscriptions, infrastructure, or credentials.
- Real quotes and historical data must be labeled by source, timestamp, currency, delay, and cache status; do not fabricate data.
- Preserve working v1.1 model evaluation, risk controls, and paper-only portfolio behavior while incrementally adding capabilities.
- Explicitly forbid brokerage order submission.
- Deterministic, leakage-safe, next-bar backtesting, fees, slippage, and accurate paper-account accounting.
- Local persistence and backups; Streamlit Community Cloud local files are not durable.

## Implementation and release stages

### Phase 0 (application base)
Keep prior v1.1 Streamlit navigation and paper simulation working; add the canonical app.py entrypoint and separate versioned SQLite workspace store. Compile, import, startup smoke-test, and persistent store-reopen tests.

### Phase 1 (market and watchlists)
Provider abstraction (Yahoo default), strict OHLCV validator, configurable historical timeframes within free-provider retention, explicit cache provenance, exchange/UTC handling, watchlist CRUD and Market Explorer. Offline deterministic tests guard duplicates, missing/invalid data, time restrictions, cache fallback and DB recovery.

### Phase 2 (charting and research)
Expand market explorer into configurable Plotly charts, price/volume indicators with verified reference calculations, saved chart layouts, company research, available fundamentals/news, and initial stock screener.

### Phase 3 (strategy and backtesting)
Pydantic-validated JSON strategy builder, shared indicator rules, deterministic next-open fills with fees/slippage and no lookahead, equity and trade history, benchmark and drawdown analysis, saved and comparable tests.

### Phase 4 (paper trading and alerts)
Enhance existing paper simulation and trading lifecycle, add multi-portfolio capabilities where safe, price/signal/indicator alerts with deduplication and a separately operated local worker. All simulation only.

### Phase 5 (polish and release)
Complete screening, exports, consistent SQLite backups and restore, data imports, accessibility/responsiveness, performance and financial-audit tests, documentation, optional non-durable demonstration Streamlit Cloud deployment.

## Audit and compatibility

The existing app is already a Streamlit multi-page research/paper platform, with source in src/stockmarket, existing SQLite paper records at PAPER_DB_PATH (default .data/paper_trading.db), and CI matrix 3.12/3.13/3.14. This work does **not** replace or migrate the existing paper database. New market/watchlist data is isolated to QUANTEDGE_WORKSPACE_DB (default .data/workspace.db).

## Data limitations

Free Yahoo data availability varies by instrument/exchange. The adapter conservatively restricts 1h, 5m and 15m requests to 60 days and 1m to 7 days; no synthetic extension of intraday history. Cached quote display always says historical, not real-time. Daily timezone-naive source dates are labeled as UTC session dates, not asserted to be real quote timestamps. Future phases will store more provider exchange/currency metadata and market-status details.
