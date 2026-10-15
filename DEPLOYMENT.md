# QuantEdge 2.1 | Free Local Installation and Deployment

QuantEdge is a **single-user, local-first Streamlit research and paper simulation** application.

## Requirements
Python 3.12, 3.13 or 3.14, pip, and internet only when asking the free public provider for historical data.

## Local operation
1. pip install -r requirements.txt
2. streamlit run app.py
3. In the web interface, open Market Explorer, add tickers, and use Refresh to save historical candles.
4. Test in Trading Charts, Strategy Builder, Backtest Lab, Manual Paper Trading, or Strategy Simulations.

Optional local worker single cycle:
python workspace_worker.py
Optional historical refresh then cycle:
python workspace_worker.py --refresh

Set QUANTEDGE_WORKSPACE_DB to the absolute persistent path of the workspace SQLite database when needed. By default it uses .data/workspace.db in the working directory.

## Free-hosting boundaries
Streamlit Community Cloud can demonstrate a repository-hosted Streamlit app using app.py. It does not guarantee the durability of locally saved SQLite databases nor an always-on scheduled worker. Never upload portfolio backups, keys or personal data to a public repo. No paid infrastructure is needed for local usage. There is no live brokerage or real-money trading backend.

## Recover existing information
The original v1.x/v2.0 ML AI Trader has been removed from application code, not from your existing SQLite data files. Data Management can back up the workspace SQLite and the optional old .data/paper_trading.db archive. Restores are staged in a different directory and require an explicit restart to use.

## Running tests
pytest -q
GitHub CI builds on Python 3.12/3.13/3.14 and generates a JUnit XML plus feature evidence JSON. Results certify tests, not external provider uptime or browser/device deployment.

Read docs/PRODUCT_SPEC.md and docs/PHASE_5_OPERATIONS.md for boundaries and recovery instructions.
