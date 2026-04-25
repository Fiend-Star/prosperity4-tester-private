# R3 1k-Tick BT Recalibration

## Context

Discovery from analysis of god logger submission (384367.zip):
**Website tests run 1,000 ticks per day, NOT 10,000.**

- Website timestamps: 0 → 99,900 (step 100) = 1,000 ticks total
- Our BT default: 0 → 999,900 (step 100) = 10,000 ticks total
- Website runs 10% of the data we calibrate against

This explained the apparent r3_v3 underperformance (1,177 website vs 28,013 BT — actually 1,177 vs 2,500 day-2-1k = 47% website ratio, matching R1 calibration).

## 1k-tick BT comparison (day 2)

All strategies produce identical $1,013 at 1k ticks:

| Strategy | 1k-tick BT day 2 | 10k-tick BT day 2 | Notes |
|---|---:|---:|---|
| r3_v1 | $1,013 | $2,500 | Pure MM baseline |
| r3_v3 | $1,013 | $2,500 | + structural arb (never fires) |
| r3_v3_theta | $1,013 | $2,500 | + terminal theta (only kicks in t > 900k) |
| r3_v4 | $1,013 | $2,500 | + size scale-up + OBI bias (disabled) |

Per-product breakdown (1k ticks):
- HYDROGEL_PACK: $606
- VELVETFRUIT_EXTRACT: $415
- VEV_5400: -$10
- VEV_5300: +$2
- All other vouchers: $0 (no fills in first 1k ticks)

**Conclusion:** at 1k-tick resolution, all strategies converge. No version-specific alpha emerges within 100k timestamps.

## Website vs BT comparison

| Source | Day 2 PnL (1k ticks) | Ratio to BT |
|---|---:|---:|
| BT default mode | $1,013 | 1.00x baseline |
| BT imc mode | -$170 | -0.17x (calibration off) |
| Website (383883, r3_v3) | $1,177 | 1.16x |

**Key finding:** website is 16% HIGHER than BT default mode at 1k ticks. Opposite of R1 pattern (BT > website by 30-56%). Explanations:
1. R3 random taker directions favor us on day 2's 1k-tick window
2. Match-mode default with R3 data has slight under-fill bias
3. The 16% gap is within seed/path noise

## Implications

1. **r3_v3 is the right submission.** No version dominates at 1k-tick scale.
2. **For final scoring (10k ticks)**, expected website PnL ≈ $2.5k × (1.18 ratio) × 3 days = ~$8.85k
   - Actually unknown if final uses 10k or 1k. R0/R1 used 10k for final. Assume same here.
3. **`imc` mode needs R3-specific calibration.** R2's extra_rate=0.038 is wrong for R3. Defer until more website results gathered.

## Recommendation

Submit **r3_v3.py** as final algorithmic strategy.  
Submit manual bids **(b1=766, b2=866)**.

No further iteration on the algorithmic side warranted given:
- All version variants converge at 1k-tick BT
- EDA shows market is efficient (0 butterfly/call-spread executable arbs)
- Quant-finance theoretical alpha sources don't survive spread costs
- IV surface trading consistently underperforms simple MM
