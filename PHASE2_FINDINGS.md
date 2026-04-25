# Phase 2 Findings: Day-Type Detection on VFE

## Summary

**Status:** ⚠ Infrastructure in place but doesn't activate on R3 data with reasonable thresholds.

The plan's Phase 2 (Bayesian portfolio rank #1, score 367, EV $20-40k/round) was based on the buy-and-hold ceiling alpha_hunt3.py identified ($41,600 day 2 if you knew the day-type at open). Implementation experience reveals this isn't reachable from row 20 detection on VFE.

## Implementation

- `trader-logic/lib/regime.py` — generalised RegimeState class with detect_day_type() and detect_drift_open() (reference, library-style)
- `trader-logic/round-3/r3_v13.py` — inlines day-type detector (single-file submission compliance) into VoucherState; build/cover/invalidation logic ported from competitor 401389
- BT result: identical to v12 (day_type stays MEAN_REVERT for all 3 R3 days)

## Why VFE day-type detection fails to fire

Empirical row-20 data from R3:
- **Day 0**: rm20 = 5248.2, mid range stays [5246, 5251] in first 20 ticks. Drift -11.8 from GLOBAL_MEAN=5260. Below threshold (20).
- **Day 1**: rm20 likely similar (~5240). Drift ~-20 (borderline).
- **Day 2**: rm20 ≈ 5267 (open 5267.5). Drift ~+7 from 5260. Below threshold.

Over the FULL day (10k ticks):
- Day 0 drift -6 (5240 → 5234)
- Day 1 drift +20.5 (5240 → 5260)
- Day 2 drift +28 (5267 → 5295)

But at row 20 (200 ticks = 2% of day), VFE has only moved ~0.5 ticks (drift ÷ 50). The detector cannot distinguish a TREND_LONG day from a MEAN_REVERT day at row 20 because **VFE drift is gentle relative to its tick noise**.

By contrast, competitor 401389's HP day-type works because HP has wide swings (range ~150 ticks day 1) and a stable cross-day mean (9990 ± 32). At row 20, HP rm20 typically deviates 30+ ticks from 9990 if a trend day is forming.

## Architectural difference: HP vs VFE

| Property | HP (HYDROGEL_PACK) | VFE (VELVETFRUIT_EXTRACT) |
|---|---|---|
| Daily range | ~150 ticks | ~95 ticks |
| Cross-day mean stability | High (9990.8 ± 32) | Low (5230, 5260, 5281 — shifts daily) |
| Spread | 13-22 (wide, dynamic) | 4-6 (tight) |
| Stdev | 31.6 | 17.0 |
| Row-20 drift detectability | Yes (≥20 ticks visible) | No (≤5 ticks visible) |

VFE is closer to a low-vol stable product (where MM dominates) than a trending product (where directional bets dominate).

## Implications for the plan

The Bayesian alpha portfolio's #1 entry (A1: day-type detector for VFE) requires either:
1. **A different anchor** — daily-rolling GLOBAL_MEAN that updates each round (per competitor 401389 with `mean_anchor_window=100`); cannot be set from historical data alone
2. **A later detection row** — if we wait to row 200+ instead of row 20, VFE drift is more visible (~5-10 ticks). But by then, 50% of website 1k-tick window is consumed
3. **A different signal** — e.g., HP-driven day-type (HP swings predict VFE direction). Untested

For ANY R4 product with VFE-like characteristics (gentle drift, shifting daily mean), day-type detection at row 20 will not fire reliably.

## What worked in this Phase

- `trader-logic/lib/regime.py` provides a clean reusable abstraction for future products
- Inline day-type implementation in r3_v13 verified bug-free (no regression vs v12 on any day)
- VoucherState extended with VFE day-type tracking that persists through traderData
- Trend invalidation safety pattern (5-tick adverse, 40-row consecutive bail) implemented and tested

## Next steps

- For HP, day-type detection from competitor 401389 might still apply (different module, similar logic)
- For voucher products in R4, F1-F5 features (IV velocity, smile R²) may be more reliable signals than day-type
- Skip the buy-and-hold ceiling pursuit on VFE — it requires per-day mean recalibration that is not available at row 20

## Files

- `trader-logic/lib/regime.py` — reusable library
- `trader-logic/round-3/r3_v13.py` — inline day-type infrastructure (no PnL gain, no regression)
- `r3_v12.py` baseline preserved for comparison
