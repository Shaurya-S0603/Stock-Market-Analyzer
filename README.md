# QuantEdge Stock Market Analyzer v1.0

QuantEdge is a professional Streamlit quantitative-research and **paper-trading** workstation with dual-timeframe forecasting, portfolio-aware capital allocation, leakage-safe validation, calibrated model evidence, multi-symbol risk controls, strategy stress testing, and persistent simulated execution.

> **Research and simulation only.** QuantEdge has no brokerage authentication, funding workflow, or real-money order endpoint. Forecasts, allocations, backtests, and paper trades are not personalized investment advice or guarantees of future performance.

## v1.0 highlights

### Quant research engine

- **Dual timeframe:** `60d / 1h` tactical bars plus leakage-safe `6mo / 1d` context. Hourly rows only receive previously completed daily information.
- **Regime detection:** bullish/bearish trend, range, volatility, and regime-strength features.
- **Contextual features:** tactical return/volatility state, relative volume, gaps, ranges, trend persistence, time-of-day encoding, SPY-relative strength, and broader-market context.
- **Improved targets:** raw future return, cost-adjusted return, profitable-after-cost labels, direction, magnitude, and action-style targets.
- **Calibrated forecasts:** probability-of-profitable-outcome calibration with Brier scoring.
- **Ensemble benchmark ladder:** simple baselines, ridge variants, context ensembles, and regime-aware challengers evaluated on identical purged folds.
- **Adaptive thresholds:** entry/exit edges respond to volatility, regime state, calibrated probability, and simulated costs.
- **Champion / challenger governance:** research-only promotion recommendations require RMSE improvement, acceptable directional behavior, positive strategy-return improvement, and enough purged folds. Models are never silently swapped.
- **Experiment registry + drift:** model hash, features, data/config signature, validation metrics, regime, challenger evidence, and drift events are stored for reproducibility.

### Portfolio Intelligence

On first launch the app creates a simulated portfolio profile:

1. choose starting paper capital;
2. select 1–20 symbols;
3. assign equal or custom per-symbol allocation ceilings;
4. preserve an explicit cash reserve;
5. choose a Conservative, Balanced, or Aggressive simulation profile;
6. start in OBSERVE or PAPER AUTO mode.

A symbol allocation is a **maximum capital sleeve**, not an instruction to immediately buy that percentage. A simulated entry still needs signal evidence, calibrated confidence, positive cost-adjusted edge, available cash, and portfolio risk capacity.

The portfolio engine adds:

- opportunity ranking by edge, confidence, volatility, and available sleeve capacity;
- correlation-aware risk and concentration rejection;
- portfolio exposure and per-symbol ceilings;
- target-vs-actual allocation monitoring;
- persistent P&L attribution and per-symbol strategy statistics;
- separate manual paper rebalancing.

### AI Trader

- **OFF:** no automated decision execution.
- **OBSERVE:** evaluate and journal decisions without modifying the paper portfolio.
- **PAPER AUTO:** execute approved simulated fills inside `PaperPortfolio` only.

The trader includes:

- portfolio-aware whole-share sizing;
- model/evidence, confidence, allocation, cash, exposure, trade-count, loss, and correlation gates;
- affordable one-share protection so soft sizing adjustments cannot collapse a valid paper entry to quantity zero;
- full-position Sell exits for existing simulated positions;
- ATR-scaled, trailing, time, signal-reversal, confidence-decay, and profit-target exits;
- duplicate-market-bar protection;
- persistent decisions, orders, account state, and portfolio snapshots.

## Research Lab

The `/research-lab` workspace adds four v1 research surfaces:

1. **Champion / Challenger** — compares the production candidate against extended ensemble challengers with explicit promotion gates.
2. **Monte Carlo** — block-bootstrap stress testing of leakage-safe holdout strategy returns and drawdowns.
3. **Portfolio Walk-Forward** — evaluates the configured symbols together across purged expanding folds with costs, allocation sleeves, exposure caps, and correlation controls.
4. **Experiments & Drift** — reads the persistent model registry and drift-event audit trail.

## Product surfaces

- **Dashboard** — portfolio KPIs, target-vs-actual allocation, strategy state, and recent AI decisions.
- **Markets** — market structure, signals, confidence, and cost-adjusted edge.
- **AI Trader** — OFF / OBSERVE / PAPER AUTO, opportunity ranking, gates, sizing, and paper execution.
- **Portfolio** — cash/equity, positions, attribution, allocation drift, and manual paper rebalancing.
- **Trade Journal** — persisted decisions, fills, cycles, and per-symbol statistics.
- **Model Analytics** — holdout metrics, purged validation, calibration, benchmark ladder, and evidence gate.
- **Research Lab** — champion/challenger governance, Monte Carlo stress tests, portfolio validation, experiments, and drift.
- **Backtesting** — leakage-aware single-symbol simulation with costs and benchmark comparison.
- **Risk Analytics** — exposure, allocation capacity, protective exits, daily limits, and risk events.
- **Settings** — runtime assumptions and persistent portfolio reconfiguration.

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
          Purged benchmark + governance
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
   Journal + experiments + drift + stress testing
```

## Persistent paper simulation

`PAPER_DB_PATH` defaults to `.data/paper_trading.db`. The SQLite database stores the portfolio profile, paper-account state, orders, decisions, model experiments, drift/risk events, snapshots, and the standalone worker checkpoint.

A simulated fill persists:

- current paper cash;
- open quantities;
- average cost;
- realized P&L;
- commission/slippage configuration.

On a new Streamlit or worker process, the account is reconstructed when the stored account configuration matches the active configuration.

### One-cycle worker

After onboarding has created a portfolio profile, a scheduler-capable host can run:

```bash
python paper_worker.py
```

The worker reads the saved profile, obtains market/context data, runs one portfolio decision cycle, records decisions and simulated fills, persists account state, writes a post-cycle fingerprint, and exits. It **never routes an order to a broker**.

Useful environment variables:

```text
PAPER_DB_PATH=/persistent/path/paper_trading.db
PAPER_TRADER_MODE=PAPER_AUTO
PAPER_ADAPTIVE_EXITS=1
PAPER_MIN_CONFIDENCE=0.65
PAPER_ENTRY_ALLOCATION_PCT=5
```

## Storage boundary

SQLite is durable only when the filesystem containing `PAPER_DB_PATH` is durable. **Streamlit Community Cloud local storage is ephemeral**, so `.data/` should not be treated as permanent long-running strategy history. Persistent scheduled simulation should run on infrastructure with a persistent disk/volume.

## Run locally

Python 3.12 is recommended. CI validates Python 3.12, 3.13, and 3.14.

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

GitHub Actions executes the complete regression suite and source compilation before release changes are merged. For v1.0.0, a second release workflow waits for successful `main` CI before creating the `v1.0.0` tag and GitHub release.

See [DEPLOYMENT.md](DEPLOYMENT.md) and [RELEASE_NOTES_v1.0.md](RELEASE_NOTES_v1.0.md).
