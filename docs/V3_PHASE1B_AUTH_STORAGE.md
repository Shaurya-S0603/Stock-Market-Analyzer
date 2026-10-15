# Phase 1B: signed identity, PostgreSQL migrations, isolated watchlists

The existing Phase 0 synthetic dashboard and Streamlit v2.1.1 remain intact.

## What is implemented
- Auth.js v5 GitHub OAuth creates an encrypted cookie-based JWT session on Next.js.
- The stable GitHub numeric account ID is used as the internal research owner
  identifier, not the email or username.
- Only a valid server-side session can ask the Next.js BFF to generate a
  two-minute HS256 service JWT with exact issuer and audience for FastAPI.
- FastAPI verifies signature, audience, issuer, expiry, issued-at and subject.
  All watchlist SQL queries are additionally scoped to that subject.
- Alembic revision `qe_v3_0001` manages three dedicated v3 tables. Existing
  Streamlit SQLite tables and stored portfolios are never migrated or changed.
- Watchlists have at most 20 names per account and 50 symbols per list.
- No brokerage connection, actual trades, or public writable demo accounts.

## Setup on a private local computer

1. Provide PostgreSQL DATABASE_URL for the FastAPI process, e.g. your local
   development container's PostgreSQL. Start the database service first.
2. Generate TWO independent random secrets (at least 32 characters):
   `AUTH_SECRET` for the Next.js session and `QUANTEDGE_API_JWT_SECRET`
   shared between Next.js server and FastAPI server.
   Never use the sample CI secrets from the workflow.
3. Register a GitHub OAuth application with local callback
   `http://localhost:3000/api/auth/callback/github`, then set
   `AUTH_GITHUB_ID` and `AUTH_GITHUB_SECRET` **on the Next.js server only**.
   Do not use NEXT_PUBLIC_ for any authentication secrets.
4. Run migrations explicitly from the project root:
   `python -m alembic -c apps/api/alembic.ini upgrade head`
5. Start FastAPI and Next.js as in V3_PHASE0_QUICKSTART.md. Navigate to
   `/watchlists`, sign in with GitHub, create a list and add a ticker.
6. For Compose, provide variables via a private, uncommitted .env file or
   shell environment. Missing variables leave saved research inaccessible.

## Safety and deployment notes
- The BFF returns HTTP 503 when GitHub OAuth/secrets are unconfigured, and HTTP 401 when configured but the user has no valid session. Neither permits anonymous data access.
- The BFF does not accept user-supplied authorization headers. No unsigned
  user-identifying headers are trusted by FastAPI.
- Authenticated research is unavailable rather than falling back to anonymous
  shared storage when secrets or the database are missing.
- POST/DELETE requests require same-origin browser context.
- The research database must be provisioned and migrated before enabling
  the feature. Do not run destructive database migrations without backup.
- Current historical data adapter is opt-in and separate from saved watchlists.
  Neither stored symbol lists nor OAuth sign-in guarantee licensed exchange data.
- Phase 1B includes a short, owner-scoped Redis read cache (15-second TTL,
  invalidated on mutations) and atomic Redis write throttle (60 changes/min/user).
  Set QUANTEDGE_REQUIRE_REDIS=1 for any public deployment so write throttling
  fails closed rather than silently bypassing missing Redis.
- Real-market provider-specific quotas, signed provider fetch jobs and persistent
  strategy/backtest records require an additional reviewed stage.
