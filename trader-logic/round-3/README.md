# Round 3 — Gloves Off

## Summary

**Submission: `r3_v3.py`** (if structural arb ever fires on live data) / fallback **`r3_v1.py`** (proven +28k BT)
- 3-day BT: **+28,013** (Day 0 +13,617 | Day 1 +11,896 | Day 2 +2,500) — both v1 and v3 identical in BT
- Per product:
  - HYDROGEL_PACK: +23,247 (MM spread capture, weak on day 2)
  - VELVETFRUIT_EXTRACT: +512 net (swings +3.6k / -2.6k / -0.6k)
  - Vouchers (spread-capture MM + intrinsic arb): +4,253

## Strategy

| Component | Products | Approach |
|---|---|---|
| Delta-1 MM | HYDROGEL_PACK, VELVETFRUIT_EXTRACT | Plain mid + pos-aggression at 50% limit + post at best±1 |
| Intrinsic arb | VEV_4000, VEV_4500 | Take if mid < spot−K−2 or > spot−K+2 (deep ITM) |
| Voucher MM | VEV_5000..VEV_5400 | Post at best_bid+1 / best_ask−1, size 20 |
| Skipped | VEV_5500, VEV_6000, VEV_6500 | Thin (spread=1) or penny-pegged (mid=0.5) |

**Key calibration decision:** Pure mid (NOT microprice) for fair value. Microprice volatility on tight-spread products (VE spread=5) caused spurious crossing takes. Switching to mid: +$8.3k on 3-day BT.

## Files

