# QuantEdge 2.0 Phase 2: Charts, Indicators, Research and Initial Screening

## Delivered
- Interactive multi-panel Plotly Charts page (candlestick, OHLC, line, area) with zoom/pan/hover and volume.
- Causal indicator library: SMA, EMA, WMA, RSI/Wilder average, MACD, Bollinger bands, ROC, Stochastic, ATR, OBV, rolling prior-bar breakout levels and UTC-day VWAP.
- Indicator length and Bollinger deviation settings. Separate panels for RSI, MACD, Stochastic, ATR, ROC, OBV. Warm-up is NaN, not invented.
- Saved chart layouts in SQLAlchemy/SQLite (create/load/update/delete) with schema-validated JSON.
- Optional on-demand company profile, available fundamentals and published news from Yahoo, without fake fields or implied guaranteed live coverage.
- Initial stock screener over explicitly known cached daily symbols, with price, change, volume, RSI, and relative SMA filters; save/load/update/delete filters and CSV results.
- Research-first navigation available even before any paper portfolio profile is created.

## Technical boundaries
- Same saved raw OHLCV data underlies Market Explorer, Charts and Screener. No new brokerage or order execution.
- Free Yahoo coverage and historical retention are limited; all quotes and derived metrics are labeled historical or cached.
- VWAP here resets by **UTC date**, not the true exchange's market session. It is deliberately restricted to intraday bars; exchange-calibrated sessions require more exchange metadata in a subsequent increment.
- Yahoo fundamentals and news are best effort and requested explicitly; missing fields are omitted rather than fabricated.
- Screener is not a global stock universe or real-time provider screener. It skips missing/insufficient daily data.
- Streamlit Community Cloud cannot guarantee durable SQLite storage. Local PC launch: streamlit run app.py.
- Layout and screener JSON configs are versioned. No arbitrary strategy code is executed.
- Tested numerics via independent references, lookahead invariants, provider-failure recovery, layout migration/reload, and existing paper-trading regressions. 
