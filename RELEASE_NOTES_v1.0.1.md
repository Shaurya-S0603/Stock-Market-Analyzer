# QuantEdge v1.0.1

This patch fixes an overly conservative AI Trader entry pipeline in the **paper-trading simulator** and retunes the default objective toward higher risk-adjusted simulated returns.

## AI Trader entry policy

- replaces the binary trading evidence gate with graded evidence:
  - strong evidence: normal simulated sizing;
  - acceptable evidence: permitted at 65% sizing;
  - weak evidence: still rejected;
- uses an edge-aware calibrated-confidence requirement instead of a fixed 65% entry threshold;
- keeps a hard 52% minimum profitable-outcome probability for paper BUY entries;
- lowers the default cost-adjusted Buy edge threshold from 0.50% to 0.30%;
- raises the default simulated entry budget from 5% to 7.5%;
- raises the default interactive Balanced exposure ceiling from 60% to 70%;
- preserves the 3% daily realized-loss stop and existing cash, symbol-sleeve, exposure, whole-share, and correlation constraints.

## Portfolio optimizer

The optimizer now emphasizes expected cost-adjusted edge more directly and uses a square-root volatility penalty instead of allowing volatility scaling to dominate the ranking. Borderline evidence receives a sizing haircut rather than full allocation.

## Consistency

The Streamlit AI Trader and standalone `paper_worker.py` now use aligned Balanced defaults so scheduled and interactive paper cycles follow the same policy.

## Regression coverage

New tests verify that:

- borderline-but-positive model evidence can participate at reduced size;
- materially weak evidence remains rejected;
- strong edge can earn confidence relief without falling below the 52% hard floor;
- a valid paper BUY below the old 65% confidence threshold produces a non-zero quantity;
- opportunity ranking and execution use the same confidence requirement;
- the Balanced worker profile retains its 3% daily loss limit.

Research and simulation only. No brokerage or real-money order route is included.
