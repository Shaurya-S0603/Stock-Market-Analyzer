# QuantEdge 3.0: Next.js + FastAPI rebuild plan

Source specification: PROJECT PROMPT PERSONAL STOCK.docx, sections 4–15.
The original document explicitly recommends **FastAPI**, not Flask ("flash"
was interpreted using the specification). No real brokerage trading.

## Architecture and release policy

Browser -> Next.js 16 (TypeScript, Tailwind, TanStack Query, Lightweight Charts)
        -> same-origin Next.js API routes/BFF (validates public inputs)
        -> FastAPI (Python analytics and validated strategy execution)
        -> PostgreSQL (future authenticated persistent user data)
        -> Redis (future rate-limited market data cache and job coordination)
        -> scheduled Python worker (future alerts and long backtests)

**Keep the existing Streamlit v2.1.1 app running alongside the migration**.
Merge each feature branch only after Python regression tests, Next production
build, HTTP connectivity and its feature-specific acceptance tests succeed.
Do NOT delete the Streamlit backend or old SQL files until parity, data
migration, and secure rollback procedures are proven.

## Phase 0 — Verified foundation [current branch]
- Next.js/TypeScript/Tailwind single-page personal research terminal.
- FastAPI health, OHLCV, indicator, strategy and backtest demo contracts.
- Real Lightweight Charts display, test-run controls, and status feedback.
- Every displayed QEDMO price is deterministic **fictional** tutorial data.
- No writable global portfolios, login bypass, broker connectors, or live quote claims.
- Local Docker Compose containing API, web, PostgreSQL and Redis.
- GitHub Actions: full Python 3.12/3.13/3.14 regression matrix plus
  additional Node 22 Next build and live API/BFF/DB/Redis integration tests.
Gate: all tests green and real HTTP integration probe passes.

## Phase 1 — Market data, authentication and persistence
- Authoritative provider abstraction, quote retrieval and ingestion service.
- Free/delayed market data, UTC/provenance and adjustment-mode validation,
  explicit provider delays and fallback.
- PostgreSQL SQLAlchemy models, Alembic migrations, per-user watchlists,
  daily/intraday OHLCV, ticker metadata and quote caches.
- Authentication using a supported managed auth provider or Auth.js and
  authorization tests for EVERY user-specific endpoint.
- Redis caching and provider rate-limit/TTL enforcement. No arbitrary
  user-controlled provider URLs.
Gate: migrations both directions, API contract, per-user isolation, provider
mock/rate tests, and Next -> API -> PostgreSQL persistence round trip.

## Phase 2 — Charts and stock research interface
- TradingView Lightweight Charts with all seven specified timeframes.
- SMA/EMA/RSI/MACD/BB/VWAP and volume panels; saved user layouts.
- Marker overlays for backtest fills and simulated paper orders.
Gate: chart browser tests, indicator parity with Python fixtures, provider
timestamp and adjustment consistency tests.

## Phase 3 — Strategy builder and robust backtesting
- Versioned, immutable validated Pydantic JSON rules.
- Reuse tested causal signal/stop/fee/backtest engines from Streamlit codebase.
- Background job queue for longer tests, durable results in PostgreSQL.
- Performance curves, benchmark, drawdown, monthly table, audit of simulated
  executions. Never permit arbitrary user-supplied Python execution.
Gate: no lookahead, cost/cash reconciliation, deterministic reruns, worker
restarts, strategy ACLs and Next BFF requests to saved results.

## Phase 4 — Isolated paper trading and alerts
- Separate real-money-disabled paper accounts, manual/strategy fills with
  explicit consent, strong database transactions and duplicate-fill safety.
- In-app price/indicator/strategy alert history, pause/resume, background
  processing. No guaranteed live/24x7 on sleeping free hosting.
Gate: account isolation, stop-gap behaviour, idempotence, durable restart,
  alert deduplication and API authentication.

## Phase 5 — Screening, fundamentals, deployment and migration
- Fundamentals/news when available, grounded source/date labels,
  cached screening, full loading/error states and accessible responsive UI.
- Student/free hosting deployment documentation and controlled credentials.
- Migrate archived Streamlit SQLite data into PostgreSQL using a verified,
  explicitly user-approved import, with rollback and integrity checks.
- Mobile/desktop browser acceptance, tests and release process.
Gate: all core requirements from document §12 verified on production-like
  services before retiring Streamlit.

## Free-tier deployment tradeoffs (verify before activating)

Suggested: **Vercel Hobby** for Next.js (personal/noncommercial use restrictions
may apply), **Render Free** for the small FastAPI service, **Neon Free
PostgreSQL** for durable development data. The Render Free backend sleeps after
15 minutes idle and can take approximately a minute to wake; a free Render
PostgreSQL instance is NOT durable beyond its stated 30-day expiration. The
Neon free tier has a bounded compute allowance and storage quota. Confirm any
GitHub Student Developer Pack promotions in your own vendor accounts; do not
assume promotional credits apply automatically. Redis and always-on workers
require separate hosting decisions; for early stages optional Redis can be
local only, not falsely claimed to be running 24/7.

Never commit secrets. Vercel server-side FASTAPI_INTERNAL_URL must reference
the actual publicly reachable FastAPI URL once deployed. Browser clients only
call same-origin BFF routes. Do not deploy unprotected writable accounts.

## Phase 1A progress (read-only historical adapter)
- Controlled local opt-in for free, unofficial yfinance historical daily data.
- Explicit provenance, last-session date semantics and unknown provider delay.
- Strict three-window history request, no real-time quote claim or paper-account mutation.
- Small in-process five-minute cache and upstream-concurrency guard.
- Dedicated /market explorer; Streamlit v2.1.1 remains untouched.
- Offline mocked provider tests in full-stack CI; production market-data uptime not certified.
- Follow-up Phase 1B: managed auth, PostgreSQL/Alembic ownership models, Redis
  cache/rate limiting, and per-user data isolation before public write APIs.