- `r3_v1.py` — **PROVEN BASELINE** (+28,013 BT). Pure MM + intrinsic arb on 4000/4500, no Black-Scholes.
- `r3_v3.py` — **v3 SUBMISSION CANDIDATE**. v1 + strict intrinsic arb on all 10 strikes + call-spread arb scanner on all 45 pairs + vol-scaled HYDROGEL_PACK MM. **Identical BT PnL to v1** (arbs don't fire on BT data — insurance for live).
- `r3_v3_theta.py` — A/B variant with terminal theta harvest. No effect in BT (may help on website if round-end liquidation uses intrinsic/BS-theoretical).
- `r3_v4.py` — v3 + EDA-driven attempts (OBI predictor, size scale-up). All disabled — both add no value or destroyed PnL. Final architecture identical to v3 (+28k BT).
- `notes/voucher_analysis.py` — Exhaustive EDA script (8 parts: dynamics, IV, smile, no-arb, cross-product, taker flow, regimes, deep-ITM TV).
- `notes/voucher_analysis_output.txt` — EDA output (~320 lines).
- `r3_v1a..r3_v1e.py` — v1 iteration history.
- `r3_v2.py`, `r3_v2b.py` — v2 IV surface experiments. Underperform v1 by $1.6k / $7.7k — abandoned.
- `manual_r3_solver.py` — Nash solver with cycle detection.
- `MANUAL_R3_WRITEUP.md` — Manual analysis; **submit (766, 866)**.
- `notes/day0_eda.py` — Product classification (random-walk profile).

## Running

```bash
cd C:/Users/gurms/PycharmProjects/imc-prosperity-4-backtester
PYTHONPATH=prosperity4bt python -m prosperity4bt trader-logic/round-3/r3_v1.py 3-0 --ticks 10000 --no-out
# Days 3-1, 3-2 for other historical days
# For submission day: same file — r3_v1.py doesn't use TTE config, purely MM-based.
```

## Why v2 Underperforms (and What to Try Next)

v2 adds a Black-Scholes implied-vol surface across tradeable strikes and trades z-score outliers. On BT it consistently loses money vs v1:

| Version | Day 0 | Day 1 | Day 2 | Total |
|---|---:|---:|---:|---:|
| v1 (MM only) | 13,617 | 11,896 | 2,500 | **28,013** |
| v2 (quadratic z=3.0) | 14,562 | 10,592 | 1,240 | 26,394 |
| v2b (linear z=2.5) | 13,712 | 10,196 | -3,579 | 20,329 |

Hypotheses for why IV-surface trading fails in BT:
1. **Residuals aren't mean-reverting** on 100-200 tick windows; smile itself drifts.
2. **Adverse selection on z-score fills**: market MM has same BS info and picks us off on genuine mispricings.
3. **VEV_5200 (near-ATM) dominates losses on day 2** (-$3k in v2b) — possibly a single regime shift.

Things to try for v3+:
- Intraday rolling regression rather than EWMA smile (catch regime changes).
- Trade only ITM arbitrage (no IV timing) + underlying delta-hedge.
- Portfolio-level vega neutrality instead of per-strike.
- Use raw strikes (no log-moneyness transform) for fit — simpler, maybe more robust.
- Calibrate `imc` mode after first website submission before re-testing v2.

## Open Items

- [ ] Submit **r3_v3** (or r3_v1 as safer fallback) to website, record per-product PnL.
- [ ] Calibrate `imc` mode `extra_rate` from v3 website result (CSV != website; see `memory/feedback_backtester.md`).
- [ ] Investigate HYDROGEL_PACK day 2 weakness (-116) — vol-scaled MM didn't help in BT (spread=16 is wide enough that post is always best±1 regardless of slack).
- [ ] After website feedback: if v3 structural arbs fire often, tune ARB_SAFETY_MARGIN and sizes.
- [ ] Submit manual challenge bids **(766, 866)** via UI.

## EDA Findings (2026-04-25)

Comprehensive 8-part EDA (`notes/voucher_analysis.py`):

**Confirmed alpha sources** (already in v1/v3):
- Spread-capture MM on 5000-5400 (+$4k 3-day BT)
- Intrinsic arb on VEV_4000/4500 (+$362, 73-83 executable arbs/day)

**Refuted theoretical claim**: quant-finance agent said "AR1(IV) ≈ 0.98, half-life > 200 ticks". **Data shows AR1(ΔIV) ≈ -0.5 universally with half-life 0-30 ticks** — IV mean-reverts at 1-30 tick scale, not 200+. v2's 100-tick window was 30× too slow.

**Tried but failed**:
- **OBI predictor on VEV_4000/4500** (β=0.30/-0.29, t-stat 8-11, R²~1%): real signal but spread=20 exceeds expected per-trade gain. Aggressive entry+exit lost -$394k in BT.
- **Size scale-up on VEV_5300/5400**: no effect — fills are taker-flow-limited, our quote depth doesn't matter.
- **VEV_5500 enabling**: spread=1 means posting at best+1 crosses the book → -$124k loss.
- **Faster IV mean-reversion (1-3 tick window)**: signal magnitude too small vs spread costs.

**Key insight**: The R3 BT data has alpha CEILING ~+28k. Markets are efficient enough that simple MM captures essentially all available edge. v1/v3/v4 all converge to the same PnL.

**Significant but unexploited**:
- All products show VR(20) = 0.4-0.8 (mean-reversion at 20-tick scale, NOT random walk)
- Smile R² degrades day 0→2: 0.81 → 0.42 (smile fits get worse)
- VEV_5400/5500 show -13% to -26% intraday drift (theta decay observable). Short-OTM strategy possible but high variance — not deployed.

## v3 Post-Mortem: What We Tried

Based on 4-agent synthesis (quant-finance, explore, code-review, data-mining-plan):

**Worked:**
- Call-spread arb scanner (insurance, no BT fires)
- Strict intrinsic arb bounds on all 10 strikes (hybrid: loose for 4000/4500, strict for others)
- Nash solver cycle detection

**Didn't help in BT:**
- Vol-scaled HYDROGEL_PACK posting (spread=16 too wide for slack to matter)
- Terminal theta harvest (no effect; depends on liquidation mechanism)
- Expanded intrinsic arb with v1's loose rule (CAUSED −$46k losses on near-ATM strikes — replaced with strict bounds)

**Key learning:** The v1 intrinsic arb sell rule `bid > intrinsic + edge` is a TV-assumption bet, not strict arb. Safe for deep ITM (TV ≤ edge), catastrophic for near-ATM (TV ≫ edge). Strict `bid > spot` never fires but is theoretically sound.

## TTE Configuration

`r3_v1.py` doesn't use Black-Scholes so TTE is irrelevant.

`r3_v2.py` / `r3_v2b.py` use `TTE_DAYS_AT_START` module constant:
- Historical day 0: `TTE_DAYS_AT_START = 8.0`
- Historical day 1: `TTE_DAYS_AT_START = 7.0`
- Historical day 2: `TTE_DAYS_AT_START = 6.0`
- Submission: `TTE_DAYS_AT_START = 5.0`
