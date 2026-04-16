# Backtester Guide — Beginner-Friendly End-to-End Walkthrough

A complete guide to using the `prosperity4bt` backtester in this repository. Written for someone new to GitHub, Python projects, and IMC Prosperity backtesting.

**Scope of this document:** every user-facing knob in the backtester.
- **5 fill-simulation modes** (`--match-mode`): `default`, `strict`, `imc`, `sim`, `website` — see [Section 10](#10-match-modes-deep-dive)
- **3 CSV-trade matching modes** (`--match-trades`): `all`, `worse`, `none` — see [Section 11](#11-trade-matching-modes-deep-dive)
- **11 CLI flags** — see [Section 9](#9-all-cli-flags-explained)

If you only want to run one command and see a score, skip to **[5. Your First Backtest](#5-your-first-backtest)**.

---

## Table of Contents

1. [What This Backtester Does](#1-what-this-backtester-does)
2. [Prerequisites](#2-prerequisites)
3. [Getting the Repository](#3-getting-the-repository)
4. [Repository Layout](#4-repository-layout)
5. [Your First Backtest](#5-your-first-backtest)
6. [Writing a Trader (Minimal Example)](#6-writing-a-trader-minimal-example)
7. [Where to Place Trader Files](#7-where-to-place-trader-files)
8. [Where to Place Data Files](#8-where-to-place-data-files)
9. [All CLI Flags Explained](#9-all-cli-flags-explained)
10. [Match Modes Deep Dive](#10-match-modes-deep-dive)
11. [Trade-Matching Modes Deep Dive](#11-trade-matching-modes-deep-dive)
12. [Understanding the Output](#12-understanding-the-output)
13. [The Tick Sequence (What Happens Every Step)](#13-the-tick-sequence-what-happens-every-step)
14. [Comparing Backtester Scores to Website Scores](#14-comparing-backtester-scores-to-website-scores)
15. [Troubleshooting Common Errors](#15-troubleshooting-common-errors)
16. [Other Community Backtesters](#16-other-community-backtesters)
17. [Cheat Sheet](#17-cheat-sheet)

---

## 1. What This Backtester Does

IMC Prosperity is a trading competition where you submit a Python `Trader` class that places orders on simulated markets. The website runs your code against historical market data and gives you a PnL score.

A **backtester** lets you run that same code on your own machine, so you can:

- iterate quickly without waiting for website submission,
- compare strategies head-to-head,
- inspect every order, fill, and position tick-by-tick.

This repo's backtester is a Python fork of [jmerle/imc-prosperity-3-backtester](https://github.com/jmerle/imc-prosperity-3-backtester) restructured in OOP style. It reads CSV order-book data, calls your `Trader.run()` exactly like the website, simulates fills, and writes a log file.

**Important caveat:** the backtester is a **ranking tool, not an exact PnL predictor**. See [Section 14](#14-comparing-backtester-scores-to-website-scores).

---

## 2. Prerequisites

Install these once:

| Tool | Why | Download |
|------|-----|----------|
| **Python 3.11+** | Runs the backtester | <https://www.python.org/downloads/> |
| **Git** | Clones the repo | <https://git-scm.com/downloads> |
| **A text editor** | Edits `.py` files | VS Code, PyCharm, Notepad++ |

Verify your install in a terminal:

```bash
python --version    # should print 3.11 or higher
git --version       # should print any version
```

### Python dependencies used by the backtester

- `typer` — command-line argument parsing
- `tqdm` — progress bars
- `IPython` — stdout-capture for trader logs
- `jsonpickle` — serializing trader data (only used if your trader imports it)

Install them all in one shot:

```bash
pip install typer tqdm ipython jsonpickle
```

If you want to isolate the environment (recommended), create a virtual environment first:

```bash
python -m venv .venv
# Windows (bash/git-bash):
source .venv/Scripts/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install typer tqdm ipython jsonpickle
```

---

## 3. Getting the Repository

If you're new to GitHub, this is the part that gets you the code onto your machine.

```bash
# 1. Open a terminal in the folder where you want the project
cd ~/Projects       # or wherever you like

# 2. Clone the repository
git clone <this-repo-url> imc-prosperity-4-backtester

# 3. Move into the folder
cd imc-prosperity-4-backtester
```

You now have a local copy. Every command in this guide assumes you're running it from this folder.

---

## 4. Repository Layout

```
imc-prosperity-4-backtester/
│
├── prosperity4bt/                  THE BACKTESTER ENGINE — do not edit unless you know why
│   ├── __main__.py                 CLI entry point (the `-m prosperity4bt` command)
│   ├── back_tester.py              Top-level controller
│   ├── test_runner.py              Per-day simulation loop
│   ├── datamodel.py                TradingState / Order / OrderDepth — MUST MATCH website
│   ├── constants.py                Position limits per product
│   ├── models/
│   │   ├── test_options.py         Enums: MatchMode, TradeMatchingMode
│   │   └── input.py, output.py     Data shapes
│   ├── tools/
│   │   ├── order_match_maker.py    Fill simulation (all 5 match modes live here)
│   │   ├── data_reader.py          CSV → TradingState
│   │   ├── log_creator.py          Per-tick activity log
│   │   ├── output_file_writer.py   Final .log file
│   │   └── summary_printer.py      The PnL table you see on stdout
│   └── resources/
│       ├── round0/                 CSV market data for tutorial round
│       │   ├── prices_round_0_day_0.csv
│       │   ├── prices_round_0_day_-1.csv
│       │   ├── prices_round_0_day_-2.csv
│       │   ├── trades_round_0_day_0.csv
│       │   └── ... etc
│       └── round1/                 CSV market data for Round 1
│           └── prices_round_1_day_*.csv, trades_round_1_day_*.csv
│
├── trader-logic/                   YOUR STRATEGY FILES GO HERE
│   ├── round-0/                    Tutorial-round strategies (at-top-level = active)
│   │   ├── s36_medallion.py        Best tutorial strategy (website 2,896)
│   │   ├── s3_carry.py             Previous best
│   │   ├── best/                   Archival copies of headline strategies
│   │   ├── experiments/            Failed / ablation runs
│   │   ├── early_versions/         Older pre-tradeflow strategies
│   │   ├── sweeps/                 Parameter-sweep variants (s26–s33)
│   │   ├── diagnostics/            Bot-reactivity and conversion tests
│   │   ├── oracle/                 God-mode and extracted-IMC-source experiments
│   │   ├── analysis/, strategy/    7-module bot-exploitation pipeline
│   │   └── infrastructure/         Feature engineering, FK solver, logger
│   │
│   ├── round-1/                    Round 1 strategies (reorganized into subfolders)
│   │   ├── r1_v4.py                CURRENT BEST (website 10,624.84) — at top level
│   │   ├── refit_regression.py     Utility: auto-refit microprice regression from CSV
│   │   ├── README.md               Strategy evolution table + key learnings
│   │   ├── best/                   Archival copy of r1_v4.py with philosophy doc
│   │   ├── early_versions/         trader.py, r1_medallion.py, r1_v2.py (superseded)
│   │   ├── experiments/            r1_v3.py, r1_hybrid.py, r1_adaptive.py, r1_medallion_dp.py
│   │   ├── references/             r1_troll.py (competitor code for study)
│   │   ├── templates/              template_stable.py, template_random_walk.py, … (6 archetypes)
│   │   ├── probes/                 Lambda-environment probes (separate workflow)
│   │   └── oracle/                 God-logger + zero-order traders
│   │
│   ├── auction_solver.py           Manual-challenge optimizer (not a backtest)
│   └── auction_writeup.md          Manual-challenge solution
│
├── backtests/                      OUTPUT FOLDER — auto-created, filled with .log files
├── run-logs/                       Website submission ZIPs (for reference)
│
├── CLAUDE.md                       Working notes (bot behavior, lessons learned)
├── README.md                       Short project intro
├── BACKTESTER_GUIDE.md             ← you are here
└── LICENSE
```

**Rule of thumb:** everything inside `prosperity4bt/` is engine code. Everything inside `trader-logic/` is strategy code you write or edit.

---

## 5. Your First Backtest

From the repo root, run:

```bash
# Recommended starting point — runs the current-best strategy (r1_v4, website 10,624.84)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1

# Older baseline for comparison (pre-drift-bias, website 4,934)
python -m prosperity4bt trader-logic/round-1/early_versions/trader.py 1
```

Breakdown:

- `python -m prosperity4bt` — runs the backtester package
- `trader-logic/round-1/r1_v4.py` — **your trader file** (path relative to repo root)
- `1` — **round number** (runs every available day for round 1)

You should see a progress bar per day, then a PnL summary like:

```
Backtesting trader-logic/round-1/r1_v4.py for round: 1 day: -2
[progress bar]
Day summary:
  ASH_COATED_OSMIUM      PnL:   3,179
  INTARIAN_PEPPER_ROOT   PnL:   7,446
  TOTAL                  PnL:  10,625
...
Successfully saved backtest results to backtests/2026-04-17_10-30-12.log
```

A `.log` file appears in `backtests/`. You can upload that log to [jmerle's visualizer](https://jmerle.github.io/imc-prosperity-3-visualizer/) to see charts of mid-price, positions, PnL, and fills.

### Running a single day

Use `<round>-<day>` (day numbers can be negative):

```bash
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1-0     # round 1, day 0
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1--1    # round 1, day -1 (note double dash)
python -m prosperity4bt trader-logic/round-0/s3_carry.py 0--2 # round 0, day -2
```

---

## 6. Writing a Trader (Minimal Example)

Your strategy is a Python class called `Trader` with a `run()` method. Minimum viable trader:

```python
# save as trader-logic/round-1/my_first_trader.py
from datamodel import TradingState, Order

class Trader:
    def run(self, state: TradingState):
        orders = {}          # dict[product_name, list[Order]]
        conversions = 0      # int — used in later rounds, leave 0 for now
        trader_data = ""     # string — persisted to next tick (state memory)

        # Example: buy 1 unit of INTARIAN_PEPPER_ROOT at price 11,000 every tick
        orders["INTARIAN_PEPPER_ROOT"] = [Order("INTARIAN_PEPPER_ROOT", 11000, 1)]

        return orders, conversions, trader_data
```

**Key rules:**

| Thing | Rule |
|-------|------|
| Import | `from datamodel import TradingState, Order` (not `from prosperity4bt.datamodel`) |
| `Order(symbol, price, quantity)` | positive `quantity` = BUY, negative = SELL |
| `OrderDepth.sell_orders` | volumes are stored as **negative** integers |
| `OrderDepth.buy_orders` | volumes are positive integers |
| Position limits | 80 per product (see `prosperity4bt/constants.py`) |
| Position-limit check | all-or-nothing per product per side: if total buys + current position > 80, **ALL buys for that product are rejected** |
| `trader_data` | plain string, max 50,000 chars, passed back as `state.traderData` on the next call |

### Reading the book

```python
book = state.order_depths["INTARIAN_PEPPER_ROOT"]
best_bid = max(book.buy_orders.keys())       # highest price someone will buy from us
best_ask = min(book.sell_orders.keys())      # lowest price someone will sell to us
best_bid_vol = book.buy_orders[best_bid]     # positive
best_ask_vol = -book.sell_orders[best_ask]   # stored negative, flip for volume
current_position = state.position.get("INTARIAN_PEPPER_ROOT", 0)
```

### Persisting state across ticks

```python
import json

class Trader:
    def run(self, state: TradingState):
        # Restore from prior tick
        memory = json.loads(state.traderData) if state.traderData else {"history": []}

        # Use it
        mid = (max(state.order_depths["INTARIAN_PEPPER_ROOT"].buy_orders)
             + min(state.order_depths["INTARIAN_PEPPER_ROOT"].sell_orders)) / 2
        memory["history"].append(mid)
        memory["history"] = memory["history"][-20:]  # keep last 20

        orders = {}
        # ... your logic here ...

        return orders, 0, json.dumps(memory)
```

For real, production-grade examples, read `trader-logic/round-1/r1_v4.py` (current best) or `trader-logic/round-0/s36_medallion.py`. Older Round 1 strategies that show the evolution are in `trader-logic/round-1/early_versions/` (`trader.py` → `r1_medallion.py` → `r1_v2.py`).

---

## 7. Where to Place Trader Files

**You can put them anywhere**, because the CLI accepts any path. The convention in this repo is:

- `trader-logic/round-<N>/<your_name>.py` — **active** strategy (what you're currently iterating on) lives at the top level
- `trader-logic/round-<N>/best/<name>.py` — archival copy of a headline strategy + README documenting the score
- `trader-logic/round-<N>/early_versions/` — strategies superseded by the current best (kept for diffing and reference)
- `trader-logic/round-<N>/experiments/` — failed or abandoned experiments kept for lessons-learned
- `trader-logic/round-<N>/templates/` — per-archetype starter templates (stable / random_walk / basket / options / conversion / olivia)
- `trader-logic/round-<N>/references/` — competitor strategies imported for study
- `trader-logic/round-<N>/probes/` — one-off Lambda-environment probes (separate workflow, not run through the backtester)
- `trader-logic/round-<N>/oracle/` — god-mode and zero-order traders for pristine data extraction
- Use descriptive names: `s3_carry.py`, `r1_drift_heavy.py`, `my_first_trader.py`

When you run it, just point at the file:

```bash
python -m prosperity4bt trader-logic/round-1/my_first_trader.py 1
# or equivalently:
python -m prosperity4bt ./trader-logic/round-1/my_first_trader.py 1
```

Absolute paths work too:

```bash
python -m prosperity4bt C:/my-folder/my_trader.py 1
```

### Why `from datamodel import ...` works

When the backtester loads your trader file, it adds the file's parent directory to `sys.path`. It also bundles `datamodel.py` in the `prosperity4bt/` package and makes it importable as a top-level `datamodel` module (same as the website environment).

If you see `ModuleNotFoundError: No module named 'datamodel'`, set `PYTHONPATH`:

```bash
# Windows PowerShell:
$env:PYTHONPATH="C:\path\to\imc-prosperity-4-backtester\prosperity4bt"

# Windows Git-Bash / Linux / macOS:
export PYTHONPATH="/c/path/to/imc-prosperity-4-backtester/prosperity4bt"
```

---

## 8. Where to Place Data Files

Data lives in `prosperity4bt/resources/round<N>/`. File-naming convention (exact match required):

```
prices_round_<N>_day_<D>.csv       ← order-book snapshots
trades_round_<N>_day_<D>.csv       ← public market trades (optional)
observations_round_<N>_day_<D>.csv ← conversion observations (later rounds)
```

- `<N>` = round number (integer, e.g. `0`, `1`, `2`)
- `<D>` = day number (integer, negative allowed, e.g. `-2`, `-1`, `0`, `1`)

Examples that exist in this repo:

```
prosperity4bt/resources/round0/prices_round_0_day_-2.csv
prosperity4bt/resources/round0/trades_round_0_day_0.csv
prosperity4bt/resources/round1/prices_round_1_day_1.csv
```

### Adding a new round or day

1. Create a folder `prosperity4bt/resources/round<N>/` if it doesn't exist.
2. Drop in `prices_round_<N>_day_<D>.csv` (and trades/observations if you have them).
3. Update `data_reader.py → available_days()` to list the day numbers:
   ```python
   def available_days(self, round: int) -> list[int]:
       if round == 2:
           return [-1, 0, 1]
       # ...
   ```
4. Run: `python -m prosperity4bt your_trader.py 2`

### CSV format (prices)

Semicolon-separated. Columns (in order):

```
day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;mid_price;profit_and_loss
```

Up to 3 bid and 3 ask levels (L1–L3). Trailing empty levels are fine.

### CSV format (trades)

```
timestamp;buyer;seller;symbol;currency;price;quantity
```

Open the existing CSVs in `prosperity4bt/resources/` to see working examples.

---

## 9. All CLI Flags Explained

Full signature (from `prosperity4bt/__main__.py`):

```bash
python -m prosperity4bt <algorithm> <days> [OPTIONS]
```

### Positional arguments

| Arg | What it is | Example |
|-----|------------|---------|
| `algorithm` | Path to your `.py` file containing the `Trader` class | `trader-logic/round-1/r1_v4.py` |
| `days` | One or more `<round>` or `<round>-<day>` specs | `1` runs all days; `1-0` runs only round 1 day 0; you can pass multiple: `0 1 2-1` |

### Options

| Flag | Default | What it does |
|------|---------|--------------|
| `--out <path>` | `backtests/<timestamp>.log` | Write the output log to this file |
| `--no-out` | off | Skip writing the log file entirely (useful for quick sweeps) |
| `--data <path>` | built-in | Load CSVs from a different folder (for custom data) |
| `--print` | off | Stream your trader's `print()` output to stdout as it runs |
| `--match-trades {all,worse,none}` | `all` | See [Section 11](#11-trade-matching-modes-deep-dive) |
| `--match-mode {default,imc,strict,sim,website}` | `default` | See [Section 10](#10-match-modes-deep-dive) |
| `--no-progress` | off | Hide the per-day tqdm progress bar |
| `--merge-pnl` / `--no-merge-pnl` | `--merge-pnl` | Sum PnL across days into one total |
| `--original-timestamps` | off | Keep raw CSV timestamps; default shifts them so they increase across days |
| `--ticks <N>` | unlimited | Cap how many ticks to simulate per day. Use `1000` for Round 1 tutorial conditions, `10000` for full scoring. |
| `--iterations <N>` | None (call every tick) | Call `run()` only N times per day. Between calls, the previous tick's orders rest in the book. **Leave this blank for tutorial rounds** — the website calls `run()` on every tick. |
| `--vis` | off | (placeholder) would open the visualizer after the run — currently stubbed |

### Common command recipes

```bash
# Full run across every day in a round (final-scoring style)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --ticks 10000

# Tutorial / test conditions (1k ticks, every tick, like the website test submission)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1-0 --ticks 1000

# Silent fast run: no log, no progress, merged PnL
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --no-out --no-progress

# Debug run: see your trader's prints
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1-0 --ticks 50 --print

# Use calibrated matching mode (matches website within ~2% on ACO)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --match-mode imc

# Multiple round-day specs in one run
python -m prosperity4bt my_trader.py 0 1-0 1-1
```

---

## 10. Match Modes Deep Dive

`--match-mode` controls **how fills are simulated**. There are five modes. Pick one based on the tradeoff you want.

| Mode | Philosophy | When to use |
|------|-----------|-------------|
| `default` | Original `>=` crossing + replay CSV market trades against you | General use, matches jmerle's P3 backtester behavior |
| `strict` | Exact `==` price matching only, no extra takers | Conservative floor — what would fill if nothing else happened |
| `imc` | `==` matching + deterministic "extra taker" supplementation | Best match to website for stable products (calibrated) |
| `sim` | Agent-based simulation with Poisson taker arrivals | Research / stress testing — noisy, not repeatable |
| `website` | Detects taker arrivals from book structure, routes them through unified book | Experimental — attempts to close the CSV-vs-website gap |

### 10.1 `default` mode (the original)

1. For each of your orders, check if the current book has levels at-or-better than your price.
2. If yes, fill against those levels up to their volume.
3. If your buy order still has qty remaining, also try to match against any CSV market-trades at that timestamp whose sell-side price ≤ your price.

This is what the upstream jmerle P3 backtester does. It overcounts fills in markets where the CSV trades file already contains trades you would have intercepted.

### 10.2 `strict` mode (exact matching only)

Same as `default` but without the CSV-market-trade fallback. Only fills that occur are where your order price exactly crosses a level already on the book.

**Use case:** lower-bound sanity check. If your strategy profits here, it profits for real.

### 10.3 `imc` mode (recommended for ranking)

Mirrors the actual IMC game engine:

1. MM bot posts the book (from CSV).
2. Your aggressive orders cross immediately against the MM book (price-clamped to best bid/ask, `==` exact semantics).
3. Your unfilled orders rest inside the spread.
4. An "extra taker" is injected probabilistically using a calibrated rate per product. The taker only fills **your resting order** if you improved the MM's best.

The extra-taker rate is deterministic (hashed from timestamp) so runs are reproducible. Calibrated values live in `TAKER_PARAMS` in `order_match_maker.py`:

```python
"INTARIAN_PEPPER_ROOT": extra_rate=0.0     # no extras needed (99.8% match without)
"ASH_COATED_OSMIUM":    extra_rate=0.064   # calibrated: day1 score 3,122 vs website 3,091
"TOMATOES":             extra_rate=0.0053
"EMERALDS":             extra_rate=0.0
```

**This mode is the default recommendation for Round 1+** because it reproduces the "invisible taker" fills that the website sees but the CSV doesn't contain.

### 10.4 `sim` mode (agent-based simulation)

Rebuilds the entire book from scratch each tick using the same Rust-engine semantics (sorted-key price-time priority), adds your orders, then simulates a full taker bot:

- Poisson-arrival taker with cadence `TICK_MS / params.cadence_ms` per product
- Taker side: 50/50 random
- Taker qty: uniform `[qty_lo, qty_hi]` per product
- Taker fill probability decays with spread width: `p_fill = exp(-0.007 * spread)`

**Non-deterministic** (uses `random.random()`). Useful for stress-testing, not for reproducible comparisons.

### 10.5 `website` mode (experimental)

Tries to detect taker arrivals from orderbook structure (tight spread + volume asymmetry) instead of relying on the CSV trades file. Combines CSV trades with Poisson supplement and routes everything through a unified book.

Still under investigation. Use `imc` for production ranking work.

### 10.6 Mode Limitations (what each mode gets wrong)

No simulation mode is a perfect substitute for the website. Know what each one cannot model:

| Mode | Known limitations |
|------|-------------------|
| `default` | Matches `>=` instead of the game engine's exact `==` semantics → overfills on spread-crossing orders. Also replays CSV trades *against you*, which overcounts fills when the CSV already contains takers you would have intercepted. No "invisible taker" modeling for inside-spread orders. |
| `strict` | Removes CSV-trade matching entirely → severely underestimates fills for inside-spread MM strategies. Your best±1 quotes appear to earn nothing because no taker ever arrives. Lower-bound sanity check, not a realistic estimate. |
| `imc` | Hardcoded per-product `extra_rate` in `order_match_maker.py → TAKER_PARAMS`. Calibrated on Round 1 tutorial (1,000 ticks) — rates may not scale linearly to full 10,000-tick days. Deterministic hash-based taker arrival is reproducible but not stochastic; a single adverse seed never appears. New products (Round 2+) need `extra_rate` refit before this mode is trustworthy. Matches ACO within 1.6%; IPR within 99.8% only because `extra_rate=0.0` for IPR. |
| `sim` | Non-deterministic (uses `random.random()`) — every run produces a different score. Poisson taker model assumes CoV=1.0, but Round 1 taker CoV is 0.76–0.81 (more regular than Poisson). Does not consume CSV market_trades, so all taker pressure is synthetic. Useful for stress-testing, not ranking. |
| `website` | Experimental. Heuristic taker detection from `tight spread + L1 volume asymmetry`; thresholds (`_TIGHT_SPREAD`, `_NORMAL_L1_VOL`) are hardcoded per product from Round 0 forensics only — untested on Round 1+. Can double-count if CSV trade and structural detection both fire on the same tick. |

**Universal limitations (apply to every mode):**

- The CSV is a market realization **without your orders**. Any fill your orders would have induced on the website is either missing (default/strict) or approximated (imc/sim/website). This is irreducible without per-tick agent-based rollout.
- `state.position` is reset to 0 at the start of each day. Multi-day inventory effects (carry across day boundaries) are not modeled.
- The MM bot does not react to your orders in any mode — confirmed by replay, so this is accurate, but it also means you cannot test strategies that *depend* on MM reaction.
- One-sided book ticks (~9% of Round 1) are passed through as-is; if your strategy dereferences `max(book.buy_orders)` on an empty side, it crashes — the backtester does not guard against this.
- No conversion economics (transport fees, tariffs) until you provide `observations_round_<N>_day_<D>.csv` and your trader returns a non-zero `conversions` value.

### When to use which

| Goal | Use this mode |
|------|----------------|
| Quick sanity check | `default` or `strict` |
| Rank strategies for website submission | `imc` |
| Stress-test with random takers | `sim` |
| Exploratory taker modeling | `website` |
| Estimate worst-case (no invisible takers) | `strict` |
| Estimate upper bound (aggressive CSV matching) | `default` |

---

## 11. Trade-Matching Modes Deep Dive

`--match-trades` is orthogonal to `--match-mode`. It controls how your orders match against **CSV market trades** (the public trades file) in `default` mode:

| Value | Behavior |
|-------|----------|
| `all` (default) | Your order matches any CSV trade where the price is equal to **or worse than** your quote |
| `worse` | Only matches CSV trades with price **strictly worse** than yours (skip equal-price) |
| `none` | Ignore CSV trades entirely; only match against the live book snapshot |

Most of the time you can leave this alone. If your strategy double-counts fills (e.g. reading `market_trades` as a signal that then causes your own trade to be re-matched), try `worse` or `none`.

---

## 12. Understanding the Output

### The PnL summary printed to your terminal

```
Day summary:
  ASH_COATED_OSMIUM      PnL:   3,091    Pos:  -2     Trades:  101
  INTARIAN_PEPPER_ROOT   PnL:   7,354    Pos:  80     Trades:   37
  TOTAL                  PnL:  10,445
```

- **PnL** = cash flow + mark-to-market of residual position
- **Pos** = end-of-day inventory (should usually be small unless you're holding a directional bet)
- **Trades** = number of fills

### The `.log` file

Lives at `backtests/<timestamp>.log` by default. It has three sections separated by headers:

```
Sandbox logs:
{"timestamp": 0, "sandboxLog": "", "lambdaLog": "<your prints>"}
...

Activities log:
day;timestamp;product;bid_price_1;...;profit_and_loss
...

Trade History:
[ {"timestamp": 100, "buyer": "SUBMISSION", "seller": "", ...}, ... ]
```

Upload the whole file to [jmerle's visualizer](https://jmerle.github.io/imc-prosperity-3-visualizer/) for charts.

### Reading the log programmatically

The format matches the IMC website's submission log exactly, so any tool that parses an IMC submission log also parses this.

---

## 13. The Tick Sequence (What Happens Every Step)

The IMC engine (and this backtester) does this per tick:

1. **Fresh book** — MM bot posts new quotes from the CSV data for this timestamp.
2. **Your `run(state)` is called** — you see the fresh book, return orders.
3. **Position limits enforced** — if any product's total buys + position > 80 (or total sells - position > 80), **all orders for that product are dropped**. Enforcement is all-or-nothing per side per product.
4. **Aggressive takes execute** — orders crossing the book fill immediately against the MM's levels.
5. **Unfilled rest** — remaining orders become passive levels inside the spread.
6. **Taker arrives** (in `imc`/`sim`/`website` modes) — a market order hits the best bid/ask by price priority. If your resting order is the effective best, you get hit.
7. **Next tick** — in `default` mode, your orders reset each call; in modes with `--iterations < ticks`, resting orders carry forward.

### Game-engine facts that surprise newcomers

- **The MM bot is not reactive** — it does not change its spread based on your orders. Confirmed by replaying "zero orders" vs a trading run: the CSV books are byte-identical.
- **Position limits are per side, all-or-nothing** — a single over-limit order dumps every order for that product that tick. Check your math.
- **`sell_orders` volumes are negative** — quirky but consistent. `book.sell_orders[price]` returns something like `-12`.
- **`state.own_trades` / `state.market_trades` are cleared every tick** — they contain only trades from the previous tick, not a running history. Store history in `trader_data` if you need it.

---

## 14. Comparing Backtester Scores to Website Scores

**The backtester is a ranking tool, not an absolute PnL predictor.**

Calibration results from Round 1 submissions (CLAUDE.md documents the full grid):

| Strategy | Website | Local BT | Gap | Notes |
|----------|--------:|---------:|----:|-------|
| r1_v4 (current best) | **10,624.84** | ≈8,970 | +18% | simple-mid IPR + LU-clear ACO |
| r1_v2 | 10,536.81 | ≈8,900 | +18% | simple mid + drift_bias=5 |
| r1_medallion | 10,467.80 | ≈8,860 | +18% | microprice regression + drift=6 |
| trader (basic) | 4,933.80 | 6,528 | +32% | no drift bias |
| (Round 0) s3_carry | 2,857 | 2,626 | −8% | inside-spread MM |
| (Round 0) s25 | 2,855 | 2,684 | −6% | cross-validated baseline |

Key lessons:

- **Relative ordering is preserved for structural comparisons.** If strategy A > strategy B locally and both use the same framework, A > B on website.
- **Absolute magnitude drifts** — volume-dependent features (IPR) see different inputs on website.
- **WARNING — the backtester is an INVERSE INDICATOR for IPR framework changes.** Example: `r1_v3` (Linear-Utility-on-IPR) ranked BEST in the backtester but WORST on the website (7,975 vs r1_v4's 10,625, a −2,650 regression). The backtester overrewards clearing behavior that the live market punishes. Treat IPR framework changes as untrusted until submitted.
- Round 0 day 0 CSV = website data (100% book match). Round 1 day 0 CSV ≠ website (36% match).
- For ACO-like stable products, `--match-mode imc` gets you within ~2% of website.
- For drift products (IPR), absolute scores can swing ±30% — use backtester only for A/B comparison of same-family strategies.
- **Practical ceiling ~10,625** on Round 1. Competitors also converged there via different paths — the remaining gap to #1 (11,744) is likely seed variance.
- The **Linear Utility take/clear/make framework** (from P2 winner) is worth +3% on stable products like ACO (+88 PnL, theory predicted +87). Do NOT apply it to drift products.

**When you submit to the website, expect scores to differ. Don't over-tune to hit a backtester target.**

### 14.1 Accuracy History — what we fixed and how much it mattered

The backtester used to be catastrophically misleading. Two silent bugs in `test_runner.py` made some strategies look great locally and fail on the website. Fixing them is what brought absolute error from "completely wrong" to "within ~7% on book-only strategies."

**Pre-fix (before 2026-03-21):** strategies that fought feedback loops or had partial-fill interactions ranked wrong.

| Strategy | Website | Local BT (pre-fix) | Sign |
|----------|--------:|-------------------:|:----:|
| s19_hybrid_fv | 2,676 | +92 over baseline | **LIED — was actually −175 on website** |
| s11_replace_microprice | 1,936 | +1,084 over baseline | **LIED — was actually −915 on website** |

**Bug #1 — stale `own_trades` / `market_trades`:** Neither dict was cleared between ticks. Trades from tick N leaked into tick N+1, causing PnL trackers and trade-flow signals to double/triple-count. Any strategy reading `state.own_trades` as a signal saw a corrupted history.
**Fix:** clear both at the start of every tick in `__initialize_trade_state()`.

**Bug #2 — resting order quantities not updated after partial fills:** `__deep_copy_orders()` snapshotted orders *before* matching. After a partial fill, the resting-order snapshot kept the original quantity. Position limits were then violated on the next tick, triggering the all-or-nothing reject — so subsequent orders vanished silently.
**Fix:** re-snapshot `resting_orders` after every matching pass.

**Bug #3 — wrong iteration count for tutorial scoring:** The README previously recommended `--iterations 1000`, which made `run()` only fire on 50% of ticks (the rest used stale resting orders). Website log analysis (run 8587) showed the site actually calls `run()` on every tick.
**Fix:** omit `--iterations` entirely (or set it equal to `--ticks`). Only use `--iterations` if you want to simulate a degraded-cadence environment.

**Post-fix accuracy (2026-03-21 onwards):**

| Strategy class | Gap vs website |
|----------------|---------------:|
| Book-only (takes cross the MM, no inside-spread make) | within 1% |
| Inside-spread MM (depends on invisible takers) | 6–9% undershoot in `default` mode |
| Stable products with `--match-mode imc` (ACO) | 1.6% |
| Drift products (IPR) with `--match-mode imc` | 99.8% match locally, but absolute PnL swings ±30% across days because CSV ≠ website |

**Rule of thumb after the fixes:** for inside-spread MM strategies, apply `website ≈ backtester × 1.07`. For at-spread / take-based strategies, backtester matches within ±2% without correction. **Never patch the backtester further to hit known website scores** — that is overfitting the infrastructure.

**Mode-specific calibration (Round 1 day 0, 1,000 ticks):**

| `--match-mode` | ACO local | ACO website | Error | Notes |
|----------------|----------:|------------:|------:|-------|
| `default` | 2,633 | 3,091 | −14.8% | no invisible-taker simulation |
| `strict` | 2,633 | 3,091 | −14.8% | identical to default here because no CSV trades at inside-spread |
| `imc` (extra_rate=0.064) | 3,122 | 3,091 | **+1.0%** | recommended for ACO |
| `sim` | varies run-to-run | 3,091 | ±5–10% stochastic | non-deterministic |
| `website` | ~3,050 | 3,091 | −1.3% | experimental |

### 14.2 Cross-backtester validation

On Round 1 day 0, 1,000 ticks, same CSV:

| Backtester | r1_medallion | basic trader | vs website (+295 expected gap) |
|-----------|-------------:|-------------:|-------------------------------:|
| **Website (ground truth)** | **5,229** | **4,934** | — |
| Ours (`default`) | 6,640 | 6,528 | +112 gap ✓ (same sign, different magnitude) |
| Ours (`imc`) | ~6,700 | ~6,580 | +120 gap ✓ |
| GeyzsoN Rust | 6,640 | 6,528 | +112 gap ✓ (byte-identical to ours) |
| Kevin-fu1 Python | 7,814 | 7,702 | +112 gap ✓ (18% higher absolute) |
| Xeeshan prosperity4btx | 7,814 | 7,702 | +112 gap ✓ (same as Kevin) |

All five backtesters agree on **ranking** and on the **delta between strategies**. They disagree on absolute PnL by 20–60% because CSV ≠ website data (36% L1 price match for Round 1). This is irreducible without rolling out a per-tick agent simulation — which `sim` attempts and which introduces its own calibration problems.

---

## 15. Troubleshooting Common Errors

### `No module named 'datamodel'`

`PYTHONPATH` isn't set. Run:

```bash
# Windows PowerShell
$env:PYTHONPATH="C:\Users\you\PycharmProjects\imc-prosperity-4-backtester\prosperity4bt"

# Bash (git-bash, Linux, macOS)
export PYTHONPATH="$PWD/prosperity4bt"
```

Or make your trader file's `import` use the installed module path:

```python
from prosperity4bt.datamodel import TradingState, Order  # works without PYTHONPATH
```

But the **website expects `from datamodel import ...`**, so prefer the PYTHONPATH approach for portability.

### `<file> does not expose a Trader class`

Your file must define a class named exactly `Trader` (capital T). Not `trader`, not `MyTrader`.

### `Warning: no data found for round N day D`

The CSV files aren't where the reader expects. Check:

- File is at `prosperity4bt/resources/round<N>/prices_round_<N>_day_<D>.csv`
- Filename matches the convention exactly (case-sensitive on Linux/macOS)
- `data_reader.py → available_days()` lists `<D>` for round `<N>`

### `Orders for product X exceeded limit of 80 set`

Your orders breach the position limit, so **all orders for that product that tick are dropped**. Not a crash, but a silent loss. Fix by computing `buy_cap = LIMIT - position` and `sell_cap = LIMIT + position` before sizing orders.

### Progress bar shows but no output appears

You're running in a shell that buffers stdout. Add `-u` to Python for unbuffered output:

```bash
python -u -m prosperity4bt my_trader.py 1
```

### Trader errors mid-run

The backtester doesn't catch exceptions thrown inside `run()`. Wrap suspicious code in try/except, or run a short tick count first to find the bug:

```bash
python -m prosperity4bt my_trader.py 1-0 --ticks 10 --print
```

---

## 16. Other Community Backtesters

If you want a second opinion on your strategy's ranking, these are known-working alternatives (validated against this repo on Round 1 day 0):

| Backtester | Language | Install | Notes |
|-----------|----------|---------|-------|
| **This repo** | Python | `git clone` | 5 match modes, calibrated `imc` mode |
| [jmerle/imc-prosperity-3-backtester](https://github.com/jmerle/imc-prosperity-3-backtester) | Python | `pip install prosperity3bt` | The upstream original (P3 products) |
| [kevin-fu1/imc-prosperity-4-backtester](https://github.com/kevin-fu1/imc-prosperity-4-backtester) | Python | `git clone` | More permissive market-trade matching (≈18% higher scores) |
| [Xeeshan85/prosperity4btx](https://pypi.org/project/prosperity4btx/) | Python | `pip install prosperity4btx` | PyPI-published, same matching as kevin-fu1 |
| [GeyzsoN/prosperity_rust_backtester](https://github.com/GeyzsoN/prosperity_rust_backtester) | Rust | `cargo build --release` | Fast, matches our scores within 1 unit |

All of them agree on the **ranking** of strategies — pick whichever is easiest for you.

---

## 17. Cheat Sheet

```bash
# === SETUP (once) ===
git clone <repo-url>
cd imc-prosperity-4-backtester
pip install typer tqdm ipython jsonpickle
export PYTHONPATH="$PWD/prosperity4bt"   # or $env:PYTHONPATH="..." on PowerShell

# === RUN ===
# All days of round 1
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1

# One day
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1-0

# Tutorial conditions (1k ticks per day, every tick)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --ticks 1000

# Full scoring conditions (10k ticks per day)
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --ticks 10000

# Best website-matching mode
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --match-mode imc

# Fast / silent for sweeps
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1 --no-out --no-progress

# Debug a crash
python -m prosperity4bt trader-logic/round-1/r1_v4.py 1-0 --ticks 20 --print

# === TRADER FILE ===
# trader-logic/round-N/<name>.py
from datamodel import TradingState, Order

class Trader:
    def run(self, state: TradingState):
        orders = {}
        conversions = 0
        trader_data = ""
        # ... your logic ...
        return orders, conversions, trader_data

# === DATA FILE LOCATIONS ===
prosperity4bt/resources/round<N>/prices_round_<N>_day_<D>.csv
prosperity4bt/resources/round<N>/trades_round_<N>_day_<D>.csv

# === OUTPUT ===
backtests/<timestamp>.log   → upload to https://jmerle.github.io/imc-prosperity-3-visualizer/

# === MATCH MODES (--match-mode) ===
default   # original >= crossing + CSV fallback
strict    # == exact only, no taker
imc       # == exact + calibrated extra-taker (RECOMMENDED)
sim       # full agent sim with Poisson taker (random, not reproducible)
website   # detect takers from book structure (experimental)

# === TRADE MATCHING (--match-trades) ===
all       # default — match CSV trades at-or-worse
worse     # only strictly-worse CSV trades
none      # ignore CSV trades entirely
```

---

**Next steps:**

1. Copy `trader-logic/round-1/templates/template_stable.py` to `trader-logic/round-1/my_trader.py` and tweak.
2. Run it with `python -m prosperity4bt trader-logic/round-1/my_trader.py 1`.
3. Upload the `backtests/*.log` to the visualizer to see what your orders did.
4. When scores look good, submit the **same `.py` file** to the IMC Prosperity website.

Happy trading.
