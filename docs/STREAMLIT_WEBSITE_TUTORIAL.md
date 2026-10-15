# QuantEdge: Streamlit Website Setup and Complete Use Tutorial

Official deployment reference: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

This is a **real Streamlit Python web app**, not a static GitHub Pages site.
All trading is paper-only. Public quotes are best-effort historical, not guaranteed real-time.
For private lasting research, run the app locally; Community Cloud's container storage is temporary.

## Step A: Publish the app for free

1. Sign in at https://share.streamlit.io with the GitHub account that owns the repository.
2. Select **Create app**, then **Yup, I have an app**.
3. Enter:
   - Repository: **Shaurya-S0603/Quant-Edge-Terminal**
   - Branch: **main**
   - Main file path: **app.py**
   - Python: **3.12** (under **Advanced settings**)
   - App URL: choose an available subdomain; availability is not guaranteed.
4. In Advanced settings, paste this **root-level** Streamlit Secrets TOML:

    QUANTEDGE_PUBLIC_DEMO = "1"

5. Click **Deploy**. Streamlit installs requirements.txt automatically.
6. Open the actual URL Streamlit assigns. Use **Start Here** and the synthetic demo
   stock to verify routing, charts, backtests and manual paper orders.
7. If an older Streamlit app still references the former GitHub repository name,
   update its repository coordinates or redeploy from the current name.
8. Do not supply private brokerage data or API keys in the app. There is no brokerage integration.

**Why the public-demo flag is required:** otherwise all visitors would use the
same writable default SQLite file. The flag assigns each browser session a
separate temporary SQLite database. It is **not** user authentication and does
**not** provide durable cloud storage. If you omit the flag, do not publish the app publicly.

## Step B: Use the site for strategy testing

The sidebar contains 13 screens. Start Here is always available.

1. **Start Here:** click **Load fictional demo stock and strategy**.
   This creates **QEDMO**, with 320 invented daily candles and one sample
   SMA/RSI strategy. It does not call the free market provider.
2. **Overview:** check the ticker count and stored-candle timestamp.
3. **Market Explorer:** select QEDMO, or add a real ticker such as AAPL,
   MSFT or an supported exchange-suffixed ticker. For real tickers, click
   the explicit Refresh control to fetch data. Data can be delayed or rate-limited.
4. **Trading Charts:** select ticker, timeframe, chart type and indicators.
   Inspect SMA, EMA, RSI, MACD or volume, zoom/hover. Save a chart layout.
5. **Strategy Builder:** select the tutorial strategy or create a strategy.
   Set entry/exit rules, stop-loss/take-profit, position size, slippage and fees.
   Click Save to create a versioned JSON strategy definition.
6. **Backtest Lab:** choose a saved strategy and its cached ticker/timeframe,
   set the testing dates and fictional starting cash, then Run. Examine return,
   buy-and-hold, drawdown, equity chart, monthly returns, trade history and
   execution audit. Save the complete backtest result.
7. **Compare Runs:** choose two saved experiments, compare equity curves and
   verify that their dates, source and transaction assumptions match.
8. **Manual Paper Trading:** create a fictional-cash account, select BUY or SELL,
   quantity and simulated costs, acknowledge the historical-price model, then
   place a **paper** order. The fill uses the last completed saved DAILY close.
9. **Strategy Simulations:** create a different, disabled-by-default strategy
   account. Enable it and process newly completed saved bars. No historical
   positions are retroactively placed at account creation.
10. **Local Alerts:** configure a price/RSI/SMA/strategy event and evaluate
    saved completed bars. These are in-app events, not phone notifications.
11. **Backup & Data:** download a verified local SQLite archive if you want
    to preserve your experiment outside the temporary cloud session.

## Step C: Run privately with lasting local storage

On your own computer:

    python -m pip install -r requirements.txt
    streamlit run app.py

Do **not** set QUANTEDGE_PUBLIC_DEMO for ordinary local use.
The workspace defaults to .data/workspace.db, or can use a custom durable path
via QUANTEDGE_WORKSPACE_DB. You control access to your computer and files.

An optional one-cycle offline monitoring worker:

    python workspace_worker.py

With explicit historical refresh:

    python workspace_worker.py --refresh

If you want periodic checks, run the worker through your OS scheduler.
Community Cloud does not automatically run a durable background worker.

## Troubleshooting

- **ModuleNotFoundError:** ensure requirements.txt is in the repo root; verify
  your Streamlit app points to app.py and check Manage app logs.
- **Old deleted entrypoint:** use app.py, NOT streamlit_app.py or StockMarketAnalyzer.py.
- **GitHub repository missing:** reauthorize the current GitHub repository at
  Share Streamlit; repository name is now Quant-Edge-Terminal.
- **Charts blank:** load synthetic QEDMO first or fetch/copy enough historical
  bars for your real ticker. Provider data availability is not guaranteed.
- **Paper account cannot trade:** first load at least three DAILY bars; the
  manual order uses the penultimate bar to avoid incomplete candles.
- **No strategy signals yet:** a long moving average needs many prior candles.
  Test with the 320-bar synthetic fixture and inspect the execution audit.
- **Lost saved cloud data:** expected if the temporary session/server resets.
  Keep backups or use local durable storage.
- **App asleep:** Streamlit Community Cloud may put idle apps to sleep; open
  the site to wake it. Do not rely on permanent 24/7 worker uptime.
- **Cloud visitor isolation:** set QUANTEDGE_PUBLIC_DEMO = "1" as a root-level
  secret, not inside a TOML section.

## Verification

The repository's GitHub Actions workflow tests Python 3.12, 3.13 and 3.14.
The new checks exercise first-run tutorial startup, deterministic sample data,
visitor-isolated workspace paths, and persistent local path selection.
These tests do **not** prove a publicly deployed URL works until you deploy and
manually open it.

Never mistake research performance, fictional paper results, or a historical
data source for a guarantee of profits.
