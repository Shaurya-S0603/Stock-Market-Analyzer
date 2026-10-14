# QuantEdge Phase 5: Operations and verification

## Start locally
Install with pip install -r requirements.txt and run streamlit run app.py. No paid account is needed. The standalone one-cycle local simulation worker is python workspace_worker.py (offline data by default). Explicit historical refresh requires --refresh. To run periodically, configure a scheduler yourself. Streamlit Community Cloud's local SQLite is ephemeral.

## Backup and restore
Data Management creates SQLite online snapshots of committed WAL transactions from both the workspace and, if present, legacy paper account. The ZIP contains workspace.sqlite and optional paper.sqlite plus SHA256 checksums in manifest.json. The user downloads it privately; backups are not encrypted. A restore checks allowed filenames, uncompressed sizes, hashes, database integrity and expected workspace tables before staging new SQLite files to a new directory. It never overwrites the live SQLite databases. To activate recovery, stop all Streamlit and worker processes, set QUANTEDGE_WORKSPACE_DB and PAPER_DB_PATH to the returned paths, then restart and verify accounts.

## OHLCV import/export
CSV exports UTC-offset timestamps, prices, volume, provider and adjustment basis. Strict imports enforce timezone-aware dates, validated OHLCV, unique timestamps, a single consistent provider and adjustment basis. Existing candle revisions and provenance conflicts are blocked to protect backtest/strategy checkpoints. Data import is bounded by file size and row count.

## Verification evidence
CI compiles the app and workers, runs the complete pytest suite on Python 3.12/3.13/3.14, writes JUnit evidence, and generates an independent feature-to-test JSON report from executed results. Every required feature group must have executed passing test modules. The reports and JUnit XML files are available as Actions artifacts. This supports a bounded *automated test certificate*, not blanket certification of all possible runtime scenarios.

## Known limits and recovery actions
- No live brokerage connectivity or real-money order execution.
- No guaranteed real-time data, 24/7 worker uptime, phone push/email alert delivery or profitable returns.
- Existing AI Trader and strategy simulation portfolios stay in separate databases.
- Release CI alone cannot verify a physical mobile device or hosted Streamlit deployment; manually inspect them after deployment.
- If history from the provider is revised, stop strategy simulations and inspect rather than overriding existing checkpoint assumptions.
- Keep backups private, inspect portfolio balances after restoring, and do not place them in a public GitHub repository.
