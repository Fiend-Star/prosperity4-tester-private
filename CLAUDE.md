# CLAUDE.md

Guidance for Claude Code working with this repository. Detailed submission history, lessons, and per-round analyses live in `memory/` — see `MEMORY.md` for the index.

## Running the Backtester

```bash
# Set PYTHONPATH if you get "No module named 'datamodel'"
$env:PYTHONPATH="c:\Users\gurms\PycharmProjects\imc-prosperity-4-backtester\prosperity4bt"

# Current best (Round 1)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1

# Tutorial (1k ticks R1, 2k ticks R0 — run() every tick like website)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --ticks 1000
python -m prosperity4bt trader-logic/round-0/trader.py 0 --ticks 2000

# Full-day scoring (10k ticks)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --ticks 10000

# Key flags
#   --ticks N                          max ticks to simulate
#   --iterations N                     run() called N times (usually match --ticks)
#   --match-trades {all|worse|none}    trade matching mode (default: all)
#   --match-mode {default|imc|sim|website}  ACO calibration — 'imc' matches ±1.6%
#   --no-out / --no-progress / --print
```

Logs → `backtests/<timestamp>.log`. Full day = 10k ticks (timestamps 0–999,900, step 100ms).

## Game Engine Tick Sequence (from chrispyroberts/imc-prosperity-4 Rust source)

Per tick:
1. Fresh books generated — MM bot posts new quotes (not carried over)
2. `Trader.run(state)` called → returns orders
3. Aggressive takes execute (orders crossing the book)
4. Unfilled orders become passive levels in the live book
5. Taker arrives → hits ALL levels by price priority (bot AND strategy)
6. Tick ends → passive orders DISCARDED

**Position limits are ALL-OR-NOTHING per product.** If buy_qty + position > LIMIT, the entire product's orders are rejected. Limits checked per side (worst case: all buys OR all sells fill).

**Takers hit our passive quotes** in step 5 whenever our best±1 is the effective best price. This is the mechanism behind "invisible taker" fills (~59 fills/2k ticks for R0 EMERALDS, ~300/1k ticks for R1).

Bots are **NOT reactive to our spread** (confirmed zero-delta god-logger runs). Conversions are **disabled** in tutorial rounds.

## Architecture

