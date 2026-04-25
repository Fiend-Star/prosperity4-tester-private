# Round 3 — Gloves Off

## Status: SHIPPED ✓

| Metric | Value |
|---|---|
| **Algo submission** | `r3_v11.py` (sub **402350**) |
| **Website PnL** | **$12,246.22** |
| **Manual bids** | **(b1=766, b2=866)** |
| **Rank** | est. top ~10% (was #615/1506 = 59 pct) |
| **BT prediction accuracy** | 99.87% ($12,262 BT → $12,246 website) |

See `BACKTEST_COMMANDS.md` for run commands. See `R3_BRIEF.md` for official spec.
See `MANUAL_R3_WRITEUP.md` for manual challenge analysis.
See `memory/project_round3_v1.md` for cross-session context and full lessons.

## v11 Architecture

```
HYDROGEL_PACK    — spread==17 GIGA SHORT (from competitor 402045)
                   When spread=17 AND mid>10010: short 200, exit at mid<9998.
                   Otherwise passive MM (v4 layered).
                   Day 2 1k-tick contribution: $10,264

VELVETFRUIT_EXTRACT — Wall Mid MM (P3-winner technique)
                   Fair = midpoint of HIGHEST-VOLUME bid/ask levels (not best±).
                   Plain MM with pos-aggression at |pos|>100.
                   Day 2 1k-tick contribution: $1,855

VEV_4000-6500    — Layered voucher trading
                   - BS taking (BS_EDGE=10, adaptive sigma rolling IV median)
                   - Intrinsic arb (loose for 4000/4500, strict elsewhere)
                   - Passive MM on 5000-5400 (post at best±1)
                   - Call-spread arb scanner (insurance, never fires)
                   Day 2 1k-tick contribution: +$127 net
```

## Active Strategy Files

| File | 1k day 2 BT | 10k 3-day | Notes |
|---|---:|---:|---|
| `r3_v1.py` | $1,013 | $28,013 | Pure MM baseline |
| `r3_v3.py` | $1,013 | $28,013 | + structural arb. Submitted as **383883 → $1,177** |
| `r3_v7.py` | $2,538 | $47,388 | **Wall Mid for VFE breakthrough** (+$19k 3-day) |
| `r3_v9.py` | $2,660 | $47,318 | + safe BS voucher taking. Submitted as **401608 → $2,636** |
| `r3_v10.py` | $5,142 | $46,970 | + 401389 HP day-type detection |
| **`r3_v11.py`** | **$12,262** | **$46,976** | **+ 402045 spread=17 GIGA SHORT. Submitted as 402350 → $12,246 ★** |

Archived experimental versions in `archive/`. Failed v2/v4/v5/v6/v8 in `archive/failed_experiments/`.

## R3 Submission History

| Sub | Strategy | Website PnL |
|---|---|---:|
| 383883 | r3_v3 | $1,177 |
| 384367 | god_logger_r3 | $0 (logger) |
| 400463 | r3_v8 (BS voucher fragile) | $1,732 |
| 401608 | r3_v9 | $2,636 |
| **402350** | **r3_v11** | **$12,246** ★ |

Run logs at `run-logs/round-3/<id>.zip`.

## Directory Map

```
trader-logic/round-3/
├── r3_v1, v3, v7, v9, v10, v11.py        # Active strategies (chronological)
├── archive/                               # Iterations & failed experiments
│   ├── README.md
│   ├── v1_iterations/                     # v1a-v1e
│   ├── failed_experiments/                # v2, v2b, v4, v5, v6, v8
│   └── superseded/                        # v3_theta
│
├── manual_r3_solver.py                    # Nash + grid search (recommends 766, 866)
├── notes/
│   ├── voucher_analysis.py + .txt         # 8-part EDA
│   ├── iv_visualization.py + iv_plots/    # 4 PNGs
│   ├── recalibration_1k.md
│   └── alpha_hunt.py + .txt
│
├── intel/
│   ├── image.png                          # Top-trader $80k chart screenshot
│   └── competitor_strategies/             # Discord-shared scripts
│       ├── 392245.py (BS voucher fragile)
│       ├── 401389.py (HP day-type detection)
│       ├── 401608.py (= our r3_v9)
│       ├── 402045.py (★ HP spread=17 GIGA SHORT)
│       └── 400463.py (= our r3_v8)
│
├── oracle/god_logger_r3.py                # Pristine market state logger
│
├── R3_BRIEF.md                            # Official wiki brief (verbatim)
├── R3_EXPLAINED.md                        # Round explanation
├── BACKTEST_COMMANDS.md                   # ★ Team reference
├── MANUAL_R3_WRITEUP.md                   # Two-bid auction analysis
├── README.md                              # This file
└── POST_MORTEM_402350.md                  # (TBD if needed)
```

## Key Learnings (durable)

1. **Wall Mid > simple mid** — every 2nd-place P1/P2/P3 team uses Wall Mid. +$19k 3-day on R3 VFE.
2. **Discord competitor mining** — single biggest win. Porting 402045's spread=17 trigger added +$9.6k 1k-tick day 2.
3. **Verify BT calibration** — `BT × 0.99 ≈ website` held twice. Check before submitting.
4. **Avoid hardcoded TARGET arrays** — overfit to specific path, fragile for final scoring.
5. **stdout NOT captured** — diagnostic loggers must use traderData JSON.
6. **Aggressive take usually loses** — MM bot quotes are AT fair, paying above is adversely selected.
7. **Spread > signal** — directional voucher signals (OBI, VR(20)) all defeated by $20 spread cost.

See `memory/project_round3_v1.md` for the complete lessons archive.
