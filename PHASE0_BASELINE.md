# Phase 0 Baseline (r3_v11.py)

Frozen 2026-04-25. All Phase 1+ changes are evaluated as Δ vs these numbers.

## 1k-tick day 2 (website-parity test)

**Total: $12,262** (predicts website ≈ $12,139 via × 0.99 ratio; actual website was $12,246)

| Product | PnL |
|---|---:|
| HYDROGEL_PACK | 10,224 |
| VELVETFRUIT_EXTRACT | 1,940 |
| VEV_5300 | 136 |
| VEV_5200 | -28 |
| VEV_5400 | -10 |
| Other vouchers | 0 |

## 10k 3-day (regression check)

**Total: $46,976**

| Day | Total |
|---|---:|
| Day 0 | 24,989 |
| Day 1 | 5,996 |
| Day 2 | 15,990 |

## Acceptance criteria for Phase 1+ changes

- 1k-tick day 2: Δ ≥ +500 (target post-fix BT > $12,762)
- 10k 3-day: non-regression (no day < 80% of baseline)
- Synthetic regime sweep (when added): ≥ 11/13 non-negative

## Commands used

```bash
cd C:/Users/gurms/PycharmProjects/imc-prosperity-4-backtester/.worktrees/r4-prep
PYTHONPATH=prosperity4bt python -m prosperity4bt trader-logic/round-3/r3_v11.py 3-2 --ticks 1000 --no-out --no-progress
PYTHONPATH=prosperity4bt python -m prosperity4bt trader-logic/round-3/r3_v11.py 3 --ticks 10000 --no-out --no-progress
```

Note: R3 uses `--match-mode default`, NOT `imc` (imc is R2-calibrated, gives -$170 instead of $1,013 on R3 day 2). Plan's Phase 0 referred to imc; we corrected to default per R3 BACKTEST_COMMANDS.md guidance.
