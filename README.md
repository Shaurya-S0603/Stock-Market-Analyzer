# QuantEdge 2.1.1 | Free Personal Streamlit Strategy Website

QuantEdge is a **single-user, local-first Streamlit** market research, interactive charting, strategy backtesting, and paper-only trading workstation. No paid API, cloud database, broker login, Next.js backend, or subscription required.

**All quotes are historical/cached or best-effort delayed. No guarantee of live executable prices, future returns or investment advice. All trades are simulated.**

## Start on your computer

1. Install Python 3.12, 3.13 or 3.14.
2. Run: pip install -r requirements.txt
3. Run: streamlit run app.py
4. In Market Explorer add stock/ETF/index tickers and explicitly fetch free-provider historical OHLCV.
5. Study Trading Charts, save layouts, create rules in Strategy Builder, backtest and compare runs, then practice with manual or strategy paper accounts.

Optional once-only offline worker: python workspace_worker.py. Add --refresh to explicitly request new historical data first. A local scheduler is required for recurring alert checks.

## Core pages

| Page | Functionality |
|---|---|
| Overview | Tracked symbols, historical saved closes, paper practice summary, recent alerts |
| Market Explorer | Ticker lookup, multiple saved watchlists, historical OHLCV download and cache |
| Trading Charts | Interactive Plotly candles/OHLC/line/area, volume histogram, SMA/EMA/WMA/RSI/MACD/BB/VWAP/ATR and other indicators; chart layouts and simulated BUY/SELL markers |
| Stock Research | Optional available company profiles, fundamentals, and linked news |
| Stock Screener | Cached price, change, volume, RSI and SMA filters, saved rules and CSV export |
| Strategy Builder | Validated versioned JSON; entry/exit rule groups, sizing, stops, trailing exits and modeled costs |
| Backtest Lab | Next-bar long-only historical fills, fees, positions, trade journal, risk metrics, equity curve, drawdowns, monthly returns and buy/hold benchmark |
| Compare Runs | Compare saved results with period, provider and cost compatibility warnings |
| Manual Paper Trading | Independent BUY/SELL practice at last completed cached daily close, fee/slippage and persistent account journal |
| Strategy Simulations | Independent opt-in automated rule simulations on completed saved bars |
| Local Alerts | Price, RSI, SMA and rule signals; saved in-app notification history |
| Backup & Data | SQLite integrity checks, workspace and optional legacy paper archive, verified staged restore, strict OHLCV CSV |

## Technology and free operation

Frontend Streamlit. Charts Plotly. Backtests custom causal Pandas/NumPy engines. SQLite/SQLAlchemy persistence. Pydantic rule validation. Best-effort yfinance public historical provider. Automated tests with pytest and GitHub Actions.

## Legacy cleanup

QuantEdge 2.1 removes the old ML forecasting/AI Trader UI, duplicate dashboards/backtests, unused FastAPI server, old launchers and obsolete test suites. Old SQLite paper-trading data at .data/paper_trading.db is NOT deleted. Backup & Data still includes the older file when present for archival recovery.

## Important limitations

- No guaranteed streaming, exchange status or complete pre/post-market coverage from the free provider.
- Fundamental screeners are not whole-market/valuation screeners: cached technical screening is supported, news/fundamentals are best-effort on demand.
- Each strategy or manual simulated account holds one instrument, but multiple independent portfolios are supported. Currency conversion and multi-symbol optimization are outside this scope.
- Historical next-open execution is deterministic and conservative, not evidence of future profitability or today's executable fills.
- Manual orders fill at saved completed historical candles, not a broker or live exchange.
- In-app alerts are not phone/email push notifications. External scheduling and persistent local disk are needed for continuing operation.
- Local single-user design has no public authentication; do not expose an unauthenticated instance or private backup archives on the internet.
- Streamlit Community Cloud has ephemeral local storage; use local operation and private backups for durable research history.

Docs: docs/PRODUCT_SPEC.md, docs/PHASE_3_STRATEGIES_BACKTESTS.md, docs/PHASE_5_OPERATIONS.md.


## Publish the interactive website and learn to use it

The **Start Here** page includes a first-time tutorial and a one-click, explicitly fictional QEDMO practice dataset. For free Streamlit Community Cloud hosting, choose **Shaurya-S0603/Quant-Edge-Terminal**, branch **main**, entrypoint **app.py**, Python **3.12**, and add the root-level Streamlit secret `QUANTEDGE_PUBLIC_DEMO = "1"`. This keeps each visitor's temporary paper workspace isolated. Cloud data is not durable, so download your backups or run privately on your own computer.

Follow the full [Website deployment and usage tutorial](docs/STREAMLIT_WEBSITE_TUTORIAL.md). The application cannot be treated as a live brokerage or guaranteed real-time market feed.