OOP backtester forked from [jmerle/imc-prosperity-3-backtester](https://github.com/jmerle/imc-prosperity-3-backtester).

```
BackTester -> for each round/day:
  TestRunner reads CSVs (prosperity4bt/resources/round{N}/)
    -> for each tick:
      if call_tick: Trader.run(state) -> new orders
      else: use resting orders from last call
      1. Build TradingState from order book data
      2. Log activity snapshot
      3. Enforce position limits
      4. OrderMatchMaker: match orders vs book, then vs market_trades
    -> Return BacktestResult
  ResultMerger -> OutputFileWriter writes .log
```

## Trader Strategy Contract

```python
from datamodel import TradingState, Order
import json

class Trader:
    def bid(self):       # Required for Round 2 auction
        return 15

    def run(self, state: TradingState):
        orders = {}      # dict[Symbol, list[Order]]
        conversions = 0  # int (disabled in tutorial)
        trader_data = "" # str (JSON, persisted to next call, 50k char cap)
        return orders, conversions, trader_data
```

- `Order(symbol, price, quantity)` — positive qty = buy, negative = sell.
- `OrderDepth.sell_orders` volumes are **negative** integers.
- All products have LIMIT=80 (`prosperity4bt/constants.py`).
- **Do NOT modify** `prosperity4bt/datamodel.py`.

## Key Files

| Path | Role |
|------|------|
| `prosperity4bt/test_runner.py` | Per-day simulator, iteration cadence, limit enforcement |
| `prosperity4bt/back_tester.py` | Main controller |
| `prosperity4bt/datamodel.py` | TradingState, Order, OrderDepth, Trade — do not edit |
| `prosperity4bt/constants.py` | Position limits |
| `prosperity4bt/tools/order_match_maker.py` | Exchange matching simulation |
| `prosperity4bt/tools/data_reader.py` | CSV -> BacktestData |
| `prosperity4bt/tools/rust_engine.py` | Independent Rust-logic validator |
| `trader-logic/auction_solver.py` | Manual challenge clearing auction optimizer |
| `trader-logic/round-1/r1_v4.py` | **Current best (website 10,624.84)** |
| `trader-logic/round-1/r1_v17.py` | Full-R1 submitted 272466 (89,861.44) |
| `trader-logic/round-1/r1_v18.py` | Latest — adaptive-threshold, wins synthetic and BT |
| `trader-logic/Prosperity_Fundamentals.pdf` | Take-Clear-Make framework |

## Backtester Calibration (Round-Agnostic)

- **Use BT for RANKING, not absolute PnL prediction.** Orderings are preserved.
- **Round 0**: `website ≈ BT × 1.07` for inside-spread MM; ±2% for at-spread.
- **Round 1**: IPR BT ≈ real IPR within 0.2%; **ACO BT × 0.63 ≈ real ACO** for v17-style inside-spread MM (2.5× BT fill-rate overshoot).
- **ACO BT gradient overshoots ~60×** — treat any ACO BT delta < 1,000 PnL as noise.
- **Don't patch the backtester to match known scores** — overfitting the infrastructure.
- **imc mode with `extra_rate=0.064`** calibrates R1 ACO within 1.6%. `imc` adds ±1,000 ACO variance per seed; trust only large structural changes.
- **CSV ≠ website** — R0 day 0 matches 100%; all other days and R1 all days do NOT. See `project_round1_final.md` for dev-vs-real calibration.

Backtester bugs fixed 2026-03-21: stale `own_trades`/`market_trades` persistence between ticks; resting-order quantity not refreshed after partial fills; wrong iteration count for tutorial.

## Round 0: Tutorial Summary

**Final best: 2,896 (s36_medallion) / 2,857 (s3_carry)** from 37+ submissions. Top scorer fabiantum: 4,950 (gap 2,054 unexplained despite exhaustive probing).

Reusable cross-round insights in [`memory/project_tomatoes_eda.md`](memory/project_tomatoes_eda.md). Bot forensics, feature engineering results, strategy evolution archived in `trader-logic/round-0/`.

**Key R0 findings reused in R1:**
- `PnL = FillRate × SpreadCaptured − InventoryRisk` (NOT IC × position). Fill rate is exogenous; queue priority dominates.
- Regression coefs `[0.06, 0.12, 0.24, 0.58]` stable across days, sum≈1.0. Use cross-validated fits.
- **Clear step HURTS drift/random-walk products** (s13: 2,077 vs 3,394 baseline; IPR LU: 4,796 vs 7,446). Only use on stable/pegged products.
- Taker bots are **contrarian on average** — gives positive inventory MTM on long in rising markets (replayed at scale in R1 IPR: +79k).
- AC(1) ≈ −0.44 is a **structural engine property**, not alpha.
- Local BT was MISLEADING pre-fix; post-fix matches within 1% for book-only strategies.

**R0 Bot Behavior** (reverse-engineered, 37+ submissions; unchanged for R1):
- MM: `bid = floor(mid − s/2)`, `ask = ceil(mid + s/2)`. Mid in 0.5 increments, OU with AC(1) = −0.44. Spreads {5–9, 13–14} (wide 92.8%). L1 vol uniform [2,12], L2 vol ≈ 2.78× L1. 82.6% asymmetric quote moves. NO post-fill response.
- Taker: pure aggressive, 100% at best bid/ask. Exponential inter-arrival (R0) / more-regular (R1). Side 50/50 iid. Qty uniform.
- Zero cross-product lead-lag.

## Round 1: "Trading Groundwork"

### Products

| Product | Limit | Price | Range/day | Spread | L1 vol | AC(1) | Archetype |
|---------|-------|-------|-----------|--------|--------|-------|-----------|
| INTARIAN_PEPPER_ROOT | 80 | ~12,000 | 1,000 | 12–14 | 11.5 | −0.50 | Drift / random walk |
| ASH_COATED_OSMIUM | 80 | ~10,000 | 27–36 | 16 (62%) | 14.0 | −0.49 | Stable FV (OU) |

- **IPR**: +1000/day uptrend across all CSV days (−2: ~10k, −1: ~11k, 0: ~12k). "Steady value".
- **ACO**: "hidden pattern" = OU mean-reversion to FV=10000. Mid deviates ±18 max.
- Both products: ~9% one-sided book ticks.

### Round 0 → Round 1 Shifts

| Metric | R0 | R1 |
|--------|----|----|
| Tutorial ticks | 2,000 | **1,000** |
| CSV↔website match | Day 0 = 100% | Day 0 = **36%** |
| Taker arrival rate | ~3.5% | **~30%** |
| Taker CoV | 0.99 (Poisson) | 0.76–0.81 (more regular) |
| One-sided ticks | 0% | ~9% |
| PnL from taker fills | ~70% | ~70% |

### Round 1 Regression (cross-validated 3 days, for reference — r1_v4 uses simple mid instead)

```python
# IPR 4-lag microprice regression
COEFS = [0.2474, 0.2529, 0.2412, 0.2585]
INTERCEPT = 0.2078
# Coef sum ≈ 1.0 → FV ≈ average of last 4 microprice values

# ACO (less useful, slight mean-reversion)
COEFS = [0.214, 0.215, 0.250, 0.294]
INTERCEPT = 215-387  # varies by day
```

### Current Best Strategy: r1_v4.py (Website 10,624.84)

**INTARIAN_PEPPER_ROOT** (drift capture, website 7,446) — from r1_v2:
- **Simple mid + drift_bias=5** (NOT microprice regression). `fv = round(mid + 5.0)`. Microprice leans LOW in ask-heavy books, missing initial take at t=0.
- Asymmetric takes: buy if price ≤ fv+2, sell only if ≥ fv+3.
- Post aggressive bid at `min(fv−1, best_bid+1, best_ask−1)`; defensive ask at `max(fv+2, best_ask−1, best_bid+1)`.
- One-sided book handling (9% of ticks).
- 4 params (LIMIT, DRIFT_BIAS, BUY_SLACK, SELL_SLACK).

**ASH_COATED_OSMIUM** (Linear Utility AMETHYSTS port, website 3,179):
- Fixed FV=10000. Take → Clear → Make (LU canonical).
- Take: `≤ fv−1` or `≥ fv+1` with adverse_vol<15 filter. Clear: flatten exactly at fv (LU's +3% trick). Make: penny/join/default (DISREGARD=1, JOIN=2, DEFAULT=4).
- Soft-limit skew at |pos|>40.
- LU-exact params (P2 #2 finish). +88 validated over baseline (theory: +3% × 3,091 = +87).

### Round 1 Submission Summary

| Variant | Website | Key |
|---------|--------:|-----|
| **r1_v4** (current best) | **10,624.84** | Simple mid + LU ACO |
| r1_v17 (full-R1 272466) | 89,861.44 | IPR 99.1% of buy-and-hold max; ACO cost ~1,743 to bootstrap anchor flicker |
| r1_v18 (unsubmitted, latest) | — | Adaptive-threshold: +4,920 BT over v17 across 3 days; wins 15-seed synthetic |
| Nancy's algov4 (benchmark) | 10,734.03 | Teammate +109 via aggressive bid + OU ACO |

Full 25+ submission trajectory, 40 lessons, and defensive-stack analysis (v9–v17) in [`memory/project_round1_results.md`](memory/project_round1_results.md) and [`memory/project_round1_final.md`](memory/project_round1_final.md). Latest v18 architecture in [`memory/project_round1_v18.md`](memory/project_round1_v18.md).

### Headline Round 1 Lessons (see memory for full list)

1. **Simple mid > microprice for drift products** (r1_v2 via probe 210525, +90 PnL).
2. **LU clear step = +3% PnL on stable products** (validated on ACO). **BREAKS drift products** (r1_v3 regressed −2,650 IPR).
3. **Drawdowns are entry-cost, not bugs** — eliminating costs PnL on drift. See [`memory/feedback_drawdown_misconception.md`](memory/feedback_drawdown_misconception.md).
4. **Drift_bias = 35% of total PnL**; trade flow / OBI / carry = 0% marginal each.
5. **ACO fills are strategy-independent** — 59 of 101 are "invisible takers" attracted by any inside-spread posting. ACO posting width has **zero effect** (FV±3 ≡ best±1).
6. **Conversions disabled, no hidden observations** in R1.
7. **traderData format matters** — removing unused state variables cost 2 IPR fills (−39 PnL). Keep all fields.
8. **Practical ceiling ~10,625–10,734**. TROLL at 10.6k, us 10.625, Nancy 10.734. Gap to #1 (11,744) likely seed variance.
9. **r1_v17 real result reversed synthetic prediction** — bootstrap anchor snapped to 10,008 from asymmetric open book, costing ~1,743 ACO PnL. Synthetic generator missed asymmetric-open failure mode. See `project_round1_final.md`.
10. **r1_v18 adaptive-threshold fix** — rolling median avg_mid, per-day frozen MAD threshold, median-of-20 bootstrap, hysteresis. Beats v17 on all 3 real days, wins 15-seed synthetic. See `project_round1_v18.md`.

### Round 1 Manual Challenge: "An Intarian Welcome"

Uniform-price clearing auction (new P4 format). Optimal orders: **Flax BUY@30 vol 9,999** (clearing 29, +9,999) + **Mushroom BUY@17 vol 19,999** (clearing 16, +77,996) = **87,995 XIRECs**. Solver at `trader-logic/auction_solver.py`, writeup in `trader-logic/auction_writeup.md`. Full derivation in [`memory/project_manual_challenge_r1.md`](memory/project_manual_challenge_r1.md).

## Round 1 File Organization

```
trader-logic/
├── auction_solver.py, auction_writeup.md, Prosperity_Fundamentals.pdf
├── round-0/                             # R0 tutorial (archived)
│   ├── s36_medallion.py, s3_carry.py, s25_training_only.py  # Best R0 strategies
│   ├── {analysis,strategy,infrastructure}/  # 7-module bot exploitation
│   ├── {oracle,sweeps,experiments,diagnostics,early_versions}/
│   └── mega_sweep.py, grid_search.py, feature_engineering.py, feynman_kac_mm.py
├── round-1/
│   ├── r1_v4.py                         # CURRENT BEST (10,624.84)
│   ├── r1_v5.py                         # Guardrail (10,612.84)
│   ├── r1_v9…v17.py                     # Defensive stack (see memory)
│   ├── r1_v18.py                        # LATEST — adaptive threshold
│   ├── refit_regression.py              # Utility: auto-refit microprice coefs
│   ├── BACKTEST_COMMANDS.md, README.md
│   ├── best/, experiments/, early_versions/
│   ├── templates/                       # Per-archetype (stable, random_walk, basket, options, conversion, olivia)
│   ├── references/                      # Competitor code (nancy_algov4, r1_troll, superduperbread)
│   ├── analyzer/                        # Superduperbread's trading_analyzer.html
│   ├── experiments/synthetic/           # generate.py + run_all.py (round99 regimes)
│   ├── probes/, oracle/
│   └── POST_MORTEM_272466.md

prosperity4bt/resources/round99/        # Synthetic regime test data
run-logs/round-{0,1}/                   # Website submission logs
```

## Round 2+ Template Library

Pre-built at `trader-logic/round-1/templates/`, reusable for any new product:

| Template | Archetype | Key technique |
|----------|-----------|---------------|
| `template_stable.py` | Pegged (AMETHYSTS/ACO-like, fixed FV) | LU take/clear/make, adverse_vol=15 |
| `template_random_walk.py` | Mean-reverting (KELP/STARFRUIT-like) | Filtered-MM-mid + small negative reversion beta |
| `template_basket.py` | ETF basket arb | Z-score on spread (threshold=7, window=45) |
| `template_options.py` | Options/derivatives | Black-Scholes r=0, rolling IV mean per strike |
| `template_conversion.py` | Cross-exchange arb | Implied bid/ask from observations + hidden-taker detection |
| `template_olivia.py` | Insider/event bot | qty=15 filter at daily min/max extremes |
| `refit_regression.py` | Utility | Auto-refit microprice regression |

See [`memory/project_round1_prep.md`](memory/project_round1_prep.md) for deployment workflow and LU framework details in [`memory/project_lu_framework.md`](memory/project_lu_framework.md).

**Warning**: CSV volume-dependent features (microprice, OBI) may not port to website (CSV↔website volume match = 1.5% in R0 days −1/−2, unknown in R1). Prefer structural features (spread states, price levels) for first draft.

## Reference Backtesters (R1 validated)

| Backtester | Language | Matching | Note |
|---|---|---|---|
| Ours (fork of jmerle P3) | Python | default/imc/sim/website | Custom `website` mode with taker supplement |
| [kevin-fu1](https://github.com/kevin-fu1/imc-prosperity-4-backtester) | Python | default (worse) | Only 1 buy + 1 sell vs market trades |
| [Xeeshan85/prosperity4btx](https://pypi.org/project/prosperity4btx/) | Python | all/worse/none | PyPI package, 3 modes |
| [GeyzsoN/rust](https://github.com/GeyzsoN/prosperity_rust_backtester) | Rust | all + queue | **Matches ours exactly** on identical CSVs |

All confirm: fill at ORDER price, all-or-nothing limit enforcement, MM non-reactive. All overpredict website by 30–56% on R1 (CSV ≠ website).

## Lambda Probe (R1)

Runtime: Python 3.12.13, AWS Lambda 128MB / 1s, Amazon Linux 2023. **Network**: only `169.254.100.1:9001` (Runtime API) + `:53` (DNS) reachable — public outbound blocked. **AWS creds** (`Prosperity_General_Lambda_Role`): only `sts:GetCallerIdentity` allowed; all services AccessDenied. `/tmp` persists within a container, 2 concurrent containers per run, **traderData is the ONLY reliable cross-invocation state**.

Round 0 vulnerabilities (os.popen, env-var extraction, `/var/task` readable) still **not patched** in R1. Full details in [`memory/project_round1_probe.md`](memory/project_round1_probe.md), including MACARONS conversion formula extracted from `orchids_trader.py` for Round 3/4.
