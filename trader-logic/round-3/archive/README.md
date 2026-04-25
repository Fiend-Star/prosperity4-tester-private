# Round 3 Archive

Iteration history for R3 strategies. Active strategies live at `trader-logic/round-3/`.

## Active (root)
- `r3_v1.py` — original baseline pure MM ($28k 3-day BT)
- `r3_v3.py` — submitted version 383883 (+structural arbs as insurance, $28k)
- `r3_v7.py` — Wall Mid for VFE breakthrough ($47k 3-day)
- **`r3_v9.py`** — current submission candidate (Wall Mid + safe BS voucher taking, $47k 3-day, +$1k 1k-tick day 0 vs v7)

## v1_iterations/
Early iteration of v1 testing different fair value calculations:
- `r3_v1a.py` — initial OOP refactor
- `r3_v1b.py` — pure MM no IV
- `r3_v1c.py` — inventory-skewed MM (lost money)
- `r3_v1d.py` — plain mid (final v1 winner)
- `r3_v1e.py` — HP wider slack (no improvement)

## failed_experiments/
Strategies that performed worse than baseline:
- `r3_v2.py` — IV quadratic smile z-score (-$1.6k vs v3, wrong timescale)
- `r3_v2b.py` — IV linear smile (-$7.7k vs v3)
- `r3_v4.py` — EDA-driven OBI predictor (-$394k from spread cost)
- `r3_v5.py` — VR(20) directional via VEV_4000 (-$40k/day, spread > signal)
- `r3_v6.py` — aggressive take TAKE_OFFSET=1 (-$80k 3-day, adverse selection)
- `r3_v8.py` — fixed-sigma BS voucher MM (day 0 +$7k, days 1-2 disasters)

## superseded/
- `r3_v3_theta.py` — terminal theta harvest A/B (no effect in BT, didn't ship)
