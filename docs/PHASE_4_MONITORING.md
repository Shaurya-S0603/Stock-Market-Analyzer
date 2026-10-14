# Phase 4: Local monitoring and independent paper strategy accounts

QuantEdge 2.0 Phase 4 is an **educational, paper-only** extension. It does not connect to a brokerage, send orders, or transfer real money.

## Preservation and separation

The existing AI Trader, its manual allocations, and its separate paper database are unchanged. New strategy accounts are stored only in the Phase 0/1 workspace SQLite file (QUANTEDGE_WORKSPACE_DB). Each account owns its own cash, quantity, cost basis, fill journal, strategy-version snapshot, and observation checkpoint.

## Activation and data handling

Each account is created paused. Enabling it checkpoints the most recent completed historical bar: old entry signals cannot immediately purchase assets. The latest cached candle is treated as possibly unfinished. Processing catches up only through the penultimate candle, uses signals from the previous completed candle, and simulates fills at the next bar's opening price. This deliberately delayed simulation must not be confused with actual market-time execution. Pausing and re-enabling skips past signals, not retroactively trading them. A revised checkpoint bar or changed price provider/adjustment basis stops the process.

Simulations use whole shares and available simulated cash, exposure ceilings, modeled slippage/commissions, exits, stops, trailing stops, and the optional maximum holding period. Atomic SQLite transactions serialize overlapping processes and commit cash, positions, and fills together. Protective stops on ambiguous bars assume the adverse stop fires first. An actual brokerage account is never touched.

## Local alerts

Supported: price threshold crossing; RSI threshold crossing; price crossing its SMA; and pinned saved-strategy entry/exit rules. New alert rules checkpoint the latest completed bar, avoiding old notifications. One event per rule and bar is persisted, and worker overlap cannot duplicate it. Pausing and resuming does not replay the paused period. Events are viewed **in the app only**. Email/SMS/push notifications are not supplied, and we cannot guarantee live quote data from a free provider.

If an alert's referenced saved strategy version is deleted, the alert will fail closed and report an error. Preserve referenced strategies for continued monitoring.

## Running locally

- Start the app: `streamlit run app.py`.
- In Market Explorer, download saved historical candles.
- Create a versioned rule strategy in Strategy Builder.
- Visit Strategy Simulations to create an independent disabled paper account, then enable it explicitly.
- Use Local Alerts to create alert rules, view events, and pause or delete rules.
- Run `python workspace_worker.py` for **one offline evaluation cycle**. This contacts no external price source by default.
- Run `python workspace_worker.py --refresh` for one explicit best-effort free historical refresh before evaluation.

A local OS task scheduler or cron may invoke the worker repeatedly. Streamlit Community Cloud has ephemeral local storage and does **not** provide a durable background worker. Use persistent local storage for real continuity. The research app never claims guaranteed real-time accuracy, profitability, or automated live trade execution.

## Verification

Tests cover alert triggers, duplicate-event suppression, pause/resume and historical replay protection, independent paper cash, first-activation behavior, single-execution idempotence, checkpoint revision detection, offline worker startup, and Streamlit page import/render. CI checks Python 3.12/3.13/3.14 plus all existing regressions.
