# QuantEdge 2.1 Product Scope and Original Specification Alignment

Source: PROJECT PROMPT: PERSONAL STOCK MARKET ANALYZER & STRATEGY TESTING PLATFORM (user-provided DOCX).

Primary objective: a focused TradingView-style **free Streamlit** research, charting, strategy testing and paper trading workspace for one local user. No real orders or paid infrastructure.

## Reference feature mapping

| DOCX section | Supported | Known gap |
|---|---|---|
| 4.1 Market data | Free historical provider abstraction, ticker search, cached OHLCV and watchlists | Not guaranteed real-time; provider may omit market status, reliable extended-hours and all asset classes |
| 4.2 Charts | Plotly OHLC/candle/line/area, volume histogram, hover/zoom, timeframe selectors, major indicators, saved layouts, simulated BUY/SELL overlays | No JS TradingView drawing toolkit, VWAP grouped by UTC date rather than exchange-local session |
| 4.3 Research | Company profile and available fundamentals/news; cache-only technical screening | Global fundamental, sector, industry, valuation and market-cap screening not guaranteed |
| 4.4 Rules | Visual validated/versioned JSON strategy editor; SMA, EMA, MACD, RSI, breakout, volume; sizing, cost, stop/target/trailing controls | One symbol per strategy, no multi-asset open-position limit beyond one |
| 4.5 Backtest | Long-only next-open simulation, trade log, returns/risk/equity/drawdowns, monthly table, benchmark and comparisons | Bar-level stop/target ordering ambiguous; costs and splits depend on saved source basis |
| 4.6 Paper | Explicit manual paper BUY/SELL and separate opt-in strategy paper accounts, persistent cash/positions/journals | Paper price is saved historical completed bar, not a live actionable quote |
| 4.7 Alerts | Price/indicator/strategy crossing events, in-app event history, local worker | Not push/email, not guaranteed 24/7 service |
| 5-8 Tech / DB / APIs | Streamlit, Plotly, SQLite, SQLAlchemy, Python service modules; portable backups | No Next.js/Postgres/Redis/FastAPI/API server/auth because unnecessary for a single local user |
| 12 MVP | Research, charts, saved rules, deterministic backtests, comparisons, paper practice | No mandatory user authentication in local-only deployment |
| 14 Technical rules | UTC historical timestamps, validation, lookahead avoidance, source adjustment labels, error reporting | Provider calendar, corporate actions and coverage cannot be assumed beyond sourced data |

## Menu
Overview, Market Explorer, Trading Charts, Stock Research, Stock Screener, Strategy Builder, Backtest Lab, Compare Runs, Manual Paper Trading, Strategy Simulations, Local Alerts, Backup & Data.

## Repository cleanup principles

Keep only the Streamlit app entrypoint, focused workspace packages, independent one-cycle worker, local data portability, verified tests and operations documentation. Remove the old ML forecaster and AI Trader runtime, unneeded API server, forced onboarding, duplicate pages, unnecessary dependencies, stale launchers and legacy-only tests. Git history and published old releases remain intact. Do not destroy existing legacy database contents.

## Operating and verification limits

Single-user local app, no public auth. SQLite backup ZIPs are not encrypted and must stay private. Free market data may be incomplete/stale. Backtesting is educational and cannot establish future results. CI checks new code, including financial-accounting tests and Streamlit offline page startup; it does not prove an external website or real-time provider uptime.
