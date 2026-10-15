# QuantEdge v2.1.0: Personal Streamlit TradingView-Style Strategy Lab

Redesigned around the user's Personal Stock Market Analyzer and Strategy Testing Platform specification. Free, local-first, Streamlit only and paper-only.

## Added / improved
- One focused 12-page navigation with direct Overview startup, without ML auto-trader onboarding.
- Saved historical watchlists, Plotly financial charts and technical indicators, company research and technical screening.
- Simulated BUY/SELL markers from saved backtest or manual-paper fills on price charts.
- Visual JSON Strategy Builder, saved historical backtests, equity/drawdowns, monthly returns and side-by-side comparisons.
- Independent manually managed paper portfolios, cash-safe BUY/SELL, fees/slippage, persistent holdings and P&L.
- Keep opt-in saved-strategy paper simulations, local alerts, worker, CSV import/export and SQLite recovery.
- Removed obsolete ML forecasting, duplicate AI Trader UI, API server, old launchers, extra dependencies and related unused tests.
- Existing legacy SQLite paper history is not deleted, and remains available to include in private backup archives.

## Start
pip install -r requirements.txt
streamlit run app.py

For a single local worker cycle: python workspace_worker.py

## Honest limitations
Historical/cached data, not guaranteed live; one symbol per paper account; free provider coverage varies; technical cached screeners only; in-app rather than push alerts; no persistent free cloud DB; no broker connectivity, automated real-money trading, financial advice or profit guarantee.
