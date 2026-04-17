# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Backtester

```bash
# Set PYTHONPATH if you get "No module named 'datamodel'"
$env:PYTHONPATH="c:\Users\gurms\PycharmProjects\imc-prosperity-4-backtester\prosperity4bt"

# Current best Round 1 strategy
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1

# Run specific round-day
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1--1

# Tutorial test conditions (1k ticks for Round 1, 2k for Round 0 — run() every tick like website)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --ticks 1000
python -m prosperity4bt trader-logic/round-0/trader.py 0 --ticks 2000

# Full-day competition scoring (10k ticks)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --ticks 10000

# Key flags
#   --iterations N                     run() called N times per day (resting orders between)
#   --ticks N                          max ticks to simulate
#   --match-trades {all|worse|none}    trade matching mode (default: all)
#   --match-mode {default|imc|sim|website}  ACO calibration — use 'imc' for ±1.6% match
#   --no-out                           skip saving .log file
#   --no-progress                      hide progress bars
#   --print                            show trader stdout
```

Output logs go to `backtests/<timestamp>.log`. Round sizes: Round 0 tutorial = 2k ticks, Round 1 tutorial = 1k ticks, full days = 10k ticks.

## Game Engine Tick Sequence (from chrispyroberts/imc-prosperity-4 Rust source)

Per tick, the IMC engine executes in THIS order:
1. **Fresh books generated** — MM bot posts new quotes (not carried from previous tick)
2. **Strategy called** — `run(state)` receives current book, returns orders
3. **Strategy aggressive takes execute** — orders that cross the book fill immediately
4. **Unfilled orders become passive levels** — inserted into the live book with `LevelOwner::Strategy`
5. **Taker arrives** — market order hits ALL levels by price priority (bot AND strategy)
6. **Tick ends** — passive orders DISCARDED, not carried to next tick

**Position limits: ALL-OR-NOTHING.** If buy_qty + position > 80, the ENTIRE product's orders are rejected.

**Taker fills our passive orders** in Step 5 if our price is the best. This is the mechanism for the 59 "invisible taker" fills in ACO — our best±1 posting creates the effective best, and takers hit it.

## Simulation Mechanics (Confirmed by IMC + website log analysis)

- Full trading day = **10,000 rows** per product (timestamps 0-999,900, step 100ms)
- **Tutorial test submission**: run() called on **EVERY tick** (confirmed: 2000 log entries for 2000 ticks in website logs). **NOT** 1000 iterations — the wiki's "1,000 iterations" refers to full-day (10k tick) submissions, not the tutorial's 2k-tick test.
- **Final scoring**: run() called **10,000 times** (every tick)
- Orders that don't fill immediately become **resting quotes** hit by bots between run() calls (only matters when iterations < ticks)
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
**Position limits:** All products 80 (`prosperity4bt/constants.py`): EMERALDS, TOMATOES, ASH_COATED_OSMIUM, INTARIAN_PEPPER_ROOT.
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
| `trader-logic/auction_solver.py` | Manual challenge clearing auction optimizer |
| `trader-logic/auction_writeup.md` | Round 1 manual challenge solution + derivation |
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
| s36_medallion | **2,896** | **BEST** — s3 base + OBI shift + EM pos aggression |
| s3_carry | **2,857** | directional posting after large moves |
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
11. **Local backtester was MISLEADING (pre-fix)** — s19 was +92 locally but -175 on website; s11 was +1,084 locally but -915 on website. After bug fixes (2026-03-21), backtester matches within 1% for book-only strategies and ~6-9% for taker-dependent strategies
12. **Partial clearing still hurts** — even 25% at pos>30 (s18: 2,648)
13. **Wall Mid posting cap hurts** — despite tracking hidden FV (s19: 2,676)
14. **Ensemble FV dilutes signal** — averaging Wall Mid + simple mid + regression loses edge (s14: 2,640)
15. **Tutorial ceiling raised to 2,896** by s36_medallion (s3 base + OBI shift 0.5 + EM pos aggression). Previous ceiling was 2,855-2,857
16. **53% of TOMATOES PnL is inventory MTM** (end position × price move) — not systematic edge
17. **Trade flow has zero marginal take impact** — +207 comes from diffuse posting shifts, not FV improvement
18. **We intercept 98% of taker flow** — market_trades is mostly our own fills (feedback loop)
19. **Taker bot is CONTRARIAN** — sells into rallies, buys into dips → gives us positive inventory PnL on average
20. **Regression's real job is integer boundary selection** — shifts FV by 1 tick at critical moments, ~15-20 correct decisions/day
21. **Day 0 CSV = website data** (100% match confirmed). **Days -1/-2 CSV ≠ website data** — volumes differ 98.5%, prices differ 9.3% even with zero orders. Use day 0 for calibration, days -1/-2 for relative comparison only
22. **Website calls run() on EVERY tick in tutorial** — NOT 1000 iterations. The `--iterations 1000` flag was wrong and caused 50% of ticks to use resting orders instead of fresh trader logic. Omit `--iterations` or set equal to `--ticks`
23. **Backtester own_trades persisted across ticks (fixed)** — strategies reading own_trades (e.g., PnL trackers) would double/triple-count fills. Clear own_trades/market_trades each tick

