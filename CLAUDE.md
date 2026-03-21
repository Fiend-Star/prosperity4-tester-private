# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Backtester

```bash
# Set PYTHONPATH if you get "No module named 'datamodel'"
$env:PYTHONPATH="c:\Users\gurms\PycharmProjects\imc-prosperity-4-backtester\prosperity4bt"

# Run on all days in a round
python -m prosperity4bt trader-logic/round-0/trader.py 0

# Run specific round-day
python -m prosperity4bt trader-logic/round-0/trader.py 0--1

# Simulate WEBSITE test conditions (2k ticks, 1000 iterations with resting orders)
python -m prosperity4bt trader-logic/round-0/trader.py 0--1 --ticks 2000 --iterations 1000

# Simulate FINAL SCORING conditions (10k ticks, every tick)
python -m prosperity4bt trader-logic/round-0/trader.py 0 --ticks 10000

# Key flags
#   --iterations N                     run() called N times per day (resting orders between)
#   --ticks N                          max ticks to simulate
#   --match-trades {all|worse|none}    trade matching mode (default: all)
#   --no-out                           skip saving .log file
#   --no-progress                      hide progress bars
#   --print                            show trader stdout
```

Output logs go to `backtests/<timestamp>.log`.

## Simulation Mechanics (Confirmed by IMC)

- Full trading day = **10,000 rows** per product (timestamps 0-999,900, step 100ms)
- **Test submission**: run() called **1,000 times** over 10,000 ticks (every ~10th tick)
- **Final scoring**: run() called **10,000 times** (every tick)
- Matching engine runs **every tick** regardless of whether run() is called
- Orders that don't fill immediately become **resting quotes** hit by bots between run() calls
- Position limits checked **per side independently** (worst-case: all buys fill OR all sells fill)
- Bots have **heterogeneous activity frequencies** — ~400ms clustering is a bot cadence, not a system constraint
- Trades match against **CURRENT tick's book** (MM updates BEFORE matching, confirmed 100%)
- **Bots are NOT reactive to our spread width** — diag_tight confirmed same fill count (1,969 vs 1,950) regardless of posting width
- **Conversions do NOT work** in tutorial round (diag_conversions = 2,518, WORSE)

## Architecture

