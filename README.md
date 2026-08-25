# Stock Market Analyzer

A local stock research and paper-trading lab. It uses Yahoo Finance for market data, technical features, return-based predictions, and a simulated portfolio. It never sends brokerage orders.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Streamlit app (recommended)

```powershell
$env:PYTHONPATH = "src"
streamlit run streamlit_app.py
```

## Optional FastAPI run

```powershell
$env:PYTHONPATH = "src"
uvicorn stockmarket.api:app --reload
```

## CLI sanity check

```powershell
python StockMarketAnalyzer.py
```

## Test

```powershell
$env:PYTHONPATH = "src"
pytest -q
```

## GitHub and Hosting

- CI pipeline: `.github/workflows/ci.yml`
- Streamlit runtime config: `.streamlit/config.toml`
- Deployment instructions: `DEPLOYMENT.md`

This is a research/demo tool. Historical model metrics do not guarantee future performance, and market data may be delayed or incomplete.
