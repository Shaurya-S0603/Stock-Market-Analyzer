# QuantEdge v2.1.1: Streamlit Website Tutorial and Public Demo Safety

QuantEdge remains a free, Streamlit-only stock research and simulated trading practice website.

## What's new
- **Start Here** tutorial page guides first-time visitors through chart research, strategy builder, historical backtests, comparisons, manual paper orders and alerts.
- One-click, entirely **synthetic** QEDMO dataset (320 daily candles) and saved tutorial SMA/RSI rule to experiment without a data-provider request.
- **Public demo mode** uses a distinct temporary SQLite workspace for every Streamlit browser session, preventing visitors from sharing writable practice accounts. Set QUANTEDGE_PUBLIC_DEMO = "1" in root-level Streamlit Community Cloud secrets.
- Ordinary private local use retains persistent SQLite storage.
- [Full website deployment and use tutorial](docs/STREAMLIT_WEBSITE_TUTORIAL.md) and updated README/DEPLOYMENT.md.
- New automated tests cover tutorial startup, fictional candle validation, temporary session isolation, and persistent local path.

## Streamlit Community Cloud
Select:
- GitHub repository: Shaurya-S0603/Quant-Edge-Terminal
- Branch: main
- Main app path: app.py
- Python: 3.12
- Advanced settings > Secrets: QUANTEDGE_PUBLIC_DEMO = "1"

Deploy through your own [Streamlit workspace](https://share.streamlit.io). This GitHub release alone does **not** deploy a public Streamlit site.

## Warnings
The fictional example is not a tradable symbol or real market forecast. Public demo storage is ephemeral: users should export their session if they want to preserve it. Free market data may be delayed, incomplete or rate-limited. Paper trades are historical simulations, not executable brokerage orders. Do not upload private financial records to a public demo.
