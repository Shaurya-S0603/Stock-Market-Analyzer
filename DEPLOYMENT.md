# Deployment Guide

## GitHub workflow

Development is merged through pull requests. CI compiles the project and runs the regression suite on Python 3.12 and 3.13.

Do not commit `.venv/`, `.data/`, SQLite files, `.env*`, caches, or Streamlit secrets.

## Streamlit Community Cloud

1. Sign in with the GitHub account that can access `Shaurya-S0603/Stock-Market-Analyzer`.
2. Create an app from the repository.
3. Select branch `main`.
4. Set the entrypoint to `streamlit_app.py`.
5. Use Python 3.12 unless another runtime has been deliberately validated by CI.
6. Deploy.

Dependencies are declared in `requirements.txt`; Streamlit configuration is in `.streamlit/config.toml`.

## PAPER AUTO runtime behavior

The AI Trader is intentionally **paper-only**. In PAPER AUTO mode, a Streamlit fragment checks approximately every two minutes **while that user session remains open**. It runs only when the market/configuration fingerprint changes, preventing repeated execution against the same cached bar.

This is not a persistent background worker. Closing/suspending the Streamlit session stops automatic checks. A future always-on simulation service would need a separately deployed scheduler/worker and persistent portfolio state; this repository does not pretend a browser session is one.

## Persistence

The local SQLite database under `.data/` stores paper orders, AI decisions, trader cycles, portfolio snapshots, model runs, and risk events. This works well locally, but a Community Cloud filesystem should be treated as **ephemeral**.

For durable multi-session deployment, move these records and paper-account state to a hosted database before relying on long-running performance history.

## Optional generic host

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
```

## Pre-deployment checks

```bash
pytest -q
python -m compileall -q StockMarketAnalyzer.py streamlit_app.py src tests
```

Also confirm that no secrets or local databases are staged and that PAPER AUTO still routes exclusively to `PaperPortfolio`.
