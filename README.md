# QuantEdge Stock Market Analyzer

A professional Streamlit market-research and **paper-trading** workstation with portfolio-aware capital allocation, multi-symbol signal research, leakage-aware model validation, realistic backtesting, and an autonomous paper-only strategy runner.

> **Simulation and research only.** The application has no brokerage authentication, funding workflow, or real-money order endpoint. Historical metrics, forecasts, allocations, automated paper decisions, and backtests are not guarantees of future performance or personalized investment advice.

## v0.5 Portfolio Intelligence

On first launch, the app creates a paper portfolio profile before entering the workspace:

1. choose simulated starting capital;
2. select 1–20 symbols;
3. assign equal-weight or custom per-symbol allocation ceilings;
4. preserve an explicit cash reserve;
5. choose a Conservative, Balanced, or Aggressive simulation profile;
6. start in OBSERVE or PAPER AUTO mode.

A symbol allocation is a **maximum capital sleeve**, not an instruction to immediately buy that percentage. A simulated entry still needs a valid signal, benchmark evidence, sufficient confidence, positive cost-adjusted edge, available cash, and risk capacity.

The profile and allocations are persisted in SQLite and restored when that database remains available.

## Product surfaces

- **Dashboard** — portfolio KPIs, target-vs-actual allocation, sleeve capacity, market signals, strategy health, and recent AI decisions.
- **Markets** — watchlist signals, cost-adjusted edge, confidence, and technical price structure.
- **AI Trader** — OFF / OBSERVE / PAPER AUTO modes, opportunity ranking, model gates, risk-aware sizing, and simulated execution.
- **Portfolio** — equity, cash, allocation, P&L attribution, positions, manual rebalance planner, and optional manual paper orders.
- **Trade Journal** — persisted AI decisions, paper fills, decision cycles, and per-symbol strategy scorecards.
- **Model Analytics** — purged walk-forward validation, holdout diagnostics, benchmark ladder, and model evidence gate.
- **Backtesting** — leakage-aware holdout simulation with next-bar execution, costs, drawdown, exposure, turnover, and benchmark metrics.
- **Risk Analytics** — portfolio exposure, symbol-sleeve capacity, daily limits, protective exits, and risk-event logs.
- **Settings** — runtime/model assumptions plus one route for reconfiguring the persistent portfolio profile.

## Portfolio-aware AI Trader workflow

```text
Persistent portfolio profile
      ↓
Configured symbols + allocation sleeves
      ↓
Multi-symbol market / feature / forecast cycle
      ↓
Purged benchmark evidence gate per symbol
      ↓
Cost-aware signal + confidence filter
      ↓
Opportunity ranking
      ↓
Portfolio risk + symbol sleeve capacity
      ↓
Position sizing
      ↓
OFF / OBSERVE / PAPER AUTO
      ↓
PaperPortfolio simulated fill only
      ↓
Journal + portfolio snapshot
      ↓
Allocation drift + attribution + symbol statistics
```

### Modes

- **OFF** — no autonomous trader cycle.
- **OBSERVE** — ranks and persists decisions without changing paper positions.
- **PAPER AUTO** — eligible decisions may place simulated fills. While the Streamlit session is open, a two-minute heartbeat checks for new market/configuration/allocation fingerprints.

PAPER AUTO stops when the Streamlit session closes. There is intentionally no hidden background daemon or brokerage integration.

## Allocation and ranking

Each configured symbol has a capital ceiling. If it is already at its sleeve limit, additional BUY signals are rejected. If paper cash is scarce, eligible BUY candidates are ranked by cost-adjusted net edge, confidence, and forecast return before simulated sizing. SELL exits are processed before new entries so released simulated cash can be considered in the same cycle.

## Risk controls

Autonomous paper entries can enforce per-symbol allocation ceilings, global position and exposure caps, maximum simultaneous positions, daily trade and realized-loss limits, confidence/volatility-adjusted sizing, duplicate-position prevention, and optional stop-loss/take-profit exits.

## Allocation analytics and attribution

Dashboard and Portfolio compare **target ceilings vs actual weights**, percentage-point drift, and remaining sleeve capacity. Portfolio attribution combines persistent realized P&L from recorded paper orders with current-session unrealized P&L from open simulated positions.

Trade Journal adds per-symbol strategy statistics including decisions, model-gate pass rate, confidence, average net edge, closed strategy trades, win rate, realized P&L, and expectancy. Manual rebalance transactions are intentionally excluded from strategy-outcome statistics.

## Manual paper rebalancing

Rebalancing is deliberately separate from the signal-driven AI Trader. The Portfolio page can build a tolerance-based paper rebalance plan that identifies overweight sleeves first, sells simulated excess exposure before proposing buys, preserves the configured cash target where whole-share sizing allows, previews every instruction, and only executes when the user explicitly applies the simulated plan.

Rebalancing does not create model signals, alter opportunity rankings, or run automatically inside PAPER AUTO.

## Model governance

The forecasting stack remains deliberately simple until evidence supports more complexity: live predictions use the newest complete feature row; holdout evaluation and walk-forward folds use forecast-horizon purge gaps; zero-return, historical-mean, momentum, ridge, and ridge+momentum candidates share identical validation folds; autonomous entries require the current model to pass the benchmark gate; and backtests fit only on pre-holdout history with next-bar execution.

## Architecture

```text
streamlit_app.py
src/stockmarket/
├── services/
│   ├── analysis.py
│   ├── portfolio_cycle.py
│   ├── opportunity.py
│   ├── paper_strategy.py
│   ├── allocation.py
│   ├── risk.py
│   ├── attribution.py
│   ├── symbol_stats.py
│   ├── rebalancing.py
│   ├── ai_trader.py
│   ├── journal.py
│   ├── analytics.py
│   └── portfolio.py
├── ui/
│   ├── onboarding.py
│   ├── portfolio_intelligence.py
│   ├── app.py
│   ├── site_pages.py
│   ├── components.py
│   ├── charts.py
│   ├── context.py
│   ├── sidebar.py
│   ├── trader.py
│   ├── tables.py
│   └── theme.py
├── benchmarks.py
├── validation.py
├── modeling.py
├── features.py
├── backtest.py
├── data.py
├── signals.py
├── trading.py
├── storage.py
└── api.py
```

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
python -m compileall -q StockMarketAnalyzer.py streamlit_app.py src tests
```

GitHub Actions runs regression, fresh-app Streamlit smoke, and compilation gates on Python 3.12, 3.13, and 3.14.

## Persistence note

`PAPER_DB_PATH` defaults to `.data/paper_trading.db`. SQLite stores portfolio profiles, allocations, paper orders, AI decisions, snapshots, model runs, and risk events. Streamlit Community Cloud storage should be treated as ephemeral, so a redeploy or runtime replacement may require onboarding again. Use a hosted database before treating long-running cloud history as durable.

See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment details.
