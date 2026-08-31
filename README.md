# QuantEdge Stock Market Analyzer

A professional Streamlit market-research and **paper-trading** workstation with a Quantedge-inspired institutional UI, leakage-aware model validation, explicit benchmarks, realistic backtesting, portfolio risk controls, and an autonomous paper-only strategy runner.

> **Simulation and research only.** The application has no brokerage authentication, funding workflow, or real-money order endpoint. Historical metrics, signals, automated paper decisions, and backtests are not guarantees of future performance or personalized investment advice.

## Product surfaces

The application is organized like a real analytics product rather than one long Streamlit worksheet:

- **Dashboard** — portfolio KPIs, strategy health, signal board, and recent AI decisions.
- **Markets** — watchlist signals, cost-adjusted model edge, confidence, and technical price structure.
- **AI Trader** — OFF / OBSERVE / PAPER AUTO modes, risk-aware sizing, model gates, and autonomous simulated execution.
- **Portfolio** — equity, cash, allocation, positions, and optional manual paper orders.
- **Trade Journal** — persisted AI decisions, rejected opportunities, execution cycles, and paper fills.
- **Model Analytics** — purged walk-forward validation, holdout diagnostics, benchmark ladder, and model evidence gate.
- **Backtesting** — purged holdout simulation with next-bar execution, costs, benchmark comparison, drawdown, hit rate, exposure, turnover, and risk-adjusted metrics.
- **Risk Analytics** — exposure, position caps, daily loss/trade limits, protective exits, and risk-event logs.
- **Settings** — watchlist, data horizon, signal thresholds, capital, costs, and protective exits.

## AI Trader workflow

```text
Yahoo Finance bars
      ↓
Feature pipeline
      ↓
Ridge + momentum forecast
      ↓
Cost-aware Buy / Hold / Sell signal
      ↓
Purged benchmark evidence gate
      ↓
Confidence threshold
      ↓
Portfolio risk engine
      ↓
OFF / OBSERVE / PAPER AUTO
      ↓
PaperPortfolio simulated fill
      ↓
Decision journal + portfolio snapshot
      ↓
Trader analytics
```

### Modes

- **OFF** — calculates no autonomous trader cycle.
- **OBSERVE** — evaluates and persists decisions without placing paper fills.
- **PAPER AUTO** — approved decisions can place simulated fills. While the Streamlit session is open, a two-minute heartbeat checks for new market bars. The same market/configuration fingerprint is not evaluated twice.

PAPER AUTO does **not** continue after the Streamlit session is closed. There is intentionally no hidden daemon or real brokerage integration.

## Risk controls

Before an autonomous paper entry is allowed, the risk engine can enforce:

- maximum position allocation;
- maximum total portfolio exposure;
- maximum simultaneous positions;
- maximum daily trades;
- maximum daily realized loss;
- confidence-adjusted and volatility-adjusted sizing;
- duplicate-position prevention;
- optional stop-loss and take-profit exits.

Every AI cycle, accepted/rejected decision, paper fill, portfolio snapshot, and protective risk event is persisted to SQLite for analysis.

## Model governance

The forecasting stack is deliberately simple until evidence justifies complexity:

- live predictions use the newest technically complete feature row;
- holdout evaluation uses a forecast-horizon purge gap;
- walk-forward validation uses expanding training windows and purged test folds;
- zero-return, historical-mean, momentum, ridge, and ridge+momentum candidates are compared on identical folds;
- autonomous entries require the current model to pass the benchmark evidence gate;
- backtests fit only on pre-holdout history and execute on the next bar's open.

Do not add a fashionable model merely because it has more letters in its name. A more complex candidate belongs here only after it beats the simple baselines on the existing leakage-safe evaluation pipeline and remains useful after trading costs.

## Architecture

```text
streamlit_app.py
src/stockmarket/
├── services/
│   ├── analysis.py       # Market/model/backtest orchestration
│   ├── ai_trader.py      # Autonomous paper decision engine
│   ├── risk.py           # Portfolio-aware sizing and entry controls
│   ├── journal.py        # AI cycle + decision persistence
│   ├── analytics.py      # Trader KPIs / outcome analytics
│   └── portfolio.py      # Paper fills + protective exits
├── ui/
│   ├── app.py            # Multipage navigation + active-session heartbeat
│   ├── site_pages.py     # Product pages
│   ├── components.py     # KPI / section / status primitives
│   ├── charts.py         # Plotly market, portfolio, and strategy charts
│   ├── context.py        # Shared application context
│   ├── sidebar.py        # Settings and application shell
│   ├── trader.py         # Streamlit AI-trader state / cycle coordination
│   ├── tables.py         # Presentation shaping
│   └── theme.py          # Accessible institutional glass design system
├── benchmarks.py         # Baselines + model evidence gate
├── validation.py         # Purged walk-forward evaluation
├── modeling.py           # Ridge + momentum primitives
├── features.py           # Technical features
├── backtest.py           # Next-bar simulation + risk metrics
├── data.py               # Yahoo Finance + OHLCV validation
├── signals.py            # Cost-aware signal rules
├── trading.py            # PaperPortfolio accounting
├── storage.py            # SQLite orders, decisions, snapshots, risk events
└── api.py                # Optional FastAPI research interface
```

## Run locally

Python 3.12 is recommended; Python 3.11 and 3.13 are supported.

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

GitHub Actions runs the same regression/compile gate on Python 3.12 and 3.13.

## Optional FastAPI interface

```bash
uvicorn stockmarket.api:app --reload
```

The API reuses `AnalysisService` so research behavior follows the same leakage-aware modeling rules.

## Environment configuration

| Variable | Default | Meaning |
|---|---:|---|
| `STOCK_SYMBOL` | `MSFT` | Primary API / CLI ticker |
| `STOCK_PERIOD` | `60d` | Yahoo Finance history window |
| `STOCK_INTERVAL` | `5m` | Bar interval |
| `FORECAST_HORIZON` | `12` | Forecast horizon in bars |
| `STARTING_CASH` | `100000` | Paper account starting cash |
| `COMMISSION_RATE` | `0.001` | Per-side simulated commission |
| `SLIPPAGE_RATE` | `0.0005` | Simulated slippage |
| `BUY_THRESHOLD` | `0.005` | Net-edge threshold for Buy |
| `SELL_THRESHOLD` | `-0.005` | Net-edge threshold for Sell |
| `PAPER_DB_PATH` | `.data/paper_trading.db` | Local SQLite audit database |

See [DEPLOYMENT.md](DEPLOYMENT.md) for hosting notes and persistence limitations.