OOP backtester based on [jmerle/imc-prosperity-3-backtester](https://github.com/jmerle/imc-prosperity-3-backtester).

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
  ResultMerger consolidates -> OutputFileWriter writes .log
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
        conversions = 0  # int (unused in tutorial)
        trader_data = "" # str (JSON, persisted to next call, 50k char cap)
        return orders, conversions, trader_data
```

**Order format:** `Order(symbol, price, quantity)` — positive qty = buy, negative = sell.
**OrderDepth:** `sell_orders` volumes are **negative** integers.
**Position limits:** EMERALDS: 80, TOMATOES: 80 (`prosperity4bt/constants.py`).
**Do NOT modify** `prosperity4bt/datamodel.py`.

## Key Files

| Path | Role |
|------|------|
| `prosperity4bt/test_runner.py` | Per-day simulator, iteration cadence, limit enforcement |
| `prosperity4bt/back_tester.py` | Main controller |
| `prosperity4bt/datamodel.py` | TradingState, Order, OrderDepth, Trade — **do not edit** |
| `prosperity4bt/constants.py` | Position limits |
| `prosperity4bt/tools/order_match_maker.py` | Exchange matching simulation |
| `prosperity4bt/tools/data_reader.py` | CSV -> BacktestData |
| `trader-logic/round-0/` | All trading strategy files |
| `trader-logic/round-0/strategy/` | 7-module bot exploitation pipeline (for Round 1+) |
| `trader-logic/round-0/analysis/` | Offline analysis scripts (bot fingerprinting, adverse selection) |
| `run-logs/round-0/` | Website submission logs (JSON: activitiesLog, graphLog, positions) |
| `mm_bot_profiler.py` | MM bot behavior analysis (8 analyses) |
| `trader-logic/round-0/feature_engineering.py` | 207-feature exhaustive scan |
| `trader-logic/round-0/feynman_kac_mm.py` | OU calibration + HJB PDE solver |
| `trader-logic/Prosperity_Fundamentals.pdf` | Guide: Take-Clear-Make framework, FV estimation |

## Bot Behavior (Reverse-Engineered)

### Market Maker Bot
- Quote formula: `bid = floor(mid - spread/2)`, `ask = ceil(mid + spread/2)`
- Mid changes: always multiples of 0.5, O-U mean-reversion (lag-1 autocorr = -0.44)
- Spread states: {5,6,7,8,9,13,14}. Wide (13-14) 92.8%, tight (5-9) 7.2%
- L1 vol: uniform [2-12], L2 vol: ~2.77x L1. Symmetric 93%+ of ticks
- 82.6% of quote moves are ASYMMETRIC (bid and ask move independently)
- Post-fill response: <0.3 ticks — NO exploitable lag after fills
- Narrow spreads: 1 tick duration, triggered by |mid move| >= 3, NOT predictable
- Updates quotes BEFORE matching (trades see fresh book, 100% confirmed)
- Volume imbalance (bid!=ask) on 6.6% of ticks — 76% directional hit rate but already captured by microprice

### Taker Bot (ONE per product)
- TOMATOES: cadence mean 2,430ms, qty uniform [2,3,4,5], side 50/50 random
- EMERALDS: cadence mean 4,910ms, qty uniform [3,4,5,6,7,8], side 50/50 random
- 100% of trades at best bid or best ask. Pure aggressive taker.
- Timing, size, side are ALL random — no predictable pattern
- Adverse selection rate: 1.5% TOMATOES, 0% EMERALDS (almost all fills are profitable)

### Cross-Product
- Zero lead-lag between EMERALDS and TOMATOES (all |r| < 0.02)

## Feature Engineering Results (207 features, OOS validated)

**Top 5 features (identical ranking both days):**
| Feature | r | What it captures |
|---------|---|------------------|
| vol_imb_dist_weighted | +0.62 | Volume imbalance weighted by 1/distance from mid |
| vol_imb_l2 | +0.617 | L2 volume imbalance |
| gap_asymmetry | -0.607 | (bid1-bid2) - (ask2-ask1) — L2 price structure |
| weighted_mp_dev | +0.600 | L1+L2 weighted microprice - mid |
| vol_imb_total | +0.593 | Full book volume imbalance |

**Regression:** Best pair R²=0.40, OOS R²=0.40 (excellent generalization, -0.02 drop)
**Confirmed useless:** trade flow, OFI, spread state, volume interactions
**The "0.9 correlation":** price LEVELS (mid[t]→mid[t+1] = r=0.993) — trivially high, not actionable

## Feynman-Kac / A-S Results

- OU calibration: kappa=0.004-0.009 (unstable), sigma=1.34 (stable both days)
- FK optimal half-spread: ~21 ticks — WAY too wide (MM quotes at ±6.5). Useless for this market.
- FK reservation shift: ±1.43 ticks at max position — similar to our existing ±1 aggression
- **Conclusion:** A-S framework doesn't help in a market with an existing MM bot

## What Works / What Doesn't (Prosperity Fundamentals)

**The Take-Clear-Make framework** (from PDF + top teams):
- Take: buy below FV, sell above FV (guaranteed profit) — WE DO THIS
- Clear: flatten at FV (zero PnL, frees capacity) — HURTS in this game (s13: 2,077 vs 3,394)
- Make: post at best±1 (speculative) — WE DO THIS
- Clear step wastes capacity that earns spread at best±1. Don't use in tutorial.

**MM-filtered mid as best FV** (from PDF): Wall Mid scored 2,614 vs microprice 2,644. Close but microprice wins.

**Adverse selection by order size**: only 1.5% toxicity in tutorial. Not worth filtering.

## Strategy Component Forensics (from run 8587 log dissection)

| Component | Mechanism (verified) | PnL Contribution |
|-----------|---------------------|-----------------|
| Best±1 posting | Queue priority over MM bot | Base fill rate (~2,518 baseline) |
| Microprice 4-lag regression | Integer FV boundary selection (33/46 buys at +5.5-6.0 edge) | ~337 over baseline |
| Trade flow (coef=1.5) | Diffuse posting shifts on 143 ticks; NOT from take decisions (zero marginal takes) | ~207 (mechanism invisible at trade level) |
| Liquidation tracking | Force-fills during narrow spread (59/88 EMERALDS fills via this path) | ~120 EMERALDS |
| Position aggression (pos>40) | Avoids wrong-side takes at high inventory | ~175 |
| Directional posting (±3 after ±4 move) | Widens continuation side; structural mean reversion | ~6 |

### PnL Decomposition (TOMATOES, run 8587)
- **Spread capture:** 925 PnL from 126 matched units at 7.34 avg spread (51%)
- **Inventory MTM:** 874 PnL from 73 units net long into rising end-of-day (49%)
- Spread capture is the bankable component; inventory MTM is variance

### EMERALDS Fill Paths (run 8587)
- 59 fills at 10,000 (liquidation path during narrow-spread windows) — avg spread 0
- 29 fills at 9,993/10,007 (±1 improvement path) — avg spread 14
- Overall avg spread: 3.55 (liquidation dominates fill count)

### Trade Flow Deep Dive
- Zero marginal takes caused or prevented (FV shifted on only 2 of 80 fills)
- 80 of 82 market_trades are our OWN fills — we intercept 98% of taker flow
- Signal is a feedback loop reading our own trading history
- Contrarian amplification: 66% of adjustments amplify position (not dampen)
- The +207 likely from diffuse posting-quality shifts across 143 ticks (~1.5 PnL each)

### Cross-Validation Result
- s25_training_only (pure cross-val, averaged coefficients): **2,855** on website
- s3_carry (35+ submission iterations): **2,857** on website
- **Gap: 2 points — strategy is NOT overfit**
- Regression coefficients [0.06, 0.12, 0.24, 0.58] are rock-stable across days (sum to ~1.0)
- Intercept varies (4.2 vs 10.6) but RMSE identical — absorbed by coefficient sum

### The Correct Framework for This Game
```
PnL = Fill Rate × Spread Captured − Inventory Risk
NOT: IC × Position Size × Volatility − Transaction Costs
```
- Fill rate is exogenous (random taker bot, ~82 fills/2k ticks)
- Signal IC does NOT affect fill rate — taker doesn't care about our quotes
- Queue priority (best±1) is the dominant PnL driver
- All signal-conditioned strategies (skewing, L2 features) score ≤2,851

## Website Scores (Complete Record — 37+ submissions)

| Strategy | Score | Key |
|----------|-------|-----|
| s3_carry | **2,857** | **BEST** — directional posting after large moves |
| s25_training_only | **2,855** | Cross-validated, NOT overfit (single submission) |
| god_mode_dp | 2,523 | DP-optimal trajectory (85 changes, spread-cost-aware) |
| god_mode (naive) | 2,248 | Naive oracle (one-sided posting, too aggressive) |
| s1_resting_optimized | **2,857** | 0 risk aversion for EMERALDS only |
| s2_tradeflow | 2,851 | microprice reg + trade flow |
| s2_speed_flat | 2,851 | same logic, 26% smaller |
| s1/s2_asymmetric | 2,851 | asymmetric sizing (no effect) |
| all L2 skew/feature additions | 2,851 | features have ZERO website effect |
| s_pipeline (7-module A-S) | 2,793 | A-S reservation HURTS |
| s2_tradeflow_tuned (coef=2.0) | 2,753 | stronger flow HURTS |
| s1_zero_risk | 2,676 | 0 risk aversion HURTS for TOMATOES |
| 6913.py | 2,644 | microprice reg only (no trade flow) |
| s1_avellaneda | 2,640 | + A-S skew alone (no effect) |
| Wall Mid approaches | ~2,600 | loses to microprice |
| diag_conversions | 2,518 | conversions DON'T WORK |
| s2_tradeflow_l2_aggressive | 2,422 | L2 as FV shift = CATASTROPHIC |
| s1_tradeflow_regime | 2,120 | spread-direction map WRONG on day 0 |
| diag_tight | 1,836 | tight posting = less edge, same fills |
| s1_probes | 1,531 | probe orders TOXIC |
| s3_tradeflow_nodrift | 1,465 | removing intercept = CATASTROPHIC |
| s18_partial_clear | 2,648 | 25% clear at pos>30 HURTS |
| s19_hybrid_fv | 2,676 | Wall Mid posting cap HURTS |
| s15_adaptive_reg | 2,495 | online learning (not enough data 2k) |
| s14_ensemble_fv | 2,640 | averaging FVs dilutes regression |
| s11_replace_microprice | 1,936 | L2-weighted microprice CATASTROPHIC |
| s6_dist_weighted | 2,640 | dist_weighted INTERFERES with flow |
| s12_no_tradeflow_distw | 2,648 | no trade flow = back to baseline |

## Critical Lessons

1. **Drift intercept 2.208667 is ESSENTIAL** — removing = -1,386 PnL
2. **Position-dependent aggression HELPS for TOMATOES** — removing = -175 PnL
3. **Trade flow coef=1.5, window=5 is OPTIMAL** — stronger/faster is worse
4. **L2 features CANNOT improve website score** — every L2 addition scores exactly 2,851 or worse
5. **Bots are NOT reactive to our spread** — confirmed identical fill counts
6. **Conversions don't work in tutorial** — confirmed 2,518
7. **Clear step HURTS** — wastes capacity (s13: 2,077 vs 3,394 baseline)
8. **FK/A-S optimal spread is useless** — 21-tick half-spread when MM quotes at 6.5
9. **All signal additions to s2_tradeflow score exactly 2,851** — hard ceiling
10. **The gap to 4,950 remains unexplained** — not from signals, features, speed, conversions, or bot reactivity
11. **Local backtester is MISLEADING** — s19 was +92 locally but -175 on website; s11 was +1,084 locally but -915 on website
12. **Partial clearing still hurts** — even 25% at pos>30 (s18: 2,648)
13. **Wall Mid posting cap hurts** — despite tracking hidden FV (s19: 2,676)
14. **Ensemble FV dilutes signal** — averaging Wall Mid + simple mid + regression loses edge (s14: 2,640)
15. **Tutorial ceiling is definitively 2,855-2,857** — confirmed NOT overfit (s25 cross-val = 2,855 vs s3 iterated = 2,857)
16. **53% of TOMATOES PnL is inventory MTM** (end position × price move) — not systematic edge
17. **Trade flow has zero marginal take impact** — +207 comes from diffuse posting shifts, not FV improvement
18. **We intercept 98% of taker flow** — market_trades is mostly our own fills (feedback loop)
19. **Taker bot is CONTRARIAN** — sells into rallies, buys into dips → gives us positive inventory PnL on average
20. **Regression's real job is integer boundary selection** — shifts FV by 1 tick at critical moments, ~15-20 correct decisions/day
21. **CSV ≠ website data** — volumes differ 98.5%, prices differ 9.3% even with zero orders. Local backtester optimizes on a different market realization

## Backtester Calibration

- Default mode: run() every tick (simulates final scoring)
- `--iterations 1000 --ticks 2000`: approximates website test (run() every 2nd tick)
- Calibrated day -1 gives 3,394 vs website 2,851 — gap from matching engine differences
- Between run() calls, resting orders persist and can be matched by bots
- Backtester uses STATIC book from CSV; website has dynamic bot interaction with our orders
- **CSV data ≠ website data** — confirmed by comparing god_logger (zero orders) vs CSV day -1:
  - Volumes differ on 98.5% of rows (different L1/L2 sizes)
  - Prices differ on 9.3% of rows (371/4000 — different bid/ask levels, sometimes different depth)
  - CSV day -2 is even more different (53% price mismatch vs website day -1)
  - These differences exist even with ZERO orders placed → not caused by our book interaction
  - Implication: local backtester trains/tests on different market data than the website evaluates on

## Strategy Architecture for Round 1+

7-module pipeline built in `trader-logic/round-0/strategy/`:
- Module 1: Bot Fingerprinting (offline, `analysis/bot_fingerprint.py`)
- Module 2: Bot Phase Tracker (real-time, `strategy/bot_phase_tracker.py`)
- Module 3: Adverse Selection (offline, `analysis/adverse_selection.py`)
- Module 4: Quote Timing Optimizer (`strategy/quote_optimizer.py`)
- Module 5: Price Path Reconstruction (`strategy/price_path.py`)
- Module 6: Position Limit Manager (`strategy/position_limits.py`)
- Module 7: Full A-S Integration (`strategy/trader.py`)

For Round 1: add new bot profiles, refit FV estimators per product, update toxicity rates.

## Round 1 Ready-to-Deploy Templates

Pre-built in `trader-logic/round-1/`:
| Template | Product Archetype | Key Technique |
|----------|-------------------|---------------|
| `template_stable.py` | Pegged product (Resin-like) | FV=10000, take at fair, post best±1, liquidation |
| `template_random_walk.py` | Volatile product (Kelp-like) | Microprice regression + trade flow + directional posting |
| `template_basket.py` | ETF basket arb | Z-score on spread (threshold=7, window=45), no component hedging |
| `template_options.py` | Options/derivatives | Black-Scholes r=0, per-strike rolling IV mean, no delta hedge |
| `template_conversion.py` | Cross-exchange arb | Implied bid/ask from observations, hidden taker bot detection |
| `template_olivia.py` | Insider bot detection | qty=15 filter at daily min/max extremes, cross-product signal |
| `refit_regression.py` | Utility | Auto-refit microprice regression: `python refit_regression.py <csv> <PRODUCT>` |

**Round 1 deployment workflow:**
1. Download sample data → `python refit_regression.py <prices.csv> KELP`
2. Identify product archetypes from names/behavior
3. Update template configs (FAIR_VALUE, COEFS, LIMIT, product names)
4. Assemble final `trader.py` from templates
5. Submit and iterate

**WARNING — CSV ≠ website data (confirmed Round 0):**
- CSV volumes differ 98.5% from website; prices differ 9.3% even with zero orders
- `refit_regression.py` fits coefficients to CSV data that the website WON'T use
- Volume-dependent features (microprice, vol_imb, gap_asymmetry) see different inputs on website
- **Round 1 strategy should prefer structural features** (spread states, mean-reversion, price levels) over volume-fitted features (L1/L2 imbalance, regression on microprice)
- Treat CSV-fitted coefficients as a starting point, not ground truth — expect to iterate on website
- Tutorial survived because s3/s25 rely on price structure, not volume specifics — new products may not be as forgiving

## File Organization (Round 0)

```
trader-logic/round-0/
├── s3_carry.py, s25_training_only.py    # BEST strategies (2,857 / 2,855)
├── s2_tradeflow.py, s2_speed_flat.py    # BASE strategies (2,851)
├── god_mode_dp.py, god_logger.py        # Oracle/troll scripts
├── best/, best_no_overfit/              # Copies + README with rankings
├── diagnostics/                         # Bot reactivity + conversion tests
├── infrastructure/                      # Feature eng, FK solver, datamodel, logger
├── early_versions/                      # 22 pre-tradeflow strategies
├── analysis/, strategy/                 # 7-module pipeline
└── experiments/{wall_mid,l2_features,execution,pde_fk,asymmetric,misc}
```

## Parameter Optimization Scripts

| Script | What it sweeps | Combos | Runtime |
|--------|---------------|--------|---------|
| `grid_search.py` | Full Cartesian of 7 params | 864 | ~43 min |
| `mega_sweep.py` | 7 independent dimension sweeps | ~488 | ~25 min |

**mega_sweep.py dimensions:**
- S0: Lag sizes [2,3,4,5,6,8] with auto-refit regression
- S1: Regression intercept + lag-4 coefficient
- S2: Trade flow (coef × window × normalization)
- S3: Position management (threshold × aggression × liq window)
- S4: Directional posting (trigger × width × decay)
- S5: EMERALDS (pos threshold × aggression × liq params)
- S6: Posting offset + EMA smoothing

**Run:** `python -u trader-logic/round-0/mega_sweep.py` (unbuffered for live output)
**Output:** `trader-logic/round-0/mega_sweep_results.json` (top 20 per sweep + landscape analysis)

## God Scripts (Troll/Oracle)

| Script | Method | Website Score |
|--------|--------|--------------|
| `god_logger.py` | Places ZERO orders, captures pristine market data | 0 (by design) |
| `god_mode.py` | Naive oracle: one-sided posting from 50-tick lookahead | 2,248 |
| `god_mode_dp.py` | DP backward induction: 322k states, spread-cost-aware | 2,523 |

**Key finding:** Website market data is 100% deterministic — clean logger data matches trading-run data perfectly (0 differences across 4,000 rows). Our orders do NOT change the book. The DP oracle scores WORSE than our legit strategy because spread crossing costs exceed directional gains in a static-book simulation. **However:** the website data does NOT match the CSV files used by the local backtester (98.5% volume mismatch, 9.3% price mismatch even with zero orders) — the CSV is a different realization of the same market.

## P3 vs P4 Data Comparison

P3 Kelp/Resin data is **completely different** from P4 TOMATOES/EMERALDS:
- Price levels: Kelp ~2,028 vs TOMATOES ~5,006
- Spreads: Kelp 2.7 vs TOMATOES 13.0 (5x wider)
- L1 volume: Kelp 21.9 vs TOMATOES 7.5 (3x smaller)
- Only AC(1) ≈ -0.45 is shared (structural game engine property)
- **Data-reuse exploit is DEAD** for P4
