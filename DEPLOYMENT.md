# Deployment Guide

## GitHub workflow

Use a feature branch and merge through a pull request. GitHub Actions compiles the project and runs regression tests on Python 3.12 and 3.13.

Do not commit `.venv/`, `.data/`, SQLite files, `.env*`, caches, or Streamlit secrets.

## Streamlit Community Cloud

1. Sign in with the GitHub account that can access `Shaurya-S0603/Stock-Market-Analyzer`.
2. Create an app from the repository.
3. Select branch `main`.
4. Set the entrypoint to `streamlit_app.py`.
5. Use Python 3.12 unless another runtime has been deliberately tested by CI.
6. Deploy.

Dependencies live in root `requirements.txt`; Streamlit configuration is in `.streamlit/config.toml`.

### Persistence

The `.data/` SQLite blotter is suitable for local/demo use but should be considered ephemeral on hosted Streamlit infrastructure. A production multi-user deployment should use a hosted database.

## Pre-deployment checks

```bash
pytest -q
python -m compileall -q StockMarketAnalyzer.py streamlit_app.py src tests
```
