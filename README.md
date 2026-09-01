# QuantEdge Stock Market Analyzer

A professional Streamlit market-research and **paper-trading** workstation with dual-timeframe forecasting, portfolio-aware capital allocation, leakage-safe validation, calibrated model evidence, multi-symbol risk controls, and persistent simulated execution.

> **Research and simulation only.** QuantEdge has no brokerage authentication, funding workflow, or real-money order endpoint. Forecasts, paper trades, allocations, and backtests are not personalized investment advice or guarantees of future performance.

## v0.7 Quant Research Engine

The v0.7 research stack upgrades the system end to end:

- **Dual timeframe:** `60d / 1h` tactical bars plus leakage-safe `6mo / 1d` context. Hourly rows only receive previously completed daily information.
- **Regime detection:** bullish/bearish trend, range, volatility, and regime-strength features.
- **Contextual features:** tactical return/volatility state, relative volume, gaps, ranges, trend persistence, time-of-day encoding, SPY-relative strength, and broader-market context.
- **Improved targets:** raw future return, cost-adjusted return, profitable-after-cost labels, direction, magnitude, and action-style targets.
- **Calibrated forecasts:** probability-of-profitable-outcome calibration with Brier scoring.
- **Ensemble benchmarks:** simple baselines, ridge variants, context ensembles, and regime-aware challengers evaluated on identical purged folds.
- **Adaptive thresholds:** entry/exit edges respond to volatility, regime state, calibrated probability, and simulated costs.
- **Portfolio optimizer:** scarce paper capital is assigned using expected edge, confidence, volatility, sleeve capacity, cash, and portfolio exposure.
- **Correlation-aware risk:** highly correlated candidates are penalized or rejected instead of being mistaken for diversification.
- **Adaptive exits:** ATR-scaled stops, trailing logic, time exits, signal reversals, confidence decay, and profit targets.
- **Experiment registry:** model hash, features, data/config signature, validation metrics, regime, and challenger evidence are stored for reproducibility.
- **Drift detection:** model-quality and feature-distribution deterioration can be flagged and persisted.
- **Portfolio walk-forward:** the full multi-symbol allocation/risk strategy is evaluated across purged expanding folds with next-bar execution.
- **Persistent simulation infrastructure:** simulated cash and positions survive process/session restarts when `PAPER_DB_PATH` points to durable storage, and `paper_worker.py` can run one idempotent paper cycle from an external scheduler.

## Portfolio Intelligence

On first launch the app creates a simulated portfolio profile:

1. choose starting paper capital;
2. select 1–20 symbols;
3. assign equal or custom per-symbol allocation ceilings;
4. preserve an explicit cash reserve;
5. choose a Conservative, Balanced, or Aggressive simulation profile;
6. start in OBSERVE or PAPER AUTO mode.

A symbol allocation is a **maximum capital sleeve**, not an instruction to immediately buy that percentage. A simulated entry still needs signal evidence, calibrated confidence, positive cost-adjusted edge, available cash, and portfolio risk capacity.

## Product surfaces

- **Dashboard** — portfolio KPIs, target-vs-actual allocation, strategy state, and recent decisions.
- **Markets** — market structure, signals, confidence, and cost-adjusted edge.
- **AI Trader** — OFF / OBSERVE / PAPER AUTO, opportunity ranking, model gates, optimizer output, and paper execution.
- **Portfolio** — cash/equity, positions, P&L attribution, allocation drift, and manual paper rebalancing.
- **Trade Journal** — persisted decisions, fills, cycles, and per-symbol statistics.
- **Model Analytics** — purged validation, calibration, benchmark ladder, experiment evidence, and drift diagnostics.
- **Backtesting** — single-symbol and portfolio-level leakage-aware simulations with costs and benchmark comparison.
- **Risk Analytics** — exposure, allocation capacity, correlation concentration, daily limits, and risk events.
- **Settings** — model/runtime assumptions and portfolio reconfiguration.

## Research pipeline

```text
60d / 1h tactical data        6mo / 1d completed context
          │                              │
          └──────────────┬───────────────┘
                         ↓
                Context + regime features
                         ↓
                  Forecast models
                         ↓
              Calibrated probability
                         ↓
           Purged benchmark evidence gate
                         ↓
              Adaptive signal threshold
                         ↓
             Multi-symbol opportunity set
                         ↓
               Portfolio optimizer
                         ↓
       Allocation + exposure + correlation risk
                         ↓
                PAPER execution only
                         ↓
          Journal + experiment + drift records
```

## Persistent paper simulation

`PAPER_DB_PATH` defaults to `.data/paper_trading.db`. The same SQLite database stores the portfolio profile, orders, decisions, model/experiment records, paper-account state, and the external worker checkpoint.

A simulated fill immediately persists:

- current paper cash;
- open symbol quantities;
- average cost;
- realized P&L;
- commission/slippage configuration.

On a new Streamlit or worker process, the account is reconstructed when the stored account configuration matches the active configuration.

### One-cycle worker

After completing onboarding at least once, a scheduler-capable host can run:

```bash
python paper_worker.py
```

The worker reads the persisted portfolio profile, obtains current research data, runs one portfolio decision cycle, records journal data, persists any simulated fills, and exits. It **never routes an order to a broker**.

The worker stores a post-cycle market/config/allocation/portfolio fingerprint. Calling it again on the same bar and unchanged account returns `unchanged` instead of repeating the simulated action.

Useful environment variables:

```text
PAPER_DB_PATH=/persistent/path/paper_trading.db
PAPER_TRADER_MODE=PAPER_AUTO
PAPER_ADAPTIVE_EXITS=1
PAPER_MIN_CONFIDENCE=0.65
PAPER_ENTRY_ALLOCATION_PCT=5
```

A scheduler may invoke `paper_worker.py` periodically. The scheduler itself is deployment infrastructure and is intentionally separate from the Streamlit browser session.

## Important storage boundary

SQLite is durable only when the filesystem containing `PAPER_DB_PATH` is durable. **Streamlit Community Cloud storage is ephemeral**, so its local `.data/` file should not be treated as permanent long-running strategy history. For persistent scheduled simulation, run the worker on a host with a persistent volume or migrate the storage implementation to a managed database.

## Run locally

Python 3.12 is recommended; CI validates Python 3.12, 3.13, and 3.14.

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Verification

```bash
pytest -q
python -m compileall -q StockMarketAnalyzer.py streamlit_app.py paper_worker.py src tests
```

GitHub Actions runs the complete regression suite and source compilation on Python 3.12, 3.13, and 3.14 before release branches are merged.

See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment details.
