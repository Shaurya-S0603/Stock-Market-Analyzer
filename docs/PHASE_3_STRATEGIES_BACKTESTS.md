# QuantEdge 2.0 Phase 3: Visual strategy rules and historical backtesting

The new builder and engine operate independently from the legacy AI model and paper portfolio.

## Strategy definitions
Validated Pydantic 2 JSON, schema v1. One symbol, one timeframe, one entry AND/OR group and one exit AND/OR group, each containing up to eight conditions. Supports SMA/EMA crossover events, RSI threshold states, MACD crossover events, breakout levels (excluding the current bar from reference), price vs SMA, and volume vs previous rolling average. Arbitrary Python execution and unknown JSON keys are rejected. Every Save is a numbered immutable snapshot; Delete preserves saved backtests.

## Execution and accounting
- Input: pre-fetched, saved, timezone-aware historical OHLCV. No API fetch during backtesting.
- A completed candle creates the signal; a permitted simulated market order is executed at the *next* candle open plus/minus configured slippage. Signals at the last bar cannot create a fill.
- Long-only, single symbol, one position, whole-share quantity. Cash cannot go below zero. Fixed cash, fixed shares, or % equity sizing, plus portfolio exposure cap.
- Stop loss and trailing stop use cost/reference levels. Trailing maxima update only **after** a bar ends.
- Take-profit may trigger intrabar. If a bar hits both stop and target, assume **stop first**. A stop opening gap exits at the opening price, not the unreachable stop level.
- Static fees and percentage commissions are applied on entry and exit; open positions are marked to the final available close and are not force-liquidated.
- Fees/slippage, provider, price-adjustment basis, bar range, and SHA256 data signature persist with each result. Mixed raw/adjusted history is prohibited.
- Buy-and-hold benchmark uses the first bar open and last available closes, assumes fractional shares and **does not** deduct benchmark trading fees. Treat it as a reference, not cost-parity.
- CAGR only provided for >=30 calendar days; Sharpe/Sortino/profit factor undefined cases show N/A rather than false infinity; return sampling uses conventional bars/year and risk-free rate 0.
- No continuous market agent, broker connection, order routing, or real-money investment recommendations.

## Pages and persistence
- **Strategy Builder:** no-code rules/parameters, JSON import/export, create/update/version/duplicate/delete.
- **Strategy Backtests:** saved local data only, historical period, starting cash, deterministic simulation, equity/drawdown chart, order/trade audit, JSON-snapshot persistence.
- **Backtest Comparison:** several persisted runs side by side, normalized equity and mismatch warnings.
- Phase 4 covers strategy-to-paper integration and alerts, separately validated.

## Known limitations
A single-symbol long-only event engine is the current phase; combined multi-symbol execution and advanced nested rule grouping require a later release. Backtesting OHLC alone cannot tell whether stop or target occurred first, so stop-first is deliberately conservative. Free data may be stale or adjusted; verify provider and adjustment fields before interpretation. Return/risk metrics are descriptive, never profit guarantees.
