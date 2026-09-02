# QuantEdge v1.0.0

QuantEdge v1.0.0 is the first production-grade research release of the Stock Market Analyzer. It remains a **research and paper-trading platform only** with no broker integration or real-money order route.

## Core research engine

- 60d / 1h tactical data with leakage-safe 6mo / 1d context
- regime detection and contextual market features
- richer cost-aware targets and calibrated profitable-outcome probabilities
- simple, ridge, context, and regime-aware benchmark ladders
- adaptive signal thresholds
- champion/challenger governance recommendations with explicit promotion gates
- experiment registry and model/feature drift detection

## Portfolio intelligence

- first-run portfolio onboarding with symbol allocation ceilings and cash reserve
- portfolio-aware opportunity ranking and capital allocation
- correlation-aware risk and exposure controls
- allocation-vs-actual monitoring, attribution, and per-symbol scorecards
- separate manual paper rebalancing

## Paper AI Trader

- OFF, OBSERVE, and PAPER AUTO modes
- whole-share sizing that preserves valid affordable paper entries without bypassing hard risk caps
- full-position Sell exits for existing paper positions
- adaptive ATR/trailing/time/confidence/signal exits
- persistent decision journal and portfolio snapshots
- persistent simulated cash/positions when PAPER_DB_PATH points to durable storage
- standalone idempotent one-cycle `paper_worker.py` for scheduler-capable hosts

## Validation and stress testing

- purged walk-forward validation
- leakage-safe next-bar holdout backtesting with costs
- portfolio-level walk-forward validation with allocation, exposure, and correlation controls
- block-bootstrap Monte Carlo strategy stress testing
- Research Lab page for governance, stress tests, portfolio validation, experiments, and drift

## Release verification

The release branch must pass GitHub Actions on Python 3.12, 3.13, and 3.14. The v1 release workflow publishes this tag/release only after the validated `main` CI run succeeds.

## Storage note

Streamlit Community Cloud local storage is ephemeral. The interactive UI can run there, but durable long-running paper simulation requires `PAPER_DB_PATH` to live on a persistent volume or a future managed-database adapter.
