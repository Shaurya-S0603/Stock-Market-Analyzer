# Deployment Guide

## GitHub workflow

Development is merged through pull requests. CI compiles the project and runs the full regression suite on Python 3.12, 3.13, and 3.14.

Do not commit `.venv/`, `.data/`, SQLite files, `.env*`, caches, or Streamlit secrets.

## Streamlit Community Cloud

1. Sign in with the GitHub account that can access `Shaurya-S0603/Stock-Market-Analyzer`.
2. Create or reconnect the app from the repository.
3. Select branch `main`.
4. Set the entrypoint to `streamlit_app.py`.
5. Python 3.12, 3.13, and 3.14 are validated by CI; the current Community Cloud runtime may use 3.14.
6. Deploy or reboot the application after a merged release.

Dependencies are declared in `requirements.txt`; Streamlit configuration is in `.streamlit/config.toml`.

## First launch

A fresh database opens the Portfolio Intelligence onboarding flow before market analysis begins. The user selects simulated starting capital, symbols, per-symbol allocation ceilings, cash reserve, risk profile, and OBSERVE/PAPER AUTO startup mode.

These settings create a paper-only portfolio profile. They do not purchase securities or connect to a broker.

## PAPER AUTO runtime behavior

The AI Trader is intentionally **paper-only**. In PAPER AUTO mode, a Streamlit fragment checks approximately every two minutes **while that user session remains open**. It runs only when the market/configuration/allocation fingerprint changes, preventing repeated simulated execution against the same cached bar.

This is not a persistent background worker. Closing or suspending the Streamlit session stops automatic checks. There is no brokerage route, funding workflow, or real-money order endpoint.

## Persistence

The local SQLite database under `.data/` stores:

- portfolio profile and symbol allocations;
- paper orders;
- AI decisions and cycles;
- portfolio snapshots;
- model runs;
- risk events.

This works well locally, but Streamlit Community Cloud filesystem storage should be treated as **ephemeral**. A redeploy, container replacement, or runtime reset can remove the SQLite file and cause onboarding/history to restart.

For durable multi-session simulation, migrate these records and paper-account state to a hosted database before relying on long-running performance history.

## Manual rebalance behavior

The rebalance planner is a separate user-triggered paper control. It previews tolerance-based simulated instructions and only modifies `PaperPortfolio` when the user explicitly applies the plan. It does not run inside PAPER AUTO and does not feed manual rebalance results into AI strategy statistics.

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

CI also executes a fresh-app Streamlit smoke test so first-load onboarding and multipage startup are validated before merge.
