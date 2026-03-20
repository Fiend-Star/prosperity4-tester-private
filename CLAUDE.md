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

## Website Scores (Complete Record — 25+ submissions)

| Strategy | Score | Key |
|----------|-------|-----|
| s3_carry | **2,857** | **BEST** — mean-reversion carry |
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

## Backtester Calibration

- Default mode: run() every tick (simulates final scoring)
- `--iterations 1000 --ticks 2000`: approximates website test (run() every 2nd tick)
- Calibrated day -1 gives 3,394 vs website 2,851 — gap from matching engine differences
- Between run() calls, resting orders persist and can be matched by bots
- Backtester uses STATIC book from CSV; website has dynamic bot interaction with our orders

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
