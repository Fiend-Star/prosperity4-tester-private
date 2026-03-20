# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Backtester

```bash
# Set PYTHONPATH if you get "No module named 'datamodel'"
$env:PYTHONPATH="c:\Users\gurms\PycharmProjects\imc-prosperity-4-backtester\prosperity4bt"

# Run on all days in a round
python -m prosperity4bt trader-logic/round-0/trader.py 0

# Run specific round-day
python -m prosperity4bt trader-logic/round-0/trader.py 0-0

# Limit ticks (2k for quick test, 10k for full)
python -m prosperity4bt trader-logic/round-0/trader.py 0 --ticks 2000

# Key flags
#   --match-trades {all|worse|none}   Trade matching mode (default: all)
#   --no-out                          Skip saving .log file
#   --print                           Show trader stdout
```

Output logs go to `backtests/<timestamp>.log`.

## Architecture

OOP backtester based on [jmerle/imc-prosperity-3-backtester](https://github.com/jmerle/imc-prosperity-3-backtester). Flow:

```
BackTester → for each round/day:
  TestRunner reads CSVs (prosperity4bt/resources/round{N}/)
    → for each 100ms tick:
      1. Build TradingState from order book data
      2. Call Trader.run(state) → (orders, conversions, trader_data)
      3. Log activity snapshot
      4. Enforce position limits (reject ALL orders for a side if aggregate exceeds limit)
      5. OrderMatchMaker: match orders vs book, then vs market_trades
    → Return BacktestResult
  ResultMerger consolidates days → OutputFileWriter writes .log
```

Position limits checked **per side independently**: if total buy quantity would breach `limit - position`, ALL buy orders rejected (sell orders evaluated separately).

## Trader Strategy Contract

Every trader file must expose a `Trader` class:

```python
from datamodel import TradingState, Order
import json

class Trader:
    def bid(self):       # Required for Round 2 auction mechanic
        return 15

    def run(self, state: TradingState):
        orders = {}      # dict[Symbol, list[Order]]
        conversions = 0  # int (unused in tutorial)
        trader_data = "" # str (JSON, persisted to next tick, 50k char cap)
        return orders, conversions, trader_data
```

**Order format:** `Order(symbol, price, quantity)` — positive qty = buy, negative = sell.

**OrderDepth:** `sell_orders` volumes are **negative** integers. Use `-v` or `abs(v)` when computing quantities.

**Position limits:** EMERALDS: 80, TOMATOES: 80 (in `prosperity4bt/constants.py`).

**Do NOT modify** `prosperity4bt/datamodel.py` — shared with the official Prosperity environment.

## Key Files

| Path | Role |
|------|------|
| `prosperity4bt/back_tester.py` | Main controller |
| `prosperity4bt/test_runner.py` | Per-day simulator, limit enforcement |
| `prosperity4bt/datamodel.py` | TradingState, Order, OrderDepth, Trade — **do not edit** |
| `prosperity4bt/constants.py` | Position limits dict |
| `prosperity4bt/tools/order_match_maker.py` | Simulates exchange matching |
| `prosperity4bt/tools/data_reader.py` | CSV → BacktestData |
| `trader-logic/round-0/` | All trading strategy files |
| `run-logs/round-0/` | Website submission logs (JSON with activitiesLog, graphLog, positions) |

## Available Data Per Tick

Via `TradingState`:
- `order_depths[symbol]` — L1-L3 bid/ask prices and volumes
- `market_trades[symbol]` — bot-to-bot trades from previous tick
- `own_trades[symbol]` — your fills from previous tick
- `position[symbol]` — current net inventory
- `timestamp` — 0 to 199900 (step 100)
- `traderData` — your persisted JSON from previous tick

## Competition Context

- **IMC Prosperity 4** tutorial round: EMERALDS (stable, fair=10000) + TOMATOES (volatile, drifting)
- Website test: 2k ticks on day -1. Final scoring: 10k ticks on unseen day.
- AWS Lambda: 900ms timeout, stateless. Execution speed matters.
- Available libs: pandas, numpy, statistics, math, typing, jsonpickle + Python 3.12 stdlib
- Zero latency vs bots, price-time priority, no PvP
- Round 0 data: days [-2, -1] in `prosperity4bt/resources/round0/`

## Proven Findings (from EDA)

**TOMATOES microstructure (stable across days):**
- Bot quote formula: `bid = floor(mid - spread/2)`, `ask = ceil(mid + spread/2)`
- Mid changes: always multiples of 0.5, O-U mean-reversion (lag-1 autocorr = -0.43)
- Spread: {5,6,7,8,9,13,14}. Wide (13-14) 92.8%, tight (5-9) 7.2%
- L1 vol: uniform [2-12], L2 vol: ~2.77× L1. Symmetric 93%+ of ticks
- L2 imbalance strongest signal (r=0.60) but cannot be used for fair value shifts (spread cost > signal)
- Trade flow from market_trades: r=-0.54, proven +207 PnL on website
- Drift direction UNRELIABLE across days (opposite on day -2 vs day -1)
- Drift intercept (2.208667) is ESSENTIAL — removing it crashes PnL

**Website scores (best → worst):**
- s2_tradeflow (microprice reg + trade flow): **2,851** ← current best
- 6913.py (microprice reg only): 2,644
- Wall Mid approaches: ~2,600
- Regime switching / no-drift: catastrophic
