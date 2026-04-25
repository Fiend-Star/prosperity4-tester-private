# Phase 1 Results

## Phase 1.1: Multi-level passive posting (r3_v12.py)

**Status:** ⚠ Marginal — failed +$500/day threshold

| Metric | v11 baseline | v12 | Δ |
|---|---:|---:|---:|
| 1k-tick day 2 | $12,262 | $12,262 | **$0** |
| 10k 3-day total | $46,976 | $47,036 | **+$60** |
| Day 0 | 24,989 | 24,973 | -$16 |
| Day 1 | 5,996 | 6,118 | +$122 |
| Day 2 (10k) | 15,990 | 15,946 | -$44 |

**Why marginal vs alpha_hunt's +$11k projection:**
- alpha_hunt Q2 measured single-level vs multi-level on a clean ceiling-comparison baseline, NOT against r3_v11's specific architecture.
- r3_v11 already saturates passive fills at single-level (VFE + voucher MM).
- Multi-level splits limited capacity (V_VOUCHER_MM_SIZE=20) across 3 layers (8/6/6); deeper layers rarely fill on 1k-tick windows.
- VFE Wall Mid MM with full 200-unit capacity DID gain marginally on day 1 (+$122), suggesting deeper layers occasionally fill on 10k windows.

**Decision:** Keep r3_v12 (non-regressive on 10k 3-day) but do not submit. Pivot to Phase 2 (day-type detector) which has 100x higher EV.

**Files:**
- `trader-logic/round-3/r3_v12.py` — multi-level VFE + voucher posting (v11 + Phase 1.1)
