# QuantEdge v2.0.0: Free, Local-First Streamlit Edition

QuantEdge 2 is a Python, Streamlit and SQLite research and simulated-strategy platform without mandatory paid services. The existing v1.1 AI Trader, portfolio logic, Research Lab and risk controls remain available.

## New across Phases 0 to 5
- Market Explorer with cached free historical OHLCV, persistent watchlists, explicit provider provenance and offline fallback.
- Plotly charts, indicators, saved layouts, available company data/news and local technical screening.
- JSON-validated rule builder, deterministic next-open backtester with modeled costs and conservative intrabar stops, saved strategy versions and historical comparisons.
- Independent paused-by-default paper strategy accounts, in-app threshold/indicator/signal alerts and optional one-cycle offline-first worker.
- SQLite online-backup archive of workspace and optional legacy paper database, SHA256 integrity manifest, staged no-overwrite recovery, historical CSV import/export with validation and strict source-revision protection.
- Data Management page with integrity diagnostics and recovery. Automated feature evidence artifacts and CI verification on Python 3.12, 3.13 and 3.14.

## Local setup
Run pip install -r requirements.txt, then streamlit run app.py. Run the optional worker once with python workspace_worker.py; to request best-effort historical data first use python workspace_worker.py --refresh.

## Explicit limits
Research/paper-only. No broker transactions, guaranteed profitable trading, complete real-time market feed, cloud-persistent SQLite storage, or guaranteed 24/7 worker. The newest historical bar may be provisional. In-app alerts are not phone push notifications. Historical VWAP is based on UTC date. CI verifies tests only, not a physical hosted-device workflow or the accuracy of the third-party market data. Backups are unencrypted and should be stored privately.
