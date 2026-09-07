# QuantEdge v1.1 Research Foundations

QuantEdge v1.1 treats investment literature as a set of research hypotheses to encode, test, and monitor. It does **not** ingest prose as a magic prediction model, and it does not assume that a result from one market or historical period will generalize unchanged.

The platform remains a research and paper-trading simulator only.

## Source-informed principles

### SIAS: 3 Dimensions of Successful Investing

Implementation themes:

- portfolio allocation is separated from trading signals;
- target allocations define portfolio intent and capital ceilings rather than immediate liquidation commands;
- tactical deviations can be allowed when analysis identifies an opportunity;
- risk tolerance, investment horizon, diversification, costs, and worst-case loss remain part of portfolio construction;
- technical decisions should use several indicators rather than one isolated signal;
- excessive portfolio turnover and over-diversification can dilute outcomes and increase costs.

QuantEdge mapping:

- manual allocation and manual rebalancing remain separate from PAPER AUTO;
- manual/rebalance purchases receive an acquisition grace period before model-driven exits are allowed;
- hard stop protection remains active during that grace period;
- entry and exit decisions use multi-factor evidence rather than a single model label;
- portfolio sleeves, correlation controls, exposure limits, and transaction costs remain hard constraints.

### Investing: Cut the Bull - the Bear Basics of Investing

Implementation themes:

- expected return and risk must be considered together;
- diversification and asset allocation are risk-management tools;
- investment strategy should reflect objectives and time horizon rather than isolated transactions;
- costs and repeated transactions matter.

QuantEdge mapping:

- the optimizer targets higher expected paper return without removing loss, exposure, cash, or correlation limits;
- allocation intent remains persistent across strategy cycles;
- performance is evaluated at both symbol and portfolio level.

### Investment Strategies, Performance, And Trading Information Impact

Implementation themes drawn from the paper's historical Canadian-market study:

- momentum was supported in the examined sample;
- price and trading-volume information together contained more useful information than price alone in that sample;
- volume findings were not universally consistent across all strategies;
- frequent portfolio rebalancing raises transaction-cost concerns.

QuantEdge mapping:

- adds tactical 24-bar momentum and daily 20/60-session momentum features;
- adds volume shock and price-volume confirmation features;
- price/volume information is confirmatory, not a standalone buy/sell command;
- multi-factor research conviction combines model edge, calibrated probability, momentum, trend, and volume;
- the research score is used in opportunity ranking, paper sizing, and exit confirmation;
- research hypotheses remain subject to walk-forward, benchmark, Monte Carlo, and drift evaluation.

## v1.1 decision architecture

```text
Portfolio intent / allocation ceilings
            |
            v
Tactical 1h + completed daily context
            |
            v
Model forecast + calibrated probability
            |
            v
Research conviction
  - model edge
  - probability
  - momentum
  - trend
  - price/volume confirmation
            |
            v
Model evidence + adaptive thresholds
            |
            v
Portfolio optimizer + correlation risk
            |
            v
Paper-only entry
            |
            v
Position lifecycle
  - entry origin
  - bars held
  - acquisition grace
            |
            v
Exit intelligence
  - hard stop may act immediately
  - model Sell requires bearish confirmation
  - confidence decay requires negative context
  - time exit requires non-positive conviction
            |
            v
Paper-only execution + journal
```

## Important research limitation

Historical evidence is context-dependent. The v1.1 research factors are therefore inputs to an evaluated ensemble, not guarantees of future performance. Every material strategy change should continue to be judged using purged walk-forward validation, cost-aware portfolio backtesting, benchmark comparisons, Monte Carlo stress testing, and drift monitoring.
