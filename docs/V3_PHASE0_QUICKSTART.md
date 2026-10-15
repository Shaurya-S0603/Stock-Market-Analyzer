# QuantEdge v3 Phase 0 Quickstart

A verified full-stack research DEMO runs in parallel with Streamlit v2.1.1.
The new app is on branch v3-phase0-nextjs-fastapi-foundation until tests pass.

## Docker (recommended for first integration)
Requirements: Docker Engine and docker compose.

    docker compose -f infra/compose.yml up --build

Visit http://localhost:3000 for the Next.js dashboard.
Visit http://localhost:8000/docs for FastAPI OpenAPI.
Visit http://localhost:8000/api/v1/health/dependencies to check actual
PostgreSQL and Redis handshakes. The local sample DB credentials are **not**
for a public deployment.

## Start servers without Docker
Use Python 3.12 and Node.js 22 (Next.js 16 needs Node >=20.9):

    python -m pip install -r requirements.txt -r apps/api/requirements.txt
    python -m uvicorn apps.api.main:app --reload --port 8000

In another shell:

    cd apps/web
    npm install
    cp .env.example .env.local
    npm run dev

Visit http://localhost:3000 and verify the API connection banner. Local
PostgreSQL and Redis are optional for the fictional demo; dependency health
truthfully reports "not configured" without environment variables.

## Initial proof of functionality
1. Next.js page shows a fictional QEDMO ticker and 320 daily candles.
2. Lightweight Charts renders price candles, crosshair and toggleable SMA.
3. API health indicates the research API is connected. The URL is never a
   broker or a live market-data feed.
4. "Run fictional backtest" sends a validated request through Next.js to
   FastAPI, reusing the previous causally tested Python backtest.
5. API /api/v1/market/MSFT/ohlcv returns 404 until a real data provider is
   explicitly integrated, rather than fabricating live prices.
6. GitHub Actions must pass both the old Python test suite and the new
   production Node build + full HTTP/Postgres/Redis integration probe.

## Current limitations
No real-data provider, authentication, durable account write, Redis caching,
background jobs, or cloud deployment in **Phase 0**. Database/Redis are
probed for connectivity only, not used to hold portfolios. Do not expose
public write endpoints until authentication and storage isolation are done.

For local durable research during the rebuild, keep using the existing
Streamlit entrypoint:

    streamlit run app.py