## Backtester Calibration

### Bugs Fixed (2026-03-21)
1. **own_trades/market_trades stale persistence** — Neither dict was cleared between ticks in `__initialize_trade_state()`. Stale trades from tick N persisted into tick N+1 if no new trades occurred. Fixed: clear both at the start of each tick.
2. **Resting order quantities not updated after partial fills** — `__deep_copy_orders()` snapshot happened before matching. After a fill, resting orders kept the ORIGINAL quantity, causing position limit violations and order rejection on subsequent ticks. Fixed: re-snapshot `resting_orders` after every matching pass.
3. **Wrong iteration count for tutorial** — `--iterations 1000` was wrong. Website log analysis (run 8587) shows 2000 log entries for 2000 ticks = run() called on EVERY tick. No resting orders in tutorial test submissions.

### Calibration Results (day 0, run() every tick, default mode)
| Strategy | Website | Backtester | Gap | Notes |
|----------|---------|------------|-----|-------|
| s3_carry | 2,857 | 2,626 | -8.1% | Inside-spread MM, intercepts takers |
| s25_training_only | 2,855 | 2,684 | -6.0% | Inside-spread MM, no trade flow |
| s2_tradeflow | 2,851 | 2,594 | -9.0% | Inside-spread MM + trade flow feedback cascade |
| s28_inside_mm | 2,701 | 2,650 | -1.9% | Inside-spread MM, different FV |
| s1_wallmid | 2,600 | 2,616 | +0.6% | At-spread MM |
| s15_adaptive_reg | 2,495 | 2,467 | -1.1% | At-spread MM |

**EMERALDS gap = 0 across all 7 tested runs.** The entire gap is TOMATOES.

### How to Use the Backtester (the Ren approach)
- **Use it for RANKING, not absolute PnL prediction.** Relative ordering is perfectly preserved across all strategies.
- **For inside-spread MM strategies**: apply mental correction `website ≈ BT × 1.07`. The ~7% undershoot is structural and constant.
- **For at-spread strategies**: BT matches within ±2%, no correction needed.
- **Never patch the backtester to match known scores.** That's overfitting the infrastructure.

### The Structural Gap: Root Cause (fully diagnosed)
- CSV records a market WITHOUT our orders. ~12 TOMATOES taker arrivals that only trade on the website (because our best±1 order provides a better price than the MM bot) don't appear in CSV
- Website has 170 fills for s25: 100 from CSV trade timestamps + 58 EMERALDS narrow-spread takes + 12 TOMATOES taker fills not in CSV
- **s2_tradeflow's larger gap (-9% vs s25's -6%)**: trade flow signal reads `market_trades` (includes own fills). Fewer BT fills → different flow → different FV → missed takes → cascade amplification
- The gap is **irreducible with CSV-replay**. Would require per-tick agent-based simulation (SIM mode) which introduces its own calibration problems
- CSV day 0 order books match website 100% (0 diffs across 4000 rows) — book data is perfect

### CSV vs Website Data
- **Day 0 CSV = website order books** (100% match confirmed, run 8587)
- **Days -1/-2 CSV ≠ website** — volumes differ 98.5%, prices differ 9.3% (different market realization)
- Use day 0 for calibration, days -1/-2 for relative comparison only

## s36_medallion Architecture (Current Best: Website 2,896)

**Base:** s3_carry (lag-4 microprice regression + trade flow + directional carry signal)
**Additions (each website-validated or structurally motivated):**
- OBI FV shift (+0.5 tick): L1+L2 volume imbalance nudges FV (website: +39 PnL)
- EMERALDS pos aggression at ±40: tighter takes when inventoried (from s30)
- Terminal flattening (t>900k, |pos|>10): locks in spread PnL on full days (+944 BT total)

**Overfit assessment:** Day 0 = 0% overfit (identical to s3). Full-day improvements = moderate risk (thresholds swept on 2 CSV days). Terminal flattening is structurally correct (OU process → carry is variance).

## Exhaustive Data Mining Results (28 hypotheses, all 3 days)

**LIVE signals (stable across all days):**
| Signal | Accuracy | Frequency | Used in s36? |
|--------|----------|-----------|-------------|
| L1+L2 OBI | 97-99% | 7% of ticks | YES (FV shift) |
| L1 vol ratio > 2.0 | 91-94% | 2% of ticks | Subset of OBI |
| Spread=5 next UP | 100% | 0.5-1% | NO (hurts when layered) |
| Spread=9 next DOWN | 94-100% | 0.5-1% | NO (hurts when layered) |
| Vol clustering |dmid| AC=+0.44 | 50x OBI PnL after big moves | 7% | NO (widening hurts fills) |

**DEAD signals (confirmed across all days):** cross-product (zero), spread memory, taker prediction (random), round numbers, FFT cycles, inventory-adjusted FV, taker impact, volume recovery, L2 gap asymmetry (anti-signal), EMERALDS narrow prediction, trade qty direction.

**De-anonymized bots:**
- Taker: exponential inter-arrival, 50/50 iid side, qty uniform [2,5], zero intelligence
- MM: mid in 0.5 increments, L2/L1 vol ratio = 2.78x constant, spread {5-9,13,14}

