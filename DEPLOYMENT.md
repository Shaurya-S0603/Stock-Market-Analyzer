# Deployment Guide

## GitHub workflow

Development is merged through pull requests. CI compiles the application and worker and runs the full regression suite on Python 3.12, 3.13, and 3.14.

Do not commit `.venv/`, `.data/`, SQLite files, `.env*`, caches, or Streamlit secrets.

## Streamlit Community Cloud

1. Sign in with the GitHub account that can access `Shaurya-S0603/Stock-Market-Analyzer`.
2. Create or reconnect the app from the repository.
3. Select branch `main`.
4. Set the entrypoint to `streamlit_app.py`.
5. Python 3.12, 3.13, and 3.14 are validated by CI.
6. Deploy or reboot the application after a merged release.

Dependencies are declared in `requirements.txt`; Streamlit configuration is in `.streamlit/config.toml`.

## First launch

A fresh database opens Portfolio Intelligence onboarding before market analysis. The user selects simulated starting capital, symbols, per-symbol allocation ceilings, cash reserve, risk profile, and OBSERVE/PAPER AUTO startup mode.

These settings create a paper-only portfolio profile. They do not purchase securities or connect to a broker.

## Streamlit PAPER AUTO behavior

Inside Streamlit, PAPER AUTO remains session-driven. The UI periodically checks for a new market/configuration/allocation fingerprint while the browser session remains active.

The v0.7 persistent account layer now writes simulated cash and open positions after every paper fill. A later Streamlit process can restore that account when `PAPER_DB_PATH` still points to the same durable database and the cash/cost configuration matches.

## Standalone paper worker

v0.7 adds `paper_worker.py`, a one-cycle command intended for an external scheduler:

```bash
python paper_worker.py
```

The worker:

1. opens `PAPER_DB_PATH`;
2. loads the saved portfolio profile and allocations;
3. restores simulated cash and open positions;
4. downloads the configured `60d/1h` tactical data and `6mo/1d` context;
5. runs the model, evidence gates, optimizer, allocation/correlation risk rules, and optional adaptive exits;
6. places **paper fills only** through `PaperPortfolio`;
7. records the decision cycle;
8. saves the resulting paper account;
9. writes a post-cycle fingerprint and exits.

If the scheduler invokes the worker again with the same completed market bars and unchanged account/configuration, it returns `unchanged` rather than replaying the simulated action.

### Worker environment

```text
PAPER_DB_PATH=/persistent/path/paper_trading.db
PAPER_TRADER_MODE=PAPER_AUTO
PAPER_ADAPTIVE_EXITS=1
PAPER_MIN_CONFIDENCE=0.65
PAPER_ENTRY_ALLOCATION_PCT=5
```

`PAPER_TRADER_MODE` may be `OFF`, `OBSERVE`, or `PAPER_AUTO`. If omitted, the persisted onboarding mode is used.

A typical scheduler can call the worker hourly or on another sensible cadence. The worker does not run continuously by itself and contains no broker API.

## Persistence requirements

The SQLite database stores:

- portfolio profile and symbol allocations;
- current simulated cash and positions;
- paper orders;
- AI decisions and cycles;
- portfolio snapshots;
- model and experiment records;
- drift and risk events;
- external worker checkpoint/fingerprint.

SQLite is only durable when its underlying filesystem is durable. **Streamlit Community Cloud local storage is ephemeral**. A redeploy or runtime replacement may remove the database.

Therefore:

- Streamlit Community Cloud is suitable for the interactive research UI and temporary simulation.
- Persistent scheduled simulation should use a host with a persistent disk/volume and set `PAPER_DB_PATH` to that volume.
- A future storage adapter can move the same persistence boundary to a managed SQL database for multi-instance deployments.

## Account reset semantics

Resetting/reconfiguring Portfolio Intelligence clears the saved paper-account snapshot and worker checkpoint together with the portfolio profile. Old simulated positions therefore cannot silently reappear in a newly initialized account.

## Manual rebalance behavior

The rebalance planner remains a separate user-triggered paper control. It previews tolerance-based simulated instructions and only modifies the paper portfolio after explicit user action. It does not create model signals or real orders.

## Optional generic host

Interactive UI:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
```

One scheduled paper cycle:

```bash
python paper_worker.py
```

## Pre-deployment checks

```bash
pytest -q
python -m compileall -q StockMarketAnalyzer.py streamlit_app.py paper_worker.py src tests
```

CI executes these gates across Python 3.12, 3.13, and 3.14 before merge.
