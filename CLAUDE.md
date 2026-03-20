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
| `run-logs/round-0/` | Website submission logs (JSON: activitiesLog, graphLog, positions) |
| `mm_bot_profiler.py` | MM bot behavior analysis script |

## Bot Behavior (Reverse-Engineered)

### Market Maker Bot
- Quote formula: `bid = floor(mid - spread/2)`, `ask = ceil(mid + spread/2)`
- Mid changes: always multiples of 0.5, O-U mean-reversion
- Spread states: {5,6,7,8,9,13,14}. Wide (13-14) 92.8%, tight (5-9) 7.2%
- L1 vol: uniform [2-12], L2 vol: ~2.77x L1. Symmetric 93%+ of ticks
- 82.6% of quote moves are ASYMMETRIC (bid and ask move independently)
- Post-fill response: <0.3 ticks — NO exploitable lag after fills
- Narrow spreads: 1 tick duration, triggered by |mid move| >= 3, NOT predictable
- Updates quotes BEFORE matching (trades see fresh book, 100% confirmed)

### Taker Bot (ONE per product)
- TOMATOES: cadence mean 2,430ms, qty uniform [2,3,4,5], side 50/50 random
- EMERALDS: cadence mean 4,910ms, qty uniform [3,4,5,6,7,8], side 50/50 random
- 100% of trades at best bid or best ask. Pure aggressive taker.
- Timing, size, side are ALL random — no predictable pattern

### Cross-Product
- Zero lead-lag between EMERALDS and TOMATOES (all |r| < 0.02)

## Exploitable Signals (verified both days)

| Signal | Correlation | Status |
|--------|------------|--------|
| Trade flow (market_trades) | r=-0.54 | **PROVEN +207 PnL on website** |
| Microprice 4-lag regression | RMSE 1.11 | **PROVEN base (2,644 website)** |
| L2 volume imbalance | r=0.60 | Cannot shift fair value (spread cost > signal) |
| Return autocorrelation | lag-1: -0.47 | Captured by regression |
| Microprice deviation from mid | CONTRA-signal | 1.7% hit rate — AVOID using directly |
| Intraday drift | Inconsistent | Opposite between days — UNRELIABLE |

## Website Scores (Complete Record)

| Strategy | Score | Key |
|----------|-------|-----|
| s1_resting_optimized | **2,857** | **NEW BEST** — 0 risk aversion for EMERALDS |
| s2_tradeflow | 2,851 | microprice reg + trade flow |
| s2_speed_flat | 2,851 | same logic, 26% smaller file |
| s2_tradeflow_tuned (coef=2.0) | 2,753 | stronger flow HURTS |
| s1_zero_risk | 2,676 | 0 risk aversion HURTS for TOMATOES |
| 6913.py | 2,644 | microprice reg only |
| s1_avellaneda | 2,640 | + A-S skew (no effect) |
| Wall Mid approaches | ~2,600 | loses to microprice |
| s1_probes | 1,531 | probe orders are TOXIC |
| s3_tradeflow_nodrift | 1,465 | removing intercept = CATASTROPHIC |

## Critical Lessons

1. **Drift intercept 2.208667 is ESSENTIAL** — removing = -1,386 PnL
2. **Position-dependent aggression HELPS for TOMATOES** — removing = -175 PnL
3. **Trade flow coef=1.5, window=5 is OPTIMAL** — stronger/faster is worse
4. **L2 imbalance CANNOT shift fair value** — must be quote skew only (and even that has no website effect)
5. **Speed optimization has zero effect** — no missing ticks in run logs
6. **Probe orders are toxic** — small fills at bad prices get adversely selected
7. **MM bot is highly efficient** — no stale quotes, no exploitable post-fill lag
8. **Everything added to s2_tradeflow scores 2,851** — hard ceiling for signal-based approaches
9. **Resting order dynamics matter** — s1_resting_optimized got 2,857 (new best)

## Backtester Calibration Notes

- Default mode: run() every tick (simulates final scoring)
- `--iterations 1000 --ticks 2000`: approximates website test (run() every 2nd tick)
- Calibrated day -1 gives 3,394 vs website 2,851 — gap from matching engine differences
- Between run() calls, resting orders persist and can be matched by bots