**Key negative results:**
- Spread-crossing is NEVER +EV (-6.5 to -7.5 per trade at every threshold)
- VWAP take FV: better RMSE (1.025 vs 1.140) but HURTS backtester PnL (CSV vol ≠ website vol)
- Reduce-only aggressive takes: +86 day 0 pre-fix, but -1305 total post-fix
- Position capping < 80: strictly worse at every level
- EMERALDS spread capture is NEGATIVE (all EM PnL from inventory carry)

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

## File Organization

```
trader-logic/
├── auction_solver.py                    # Manual challenge clearing auction optimizer (reusable)
├── auction_writeup.md                   # Round 1 manual challenge solution
├── Prosperity_Fundamentals.pdf          # Take-Clear-Make framework guide
├── round-0/                             # Tutorial round strategies
├── round-1/                             # Round 1 templates (7 files)
```

### Round 0 Detail

```
trader-logic/round-0/
├── s36_medallion.py                     # CURRENT BEST (website 2,896)
├── s3_carry.py                          # Previous best (website 2,857)
├── s25_training_only.py                 # Cross-validated baseline (2,855)
├── s28_inside_mm.py                     # Inside-spread MM variant (2,701)
├── s34_grid.py                          # Grid posting + terminal flatten
├── s35_ar2_trailing.py                  # AR(2) + trailing stop experiment
├── best/, best_no_overfit/              # Copies + README with rankings
├── diagnostics/                         # Bot reactivity + conversion tests
├── oracle/                              # God mode scripts + IMC extracted source
├── sweeps/                              # Parameter sweep variants (s26-s33)
├── experiments/                         # Overfit tests, DP experiments, s35 variants
├── early_versions/                      # 22 pre-tradeflow strategies
├── infrastructure/                      # Feature eng, FK solver, datamodel, logger
├── analysis/, strategy/                 # 7-module bot exploitation pipeline
└── sim_tmp/                             # Auto-generated sim sweep temp files
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

## Round 1 Manual Challenge: "An Intarian Welcome"

One-shot uniform-price clearing auction. Stale order books for two products, one limit order each, buyback at fixed price after auction.

**Clearing rule:** price that maximizes `min(cum_bids >= P, cum_asks <= P)`, tie-break highest price. Price-time priority allocation (we submit last = last in time at our price level).

**Key exploit:** bid ABOVE target clearing price for price priority, cap volume just below the threshold that tips clearing upward. This lets us fill at lower clearing price while jumping the queue.

| Product | Order | Clearing | Fills | Edge | Profit |
|---------|-------|:--------:|------:|-----:|-------:|
| Dryland Flax (buyback=30, no fee) | BUY @ 30, vol 9,999 | 29 | 9,999 | 1.00 | 9,999 |
| Ember Mushroom (buyback=20, fee=0.10) | BUY @ 17, vol 19,999 | 16 | 19,999 | 3.90 | 77,996 |
| **Total** | | | | | **87,995** |

Cliff edges: Flax vol 10,000 -> clearing 30 -> profit 0. Mushroom vol 20,000 -> clearing 17 -> profit 58,000.

**Solver:** `trader-logic/auction_solver.py` (exhaustive 2D price*volume sweep, step=1 at boundaries)
**Writeup:** `trader-logic/auction_writeup.md`

## P3 vs P4 Data Comparison

P3 Kelp/Resin data is **completely different** from P4 TOMATOES/EMERALDS:
- Price levels: Kelp ~2,028 vs TOMATOES ~5,006
- Spreads: Kelp 2.7 vs TOMATOES 13.0 (5x wider)
- L1 volume: Kelp 21.9 vs TOMATOES 7.5 (3x smaller)
- Only AC(1) ≈ -0.45 is shared (structural game engine property)
- **Data-reuse exploit is DEAD** for P4

---

## Round 1: "Trading Groundwork"

### Round 1 Products

| Product | Limit | Price | Range/day | Spread | L1 vol | AC(1) | Archetype |
|---------|-------|-------|-----------|--------|--------|-------|-----------|
| INTARIAN_PEPPER_ROOT | 80 | ~12,000 | 1,000 | 12-14 | 11.5 | -0.50 | TOMATOES (random walk) |
| ASH_COATED_OSMIUM | 80 | ~10,000 | 27-36 | 16 (62%) | 14.0 | -0.49 | EMERALDS (stable FV) |

**IPR** has +1000/day uptrend across CSV days (-2: ~10k, -1: ~11k, 0: ~12k). "Steady value" per spec.
**ACO** has "hidden pattern" per spec = O-U mean-reversion to FV ~10000. Mid deviates ±18 max.
**Both products** have ~9% one-sided book ticks (no bid or no ask). Strategy must handle gracefully.

### Round 1 Key Differences from Round 0

| Metric | Round 0 (Tutorial) | Round 1 |
|--------|-------------------|---------|
| Website tutorial ticks | 2,000 per product | **1,000 per product** |
| CSV ≠ website match | Day 0 = 100% match | **Day 0 = 36% match** |
| Taker arrival rate | ~70/2000 ticks (3.5%) | **~300/1000 ticks (30%)** |
| Taker CoV | 0.99 (Poisson) | **0.76-0.81 (more regular)** |
| One-sided book ticks | 0% | **~9%** |
| PnL from taker fills | ~70% | **~70%** |

### Round 1 Bot Behavior (Website-Confirmed)

**MM Bot**: 100% non-reactive to our orders (confirmed: god logger vs trading run = 0 differences across 2000 rows). Same engine as Round 0.

**Taker Bot** (from clean book forensics, 1000 ticks):
- IPR: ~300 arrivals/1000 ticks, qty [3-8], side 50/50
- ACO: ~308 arrivals/1000 ticks, qty [2-10], side 50/50
- Arrival pattern NOT Poisson (CoV 0.76-0.81 vs 1.0 expected)
- Asymmetric L1 volumes on ~33% of ticks (mix of taker + MM's own asymmetry)
- 70% of PnL comes from taker fills, only 30% from order-depth takes

### Round 1 Regression (Cross-Validated 3 Days)

**INTARIAN_PEPPER_ROOT** (4-lag microprice regression):
```python
COEFS = [0.2474, 0.2529, 0.2412, 0.2585]  # Nearly uniform (~0.25 each)
INTERCEPT = 0.2078                           # Near zero
# Coef sum = 1.0 → FV ≈ average of last 4 microprice values
# RMSE = 1.23-1.46 (stable across days)
```

**ASH_COATED_OSMIUM** (regression also works but less needed):
```python
COEFS = [0.214, 0.215, 0.250, 0.294]
INTERCEPT = 215-387 (varies by day — absorbed by FV ~10000)
# Coef sum = 0.96-0.98 (not quite 1.0 → slight mean-reversion)
```

### Round 1 Website Scores (25+ submissions, updated 2026-04-17)

| Strategy | Submission | Score | IPR | ACO | Key |
|----------|------------|------:|----:|----:|-----|
| Nancy's algov4 (benchmark) | 228959 | **10,734.03** | 7,496 | 3,238 | Teammate reference — +109 over our best |
| **r1_v4** | 213352 | **10,624.84** | **7,446** | **3,179** | **OUR CURRENT BEST** — r1_v2 IPR + LU ACO |
| r1_v5 (guardrail) | 228366 | 10,612.84 | 7,434 | 3,179 | Nancy-inspired trend detector — neutral −12 |
| r1_v9_defensive | 251714 | 10,601.66 | 7,438 | 3,164 | Cubic ACO skew + circuit breaker + correctness fixes (Banker's, tie-breakers). Insurance −23 vs v4. |
| r1_v10_defensive | 252728 | 10,455.66 | 7,292 | 3,164 | v9 + toxic-maker fix (anchors to avg_mid in crash) + blind-bull startup fix. ACO identical to v9 on real (dormant). IPR cost −146 from neutral startup. |
| r1_v11_defensive | 253476 | **10,455.66** | **7,292** | **3,164** | v10 + cur_mid crash trigger + IPR one-sided drop. **Byte-identical to v10 on website** — both fixes dormant (no crash, one-sided ticks had no taker flow). Zero-cost structural insurance. |
| r1_v12_defensive | 257139 | **10,443.78** | 7,292 | 3,152 | v11 + blind-eye reset fix + sweep-optimal params (MAX_CONCESSION 8→4, CRASH_THRESHOLD 25→15). Synthetic +14,940 over v10; **website −12 (regressed, crash regimes never materialized)**. BT-gradient-vs-website overshoot confirmed once more. |
| r1_v13_defensive | 258586 | 10,443.78 | 7,292 | 3,152 | v12 + forced-dump (spread-cross when crash_mode + \|pos\|>60). **Byte-identical to v12 on website** (no crash + pos>60 state). **Synthetic −21,715 vs v12** from ping-pong: dumps flip pos +60→−15, make re-accumulates, cycle repeats. |
| r1_v14_defensive | not submitted | — | — | — | v12 + asymmetric quoting ("lean out"): when crash_mode + \|pos\|≥60, set accumulation-side cap to 0 (skip that quote). **Synthetic −4,736 vs v12** but +21,979 vs v13 — clean architecture that avoids v13's cycle-loss. In synthetic mean-reverting crashes, v12's passive bid at widened edges captures edge on toxic fills; v14 forfeits that. **Architecturally correct for true one-way crashes; empirically costly for our synthetic regimes.** |
| r1_v2 | 211338 | 10,536.81 | 7,446 | 3,091 | Simple mid + drift_bias=5 (via 210525 probe) |
| r1_medallion bias=6 | 134926 | 10,467.8 | 7,377 | 3,091 | Previous best, microprice regression |
| r1_v7 (guardrail + wall-mid) | 228024 | 10,465.84 | 7,287 | 3,179 | REGRESSION −159, delayed entry trap |
| r1_medallion bias=5 | baseline | 10,444.8 | 7,354 | 3,091 | Drift bias=5, proven stable |
| TROLL ACO | — | 10,435.4 | 7,354 | 3,081 | Their take/clear/make attempt |
| ACO swept params | — | 10,312.6 | 7,354 | 2,959 | BT gradient WRONG for ACO |
| r1_hybrid (×3) | 207789/208196/210055 | **10,106-10,107** | 7,016-7,446 | 3,091-3,179 | Seed-detection — byte-identical, NO improvement |
| probe1 no-take ACO | — | 9,986.9 | 7,354 | 2,633 | ACO takes worth 458 |
| r1_v3 | 212392 | **7,974.84** | **4,796** | 3,179 | **LU framework on IPR = REGRESSION** |
| r1_medallion v1 (no drift) | — | 5,229.0 | 2,138 | 3,091 | Pre-drift baseline |
| trader (basic) | 105087 | 4,933.8 | 2,138 | 2,796 | Original basic trader |

**Key findings (2026-04-17 update):**
- **Simple mid beats microprice for IPR** (v2 discovery via 210525 probe)
- **LU clear step = +88 for ACO** (theory: +3% × 3,091 = +87, actual: +88)
- **LU framework BREAKS drift products** (v3 regressed −2,650 IPR)
- **Drawdowns are entry-cost, not bugs** (r1_hybrid, r1_v7 both regress)
- **Nancy's rolling-slope + direction-history guardrail is structurally sound** — our r1_v5 adopts the mechanism with conservative asymmetric thresholds (0.55/0.35 vs her symmetric 0.5)
- **r1_v5 multi-seed synthetic validation**: beats r1_v4 on 16/16 seed×regime combos (+15k uptrend, +20k flat, +28k downtrend, +23k reversal)
- **r1_v5 website cost is noise** (−12 vs v4, buys real downtrend insurance)
- **Nancy's OU ACO model is NOT adopted** — 9 tuned params, her +59 ACO edge likely seed variance
- **r1_v8 (Nancy bid placement port) failed to port** — self-wash bug, BT regression persists after fix
- **Practical website ceiling ~10,625-10,734**. TROLL at 10.6k, us at 10.625, Nancy at 10.734
- Submission framework: r1_v4 for max-PnL uptrend, r1_v5 for regime insurance

### Round 1 Backtester Cross-Validation (4 Backtesters)

All tested on same CSV data, day 0, 1k ticks:

| Backtester | Basic | Medallion | Delta | Notes |
|---|---|---|---|---|
| **Website** | **4,934** | **5,229** | **+295** | Ground truth |
| Ours | 6,528 | 6,640 | +112 | Conservative matching |
| Kevin-fu1 | 7,702 | 7,814 | +112 | More generous matching (default=worse) |
| Xeeshan/prosperity4btx | 7,702 | 7,814 | +112 | Same as Kevin at 1k |
| Rust (GeyzsoN) | 6,528 | 6,640 | +112 | **Matches ours exactly** |

**Key findings:**
1. All 4 backtesters agree: medallion > basic (+112 at 1k ticks, +295 on website)
2. Our backtester = Rust backtester (identical scores — independent validation)
3. Kevin/Xeeshan give ~18% higher scores (more generous market trade matching)
4. All overpredict vs website by 30-56% (CSV ≠ website data, 36% book match)
5. Backtesters are for **structural ranking only**, not absolute PnL prediction

### Round 1 CSV vs Website Data

- **Day 0 CSV ≠ website** — only 36% L1 price match (vs Round 0's 100%)
- **God logger website data** extracted to `prices_round_1_day_0_website.csv` (1000 ticks)
- Order-depth-only PnL on website data: 1,471 (30% of total 4,934)
- Taker fill PnL: ~3,463 (70% of total) — cannot simulate accurately from CSV
- Website data preserved as `*_website.csv` files in `prosperity4bt/resources/round1/`

### Round 1 Strategy Architecture

**r1_v4.py** (Current Best: Website **10,624.84**):

**INTARIAN_PEPPER_ROOT** (drift capture, website **7,446**) — from r1_v2:
- **Simple mid FV + drift_bias=5** (NOT microprice regression)
  - `fv = round(mid + 5.0)` where `mid = (best_bid + best_ask) / 2`
  - Microprice would lean LOW in ask-heavy book, missing initial take
- Asymmetric takes: buy if price ≤ fv+2, sell only if price ≥ fv+3
- Post aggressive bid at `min(fv-1, best_bid+1, best_ask-1)`, defensive ask at `max(fv+2, best_ask-1, best_bid+1)`
- One-sided book handling (9% of ticks)
- 4 tunable params (LIMIT, DRIFT_BIAS, BUY_SLACK, SELL_SLACK)

**ASH_COATED_OSMIUM** (Linear Utility AMETHYSTS port, website **3,179**):
- Fixed FV = 10000
- **Take → Clear → Make pipeline** (LU canonical):
  - Take: buy if ≤ fv-1 (TAKE_WIDTH=1), sell if ≥ fv+1, with adverse_vol<15 filter
  - Clear: flatten at fv exactly (CLEAR_WIDTH=0) — Linear Utility's +3% trick
  - Make: penny/join/default posting (DISREGARD=1, JOIN=2, DEFAULT=4)
- Soft-limit skew: shift 1 tick toward neutral at |pos|>40
- All params are LU-exact (P2 #2 finish values) — zero backtest tuning
- +88 validated over baseline ACO (matches theoretical +3%)

**Overall:** 10 params total, all derived from market structure or copied from validated P2 winner code.

### Round 1 Critical Lessons (22+ submissions, as of 2026-04-17)

1. **Simple mid > microprice for drift products** — r1_v2 discovery via 210525 probe. Microprice volume-weights toward heavier side; in ask-heavy books (bullish) it leans LOW, missing the t=0 ask-take at 12006. Simple mid catches it. +90 PnL.
2. **Linear Utility clear step = +3% on stable products** — validated on ACO (+88, theory predicted +87). Apply LU framework to AMETHYSTS/ACO-like products; DO NOT apply to drift products.
3. **LU take_width=1 BREAKS drift products** — r1_v3 regressed IPR by -2,650. LU assumes FV is present-value accurate; drift needs future-value FV.
4. **Drawdowns are entry-cost, not bugs** — r1_hybrid (passive bids, 0 drawdown) scored -429 vs r1_medallion. Eliminating drawdown = entering later = paying more. Drawdown IS the drift trade entry.
5. **Seed detection works but doesn't help** — 3 hybrid submissions correctly detected seed match; but hardcoded bids at 11995 never filled (no taker sells at that price during drawdown).
6. **Drift bias = 35% of total PnL** — FV += 5 is the core IPR alpha.
7. **Trade flow, OBI, carry = 0% marginal PnL each** — ablation-confirmed. Dropped from r1_v2 onwards.
8. **ACO fills are STRATEGY-INDEPENDENT** — 59 of 101 fills are "invisible takers" attracted by any inside-spread posting.
9. **ACO posting width has ZERO effect** — FV±3 = best±1 (byte-identical fills).
10. **Conversions are DISABLED for Round 1** — probes: conversions=+1 and -1 both identical to 0.
11. **No hidden observations** — state.observations.plainValueObservations={}, conversionObservations=EMPTY.
12. **Backtester calibration: imc mode with extra_rate=0.064** matches website within 1.6% for ACO. Use `--match-mode imc`.
13. **CSV ≠ website (36% match)** — backtester is for ranking only. IPR backtester is INVERSE-indicator for framework changes (r1_v3 looked best on backtester, worst on website).
14. **Practical ceiling ~10,625**. TROLL (competitor) also stuck at ~10,600 with 14+ params. Different approaches converged.
15. **Gap to #1 (11,744) likely seed variance** — exhaustive probing found no unexploited alpha.
16. **traderData format matters** — removing unused state variables caused 2 fewer IPR fills (-39 PnL). Keep all fields.
17. **ACO BT gradient overshoots ~60×** — quantified by r1_v9_defensive (251714): cubic skew predicted −924 ACO BT on day 1, actual website cost was −15. Treat any ACO BT delta < 1,000 as noise; trust only large structural changes.
18. **Cubic inventory skew + circuit breaker = essentially free insurance** — r1_v9_defensive cost only −23 vs r1_v4 on website but wins 16/16 synthetic regime stress tests with +10k mean PnL. Use as base when tail-risk weighting > 0.2%.
19. **Banker's rounding bug latent in v7** — Python's `round()` is round-half-to-even; with `(int+int)/2.0` midpoints landing on .5 ~50% of ticks, this introduced arbitrary 1-tick bias. Fix via `int(math.floor(x + 0.5))` recovered ~+150 IPR PnL in v9 vs v7 (7,438 vs 7,287).
20. **v9 had a "toxic maker" circuit-breaker bug** — when crash_mode disabled take/clear, the maker still anchored to fv_eff≈10000. In a market crash to 9,940, every market bid is below 10000, so the bot posted passive buys at `max(bid)+1` and got crossed by toxic sellers. v10 fix: in crash_mode, anchor `base_fv` to `avg_mid` and widen edges by +8/+4 ticks. ACO crash test (synthetic, ACO 10000→9940→10000 over ticks 4000-7000): **v10 saves +41,339 ACO PnL vs v9**.
21. **Blind-bull startup latent in v5/v7/v9** — `if n < MIN_HISTORY: return IPR_DRIFT_BIAS` defaulted to +5 (bullish prior) before any trend data. v10 fix: return 0.0 (neutral). Cost: ~100-150 IPR PnL/day on uptrends. Worth it for regime-uncertain days; r1_v4/v5/v9 still appropriate when uptrend is the strong prior. **Quantified on website:** v10 (252728) scored 7,292 IPR = −146 vs v9's 7,438.
22. **v10 had circuit-breaker lag latent in the 5-tick avg_mid trigger** — detection took 2-3 ticks after an instant 50-tick mid drop. During those 2-3 ticks the bot executed normal taker logic and bought aggressively into the crash. Accidentally profitable in mean-reverting synthetic tests (ACO_CRASH v10 > v11 by 991; ACO_FLASH v11 > v10 by only 205), but catastrophic in a persistent regime change. v11 fix: trigger on `cur_mid` (instant), keep `avg_mid` as anchor for stable quoting in stress.
23. **IPR one-sided penny-improve = adverse selection** — when ask side disappears, posting buy at `best_bid+1` puts you at the top of the crowded bid stack right when toxic sellers return. v11 fix: in one-sided books, provide liquidity ONLY on the disappeared side at premium edge; skip the penny-improve on the crowded side. Rare regime (~9% of ticks), but free defense.
24. **v10 and v11 byte-identical on Round 1 day-1 website** — submissions 252728 (v10) and 253476 (v11) produced exact same total/IPR/ACO/positions/traderData. Confirms: (a) circuit breaker never triggered in Round 1 (no ACO crash); (b) one-sided IPR ticks had no taker flow in this market, so removing penny-improve changed zero fills. Insurance is structurally correct but dormant until a regime event.
25. **PERMANENT regime (day 6, added 2026-04-17) reveals toxic-maker fix's true value** — 25-seed synthetic: mean-reverting ACO_CRASH hides most of the v10-vs-v9 benefit (shows +40k because lag-induced buys become profitable on revert), ACO_FLASH shows +15k. **PERMANENT (drop + no recovery) shows +97,135 PnL v10 over v9** — the persistent-regime-change scenario where lag-induced buys stay toxic. Use PERMANENT regime to quantify circuit-breaker value; use mean-reverting regimes to calibrate false-positive cost.
26. **v10 beats v11 on synthetic totals (1,543,869 vs 1,543,559 across 7 regimes, 25 seeds)** — v11's cur_mid trigger reacts faster but flickers in/out of crash_mode on gradual crashes (ACO_CRASH: v11 −1,017 ± 49 SE vs v10). v11 wins on sharp transitions (ACO_FLASH +400, PERMANENT +307) but loses more on gradual (−1,017). Net: v10 is empirically better on our regime mix. The trigger-lag fix is structurally correct (prevents 2-3 tick lag on instant crashes) but empirically costs on noisy threshold crossings. Add hysteresis (enter at 25, exit at 20) to get best of both worlds, or keep v10 as operational default.
27. **ACO param sweep (9 combos × 4 regimes × 25 seeds) inverted the user's intuition about the skew-vs-edge collision**. Hypothesis was that MAX_CONCESSION (8) < widened edge (12) leaves inventory trapped at +80 during crashes, so scale concession up to 16. Sweep data showed the opposite: (4, 15) beats (8, 25) by +9,280, (12, 35) worst at −18,844. Rankings:
    - (4, 15): 892,746 mean ← v12 adopts
    - (8, 15): 890,239
    - (4, 25): 886,650
    - (8, 25): 883,766 ← v11 default
    - (12, 35): 864,922
    The "trapped at +80" scenario is mathematically real but empirically dominated: widening concession pulls FV further from market during the gradient, hurting UPTREND by ~6k while gaining essentially nothing on PERMANENT. The correct lever for forced dumping is aggressive spread-crossing, not larger skew.
28. **v12 (sweep-optimal + blind-eye reset fix) wins 7/7 regimes over v10 at 25-seed significance** — +14,940 total, per-regime gains: UPTREND +2,073, FLAT +2,169, DOWNTREND +2,001, REVERSAL +2,100, ACO_CRASH +4,582, ACO_FLASH +1,664, PERMANENT +352. Lower MAX_CONCESSION=4 reduces FV distortion at moderate inventory (helps baseline regimes); lower CRASH_THRESHOLD=15 catches gradient crashes earlier (helps ACO_CRASH). Ship v12 as the new defensive default pending website validation.
29. **Blind-eye reset bug in v10/v11** — `else: cur_mid = avg_mid = ACO_FV` triggered when book lost a side, which reset the crash detection math to |10000-10000|=0 and silently disarmed `crash_mode` at the exact moment market structure broke. v12 fix: fall back to last known `aco_mids` average, only use ACO_FV at tick 0 boot. Unobserved in synthetic (book never breaks during crashes) but real scenario (flash crash → bids evaporate → v10/v11 disarm).
30. **Aggressive spread-cross forced-dump is counterproductive in crashes** — v13 added `if crash_mode and |pos|>60: ask = market_best_bid`. Synthetic CRASH_DEEP regime (ACO drops 150 ticks, never recovers): v13 scored −6,753 vs v12 (target regime!). Mechanism: forced-dump flips pos from +60 to −15, standard make logic re-accumulates from toxic sell flow, cycle repeats, each cycle locks in realized loss. In synthetic (where end-of-day MTM is realized anyway), cycle loss > held loss. Correct approach would be **STOP posting on the accumulation side** (no bid when crash_mode + long), not force-dump. The "trap at +80" scenario's empirical cost in synthetic = 0 (v12 passive quoting nets the same PnL at end of day); the problem is actually repeated toxic-buy cycles, which dump-acceleration makes worse.
31. **Full defensive ranking (25 seeds × 8 regimes synthetic)**: v12 (1,784,466) > v14 (1,779,730) > v10 (1,768,987) > v13 (1,762,751). Per-regime: v12 wins 7/8 vs v10 with *** significance; v13 loses 4/8 vs v12 by cycle-loss; v14 loses 4/8 vs v12 by forfeited edge-capture. Real-data ranking of neutral-startup variants: v10/v11 (10,455.66) > v12 = v13 (10,443.78). v9 (10,601.66) is a separate lineage that kept the +5 blind-bull startup. v12's −12 real regression is the cost of false-positive crash_mode triggers (CRASH_THRESHOLD=15 < actual ACO normal range of ±18).
32. **v14 "lean out" architecture is theoretically correct but empirically dominated** — when crash_mode + \|pos\|>=60, zero out `buy_cap` (long) or `sell_cap` (short) to break the accumulation cycle cleanly. This is the textbook fix for v13's inventory ping-pong (where forced dumps flip pos, make logic re-accumulates, cycle repeats). v14 is −4,736 vs v12 on synthetic but +21,979 vs v13. **The trade-off in synthetic:** v12's passive bid at widened edges during a crash is actually *edge-capturing* (toxic sells fill below mid, units carry positive MTM on eventual reversion/stabilization). v14 forfeits that edge capture for units 61-80 in exchange for bounded inventory. **Choose v14 if the threat model expects one-way crashes harder than CRASH_DEEP; choose v12 if synthetic-likeness of future regimes is the prior.**

### Round 1 File Organization

```
trader-logic/round-1/
├── r1_v4.py                             # CURRENT BEST (website 10,624.84)
├── r1_v9_defensive.py                   # Cubic ACO skew + circuit breaker (website 10,601.66)
├── r1_v10_defensive.py                  # v9 + crash_mode anchor-to-avg_mid + neutral startup drift (website 10,455.66)
├── r1_v11_defensive.py                  # v10 + cur_mid crash trigger (reactive) + one-sided penny-improve drop (website 10,455.66 — byte-identical to v10)
├── r1_v12_defensive.py                  # v11 + blind-eye reset fix + sweep-optimal (MAX_CONCESSION=4, CRASH_THRESHOLD=15). Synthetic 25-seed: +14,940 vs v10; website 10,443.78
├── r1_v13_defensive.py                  # v12 + forced-dump (spread-cross). ABANDONED: synthetic −21,715 vs v12 from cycle-loss; website 10,443.78 (byte-identical to v12)
├── r1_v14_defensive.py                  # v12 + "lean out" (skip accumulation side when crash_mode + |pos|>=60). Synthetic −4,736 vs v12 but +21,979 vs v13. Structurally correct for one-way crashes.
├── refit_regression.py                  # Utility: auto-refit microprice regression
├── BACKTEST_COMMANDS.md                 # Canonical backtest command reference
├── README.md                            # Strategy evolution table + directory map
├── best/                                # Archival best + rationale
│   ├── r1_v4.py
│   └── README.md
├── experiments/                         # Failed/abandoned experiments (lessons)
│   ├── r1_v3.py                         # LU framework on IPR (website 7,974)
│   ├── r1_hybrid.py                     # Seed-detection (3 × 10,106)
│   ├── r1_adaptive.py                   # Drift-adaptive variant
│   ├── r1_medallion_dp.py               # DP experiment
│   ├── synthetic/                       # Regime stress-test framework
│   │   ├── generate.py                  # CSV generator (4 regimes)
│   │   └── run_all.py                   # Multi-seed comparator
│   └── README.md
├── early_versions/                      # Superseded baselines (useful for ablations)
│   ├── trader.py, r1_medallion.py, r1_v2.py
│   └── README.md
├── templates/                           # Per-archetype starters (Round 2+ scaffolding)
│   └── template_{stable,random_walk,basket,options,conversion,olivia}.py
├── references/                          # Competitor / teammate code for study
│   ├── nancy_algov4.py                  # Nancy's 10,734 submission (guardrail source)
│   ├── superduperbread_round1_26.py     # Teammate's 10,400
│   ├── r1_troll.py                      # Competitor TROLL's ~10.6k
│   └── README.md
├── r1_v5.py                             # Guardrail variant (website 10,612.84)
├── r1_v6.py, r1_v6b.py, r1_v7.py, r1_v8.py  # Test variants (see experiments/ for results)
├── probes/                              # Historical probe submissions
└── oracle/                              # God-logger + AWS Lambda probes

