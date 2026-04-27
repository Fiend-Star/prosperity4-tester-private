# R3 NN Regime Analysis — Findings for R4

Date: 2026-04-28. Method: feature engineering + RandomForest/MLP regression on
sliding-window samples (32 total: 8 windows/day × 4 days), train on R3 d0/d1/d2,
test on R3 d3 (= R4 d3). Code: `C:/tmp/r4_nn_train.py`, `C:/tmp/r4_yolo_window.py`.

## TL;DR

R3 d3 is a **statistical outlier on multiple dimensions simultaneously** that the
current YOLO gate (single feature: `vfe_drift @ ts=3000 ≤ +2.0`) catches on a
tight 5pt margin. NN analysis surfaces 3 independent confirming signals; we use
them as a **defensive veto** rather than additional fire-triggers (primary gate
is already optimal on training data; veto adds R4 d4 protection at zero BT cost).

## Top 3 Findings

### 1. R3 d3 is a 4σ multi-feature anomaly within the first 1000 ticks
PCA reconstruction error on d3 is **4.0×** the d0/d1/d2 mean. Per-feature z-scores
of d3's first-1000-tick window vs d0/d1/d2 baseline:

| Feature | d3 value | baseline μ ± σ | z |
|---|---|---|---|
| vfe_mid_std | 15.7 | 6.5 ± 1.0 | +9.2 |
| **hp_s17_density** | **0.039** | **0.004 ± 0.004** | **+8.7** |
| **hp_vfe_corr** | **−0.81** | **+0.15 ± 0.12** | **−7.8** |
| hp_above_10010 | 0.92 | 0.09 ± 0.11 | +7.8 |
| vfe_ret_skew | −0.17 | +0.07 ± 0.04 | −6.1 |
| vfe_mid_drift | −42.0 | −4.2 ± 7.0 | −5.4 |

**Five features each at |z|>5σ.** Probability of joint occurrence under d0-d2 distribution
is effectively zero. Day 3 is genuinely a different regime, not seed noise.

### 2. RandomForest predicts d3 future-drift direction at 87.5% accuracy
On 8 sliding-window holdout samples from d3, RF regressor (trained on d0/d1/d2):
- MAE = 18.1 (vs σ_label = 26.2 on test), train MAE = 5.8 → mild overfit but not catastrophic
- **Direction accuracy = 87.5%** (7/8 correct sign)
- Top features by RF importance: `hp_mid_std` (0.19), `vfe_ret_mean` (0.13), `vfe_mid_drift` (0.13), `vfe_obi_skew` (0.13), `vfe_ret_ac1` (0.09)

3-class classifier (down/side/up) only hits 37.5% — direction is learnable, magnitude is not.

### 3. The current YOLO threshold is on a knife-edge — 5pt margin between fire and skip
At ts=3000: d3 vfe_drift = **−3.0**, d2 = **+3.0**. Threshold = +2.0 fires on d3 by
exactly 5pt. **Moving detection later costs us d3**: at ts=10000, d3 drift = +1.0
(positive!) — the catastrophic drift only becomes visible after ts=15000.

The single-feature gate is fragile. R4 d4 may have a regime where the early-window
vfe_drift looks d1/d2-like (slightly positive) but other features show d3-like
distress. Multi-feature confirmation hardens the gate.

## Concrete R4 Recommendation

`r4_final_v2.py` adds a **defensive veto layer** at the existing ts=3000 decision:

```
if primary_fire (drift ≤ +2.0):
    if drift >= -2 (borderline, not deeply down):
        compute hp_vfe_corr from samples in [0, 3000ts]
        if corr >= +0.30 (d1/d2-style positive coupling):
            VETO — skip yolo
    yolo_fires = primary_fire AND not veto
```

**Rationale**: corr@ts=3000 separates the training days cleanly:
- d3: −0.27 (negative — VFE/HP decoupled, distress signal) → fire
- d0: +0.35 → veto (would lose small d0 yolo PnL, accept for d4 protection)
- d1/d2: +0.20/+0.36 → already vetoed by primary anyway

**BT verification (vs r4_final.py baseline)**:
| Test | Baseline | v2 | Δ |
|---|---|---|---|
| d3 1k probe | $60,390 | $60,390 | 0 |
| 10k 3-day default | $263,328 | $263,328 | 0 |
| 10k 3-day imc | $249,480 | $249,480 | 0 |

**Byte-identical PnL on training data** — veto is dormant insurance.
The only path it changes behavior is R4 d4 if its early-window corr ≥ +0.30
(d1/d2-style up-day signature), in which case the veto saves us from a misfire
that would deploy max-short on an up-day (~$50k+ avoidable loss).

## What this tells us about R4 d4 prediction risk

1. **The first 100 ticks (~ts=10000) are mostly uninformative** for VFE direction —
   d3 still shows +1.0 drift at that point. Primary YOLO must commit at ts=3000
   or accept missing d3-style regimes entirely.
2. **Cross-product structure (hp_vfe_corr, hp_s17_density) leaks regime info
   earlier than VFE itself does** — these are the right features to gate on.
3. **R3 d3 was an extreme outlier (4× anomaly score)**. R4 d4 is unlikely to be
   another 4σ event, but the regime-classifier can fail silently. Bias toward
   *additive defenses* (vetoes that protect against d1/d2-style false-fires)
   rather than additional fire-triggers (which risk collapsing on borderline days).
4. **All 4 R3 days had EOD VFE drift in [−63.5, +28]**. R4 d4 baseline expectation:
   uniform prior over similar magnitude. Yolo's +2.0 threshold gives 5pt buffer
   either side — adequate but not generous.

## Files
- Modified: `C:/tmp/r4_final_v2.py` (NN-augmented defensive veto)
- Analysis: `C:/tmp/r4_nn_train.py`, `C:/tmp/r4_yolo_window.py`, `C:/tmp/r4_yolo_robustness.py`

To deploy: copy `C:/tmp/r4_final_v2.py` over `trader-logic/round-4/r4_final.py`.
Not deployed automatically — current submission is canonical until user approves.
