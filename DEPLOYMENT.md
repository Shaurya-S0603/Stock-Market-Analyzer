# QuantEdge v1.0 Deployment Guide

## Release workflow

Development is merged through pull requests. CI compiles the Streamlit application, research engine, standalone paper worker, and tests on Python 3.12, 3.13, and 3.14.

The `Publish v1 Release` workflow waits for a **successful CI run on `main`**. If `pyproject.toml` reports version `1.0.0` and the release does not already exist, it creates the `v1.0.0` tag and GitHub release from `RELEASE_NOTES_v1.0.md`.

Do not commit `.venv/`, `.data/`, SQLite files, `.env*`, caches, or Streamlit secrets.

## Streamlit Community Cloud

1. Sign in with the GitHub account that can access `Shaurya-S0603/Stock-Market-Analyzer`.
2. Create or reconnect the app from the repository.
3. Select branch `main`.
4. Set the entrypoint to `streamlit_app.py`.
5. Use a Python runtime compatible with 3.12–3.14.
6. Deploy or reboot after the v1 merge if automatic redeployment is not already enabled.

Dependencies are declared in `requirements.txt`; Streamlit configuration is in `.streamlit/config.toml`.

## First launch

A fresh database opens Portfolio Intelligence onboarding before market analysis. The user selects simulated starting capital, symbols, per-symbol allocation ceilings, cash reserve, risk profile, and OBSERVE/PAPER AUTO startup mode.

These settings create a paper-only portfolio profile. They do not purchase securities or connect to a broker.

## v1 Research Lab

The `/research-lab` page exposes:

- champion/challenger governance recommendations;
- Monte Carlo block-bootstrap stress tests;
- portfolio-level purged walk-forward validation;
- persistent experiment and drift-event history.

These research actions are read-only with respect to live trading. They can run backtests and simulations but cannot route real orders or automatically replace the production model.

## Streamlit PAPER AUTO behavior

Inside Streamlit, PAPER AUTO remains session-driven. The UI periodically checks for a new market/configuration/allocation fingerprint while the browser session remains active.

The persistent account layer writes simulated cash and open positions after every paper fill. A later Streamlit process can restore that account when `PAPER_DB_PATH` still points to the same durable database and the cash/cost configuration matches.

## Standalone paper worker

`paper_worker.py` is a one-cycle command intended for an external scheduler:

```bash
python paper_worker.py
```

The worker:

1. opens `PAPER_DB_PATH`;
2. loads the saved portfolio profile and allocations;
3. restores simulated cash and open positions;
4. downloads configured `60d/1h` tactical data and `6mo/1d` context;
5. runs forecasting, evidence gates, optimizer, allocation/correlation risk, and optional adaptive exits;
6. places **paper fills only** through `PaperPortfolio`;
7. records the decision cycle and experiments/drift evidence;
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

## Persistence requirements

The SQLite database stores:

- portfolio profile and symbol allocations;
- current simulated cash and positions;
- paper orders;
- AI decisions and cycles;
- portfolio snapshots;
- model experiments and drift events;
- risk events;
- external worker checkpoint/fingerprint.

SQLite is only durable when its underlying filesystem is durable. **Streamlit Community Cloud local storage is ephemeral**. A redeploy or runtime replacement may remove the database.

Therefore:

- Streamlit Community Cloud is suitable for the interactive research UI and temporary simulation;
- persistent scheduled simulation should use a host with a persistent disk/volume and set `PAPER_DB_PATH` to that volume;
- multi-instance deployment should eventually use a managed database adapter rather than sharing a local SQLite file.

## Account reset semantics

Resetting/reconfiguring Portfolio Intelligence clears the saved paper-account snapshot and worker checkpoint together with the portfolio profile. Old simulated positions therefore cannot silently reappear in a newly initialized account.

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

CI executes these gates across Python 3.12, 3.13, and 3.14 before merge. The v1 release tag is created only after the validated `main` CI run succeeds.