prosperity4bt/resources/round99/        # Synthetic regime test data (generate.py output)
├── prices_round_99_day_{0,1,2,3}.csv   # 10k ticks × 4 regimes
└── trades_round_99_day_{0,1,2,3}.csv

run-logs/round-1/
├── god-logger-run/103917/               # Clean book (zero orders)
├── 134926/                              # r1_medallion best — website 10,467.8
├── 210525/                              # Probe that found simpler-mid alpha → v2
├── 211338/                              # r1_v2 — website 10,536.81
├── 213352/                              # r1_v4 CURRENT BEST — 10,624.84
├── 228024/                              # r1_v7 — 10,465.84 (regression)
├── 228366/                              # r1_v5 — 10,612.84 (neutral)
└── 228959/                              # Nancy's algov4 benchmark — 10,734.03
```

### Reference Backtesters (Round 1 Validated)

| Backtester | Language | Matching | Key Feature |
|---|---|---|---|
| Ours (fork of jmerle P3) | Python | default/imc/sim/website | Custom `website` mode with taker supplement |
| [kevin-fu1](https://github.com/kevin-fu1/imc-prosperity-4-backtester) | Python | default (worse) | Only processes 1 buy + 1 sell vs market trades |
| [Xeeshan85/prosperity4btx](https://pypi.org/project/prosperity4btx/) | Python | all/worse/none | Published PyPI package, 3 match modes |
| [GeyzsoN/rust](https://github.com/GeyzsoN/prosperity_rust_backtester) | Rust | all + queue penetration | Position carry across days, slippage modeling |

**All confirm**: fill at ORDER price (not market trade price), all-or-nothing limit enforcement, MM non-reactive.
