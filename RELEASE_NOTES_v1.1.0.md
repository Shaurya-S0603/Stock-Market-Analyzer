# QuantEdge v1.1.0 - Research Intelligence

QuantEdge v1.1.0 upgrades the paper AI Trader from single-label entry/exit behavior to a lifecycle-aware, multi-factor research engine.

The application remains a **research and paper-trading simulator only**. No brokerage integration or real-money execution route is included.

## Position lifecycle intelligence

- manual and allocation-driven purchases are no longer treated as disposable positions on the next model cycle;
- manual/rebalance purchases receive a 12-bar acquisition grace window before model-driven liquidation is permitted;
- strategy-originated entries receive a shorter 3-bar stabilization window;
- a hard cost-based stop may still protect the paper portfolio immediately;
- pre-entry trailing highs cannot instantly stop out a freshly allocated manual position.

## Multi-factor exit intelligence

A single Sell label is no longer sufficient to liquidate an open paper position.

Model-driven exits now evaluate:

- cost-adjusted model edge;
- calibrated profitable-outcome probability;
- tactical momentum;
- medium-horizon daily momentum;
- trend structure and persistence;
- price/volume confirmation;
- position origin and bars held.

Confirmed bearish exits require multiple negative factors. Confidence-decay exits also require negative research context, while time exits require non-positive conviction.

## Research-informed features

The model feature set now includes:

- 24-bar tactical return;
- 20-session daily momentum;
- 60-session daily momentum with causal warm-up fallback;
- volume shock;
- price/volume confirmation;
- 24-bar trend persistence.

These features are added to the existing leakage-safe 60d/1h tactical and 6mo/1d completed-daily context pipeline.

## Research conviction

QuantEdge now computes a bounded multi-factor research score from model edge, calibrated probability, momentum, trend, and volume information.

The score affects:

- opportunity ranking;
- paper entry sizing;
- strongly contradictory entry vetoes;
- Sell confirmation;
- decision explanations and audit visibility.

Positive research conviction can improve priority within the available cycle budget, but never raises the user's configured per-entry allocation ceiling. Hard cash, exposure, sleeve, whole-share, daily-loss, and correlation controls remain binding.

## Allocation semantics

Portfolio allocations remain capital ceilings and portfolio intent. They are not automatic Sell instructions.

The onboarding Balanced profile is now aligned with the current v1 paper-trader policy so reconfiguring a portfolio no longer silently restores older conservative defaults.

## Research foundations

`RESEARCH_FOUNDATIONS.md` documents the mapping from the supplied investment literature into testable system behavior. Literature-derived ideas are treated as hypotheses to validate rather than universal trading rules.

## Regression coverage

New tests cover:

- fresh manual/rebalance position + immediate Sell label = HOLD;
- hard stop during acquisition grace = permitted paper exit;
- bearish exit after grace requires multi-factor confirmation;
- unsupported Sell label after grace = HOLD;
- confidence decay requires negative research confirmation;
- AI Trader full-position Sell after valid bearish confirmation;
- research conviction bullish/bearish separation;
- strong contradictory research can block an otherwise eligible entry;
- manual allocations receive the longer lifecycle grace period.

Release publication remains gated by GitHub Actions on Python 3.12, 3.13, and 3.14.
