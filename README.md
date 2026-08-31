# 📈 Stock Market Analyzer

A modular Streamlit stock-research and paper-trading lab built around **leakage-aware time-series validation**, explicit benchmark comparisons, realistic next-bar backtesting, and a simulated portfolio. It uses Yahoo Finance market data and does **not** route brokerage orders.

> **Research only:** historical metrics, model signals, and backtests are not guarantees of future performance or personalized investment advice.

## Engineering highlights

- Thin `streamlit_app.py` composition entrypoint.
- Application services separate analysis and paper-portfolio workflows from UI rendering.
- Dedicated UI modules for theme, sidebar, charts, tables, and pages.
- Live predictions use the newest technically complete feature row.
- Horizon-sized purge gaps protect holdout and expanding walk-forward validation from label overlap.
- Benchmark ladder compares zero-return, historical-mean, momentum, ridge, and ridge+momentum candidates on identical folds.
- Model evidence gate blocks unjustified complexity when simple baselines perform as well or better.
- Backtests train only on pre-holdout history, purge the horizon, predict unseen rows, and execute on the following bar's open.
- Strategy reporting includes return, drawdown, hit rate, turnover, exposure, risk-adjusted score, buy-and-hold return, and excess return.
- UI includes visible focus states, large controls, reduced-motion support, strong contrast, descriptive labels, and textual chart summaries.

## Architecture

```text
streamlit_app.py
src/stockmarket/
├── services/       # Analysis + portfolio orchestration
├── ui/             # Streamlit presentation modules
├── validation.py   # Purged walk-forward validation
├── benchmarks.py   # Baseline ladder + evidence gate
├── modeling.py     # Ridge + momentum forecasting primitives
├── features.py     # Technical features
├── backtest.py     # Next-bar simulation + risk metrics
├── data.py         # Yahoo Finance + OHLCV validation
├── signals.py      # Cost-aware Buy/Hold/Sell rules
├── trading.py      # Paper portfolio accounting
├── storage.py      # SQLite persistence
└── api.py          # Optional FastAPI surface using the same services
```

## Run locally

Python 3.12 is the recommended default; Python 3.11 and 3.13 are supported.

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Test

```bash
pytest -q
python -m compileall -q StockMarketAnalyzer.py streamlit_app.py src tests
```

## Optional API

```bash
uvicorn stockmarket.api:app --reload
```

The API uses the same `AnalysisService` as Streamlit, so training and backtesting obey the same leakage-safe rules.

## Model-development rule

Do not add XGBoost, LightGBM, neural networks, or other higher-complexity models merely because they are fashionable. Add a candidate only when it can be evaluated through the existing purged folds and benchmark gate, and keep it only if improvement remains meaningful after costs and across multiple symbols / regimes.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md). Hosted SQLite storage should be treated as ephemeral.
