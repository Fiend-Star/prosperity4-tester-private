# Round 3 — Gloves Off

## Summary

**SUBMISSION: `r3_v9.py`** — v7 base + safe BS voucher taking (BS_EDGE=10, adaptive sigma via rolling IV median)
- **3-day BT: +$47,318** (Day 0 +17,238 | Day 1 +16,006 | Day 2 +14,075) — essentially tied with v7
- **1k-tick day 0: +$2,074** vs v7 $1,006 (+106%)
- **1k-tick day 2: +$2,596** vs v7 $2,538 (+2%)
- Expected leaderboard rank: top ~25% (vs current 59th percentile at $1,177)

Previous best: `r3_v7.py` ($47,388 3-day, $2,538 1k-tick day 2) — Wall Mid for VFE breakthrough
Previous submissions:
- `r3_v3.py` — fallback (+$28,013 3-day BT)
- `r3_v1.py` — original baseline (+$28,013, identical to v3 in BT)
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

## Files (Active)

- **`r3_v11.py`** — **CURRENT SUBMISSION**. 402045's spread=17 GIGA SHORT HP + v9's voucher/VFE. **1k-tick day 2 $12,262** (4.6× v9). Estimated website $12,140 → top 7-10%.
- `r3_v10.py` — 401389 HP day-type + v9 vouchers. 1k-tick day 2 $5,142.
- `r3_v9.py` — v7 + safe BS voucher taking. Submitted as 401608 → website $2,636.
- `r3_v7.py` — Wall Mid for VFE breakthrough. 10k 3-day $47k.
- `r3_v3.py` — v1 + structural arb. Submitted as 383883 → website $1,177.
- `r3_v1.py` — Original baseline pure MM. $28k 3-day.

## Archive (`archive/`)

Iteration history moved to subfolders for cleanliness:
- `archive/v1_iterations/` — v1a-v1e (microprice/inventory-skew/slack experiments)
- `archive/failed_experiments/` — v2, v2b, v4, v5, v6, v8 (lost money in BT)
- `archive/superseded/` — v3_theta (no effect)

See `archive/README.md` for details on each.
- `r3_v8.py` — v7 + BS voucher MM (fixed sigma=0.20, edge=1.6 ticks) + delta hedge. Inspired by competitor 392245.py. Day 0 1k-tick +$7k (huge gain) but DAY 2 10K -$14k (catastrophic). 3-day total $4.5k. **NOT SUBMITTED**. Same vol-regime fragility as competitor.

## v8 Lesson: Fixed-sigma BS voucher MM fails (2026-04-25)

Tested replicating competitor 392245.py's BS voucher trading. Fixed sigma=0.20 (matches our EDA mean IV across days). Edge=1.6 ticks. Position-limit aware delta hedge into VFE.

**Results**:
| Window | r3_v7 | r3_v8 | Δ |
|---|---:|---:|---:|
| 10k 3-day | **$47,388** | $4,564 | **−$42,824** |
| 1k day 0 | $1,006 | **$7,035** | +$6,029 |
| 1k day 1 | **$1,866** | -$4,792 | -$6,658 |
| 1k day 2 | **$2,538** | $1,820 | -$718 |

Day 0 looks amazing (BS captures IV mispricing on calm market) but days 1-2 explode losses (-$14k day 2 10k). **Same fragility as competitor**: BS-based voucher trading loses massively when underlying vol is non-stationary across the day. Fixed sigma doesn't help because the issue is mid-day regime shifts, not initial calibration.
- `notes/voucher_analysis.py` — Exhaustive EDA script (8 parts: dynamics, IV, smile, no-arb, cross-product, taker flow, regimes, deep-ITM TV).
- `notes/voucher_analysis_output.txt` — EDA output (~320 lines).
- `notes/iv_visualization.py` — Generates 4 IV plots (matplotlib).
- `notes/iv_plots/{smile_per_day,iv_timeseries,delta_iv_distribution,smile_residuals}.png` — Visual IV diagnostics.
- `notes/recalibration_1k.md` — 1k-tick BT comparison + website vs BT analysis.
- `R3_BRIEF.md` — Official R3 wiki brief (saved verbatim for record).
- `oracle/god_logger_r3.py` — Pristine market state logger (submitted as 384367 — confirmed stdout NOT captured by website).
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

## Backtester Score Verification (2026-04-25)

| Backtester | Source | r3_v3 score (3-day, 10k ticks) | Match |
|---|---|---:|:---:|
| Ours (Python fork of jmerle P3) | local | $28,013 (D0:13,617, D1:11,896, D2:2,500) | ✓ |
| Xeeshan85's prosperity4btx 3.0.2 | `pip install -U prosperity4btx` | **$28,013 (identical per-product)** | ✓ |
| Website test (383883) | submission | $1,177 (1k-tick day 2 only) | matches BT 1k = $1,013 × 1.16 |

Two independent backtester implementations produce **identical** PnL down to the dollar. Confirms our matching engine is correct. The $1,177 website score reflects the 10× shorter test window (1k vs 10k ticks).

## Top Trader PnL Curve Analysis (intel/image.png)

User-shared chart shows top trader PnL going **0 → ~$80,000 over 1,000 ticks** (timestamps 500-99,900). Pattern:

- Slow start (first 20% of time): drawdown to -$5k, recovery
- Mid-day acceleration (33k-40k timestamps): rapid surge +$20k
- Steady climb 40k-75k: gradual accumulation +$30k
- Late surge 75k-90k: another rapid surge to $80k
- Plateau at end: $80k with $5-10k volatility

Average gain: **~$80 per tick**.

This profile suggests **NOT** a single big directional bet — it's many small wins compounding. Most likely candidates:
1. **Aggressive MM on delta-1 products** with very high turnover (no inventory caps, capture spread on every cycle)
2. **Multi-product simultaneous MM** with full position limits (200+200+10×300 = 3400 contract capacity)
3. **Specific timing-based entry** at 33k and 75k (event detection)

Our v3 captures ~$1/tick. Top traders ~$80/tick. Need 80× more aggressive turnover or fundamentally different alpha.

## R3 Leaderboard Reality Check (2026-04-25)

Community leaderboard (1641 verified submissions, 1506 deduped):

| Rank | Score | Notes |
|---|---:|---|
| #1 | $154,335 | Recovery 14.82, MaxDD $10.4k |
| #4 | $139,812 | |
| #10 cutoff | $102,128 | |
| Median | $739 | 70.7% profitable |
| Avg | $2,268 | |
| **Our (#615)** | **$1,177** | **59.2 percentile** |

**Universal 1k-tick test confirmed** — all submissions on same window. Top traders pulling **100×+ our PnL** on identical data.

**Failed v5 hypothesis**: directional trading via VEV_4000 (delta≈1) using VR(20)=0.7 mean-reversion signal. Both MR (-$40k/day) and trend-follow (-$44k/day) lose because $20 spread on VEV_4000 ≫ signal value × position size. Top traders are NOT doing naive direction bets via vouchers.

**Unsolved**: where does the $100k alpha come from? Unknown. Candidate hypotheses for future investigation:
1. Sophisticated quote-prediction (predict MM bot's next quote, post 1 tick ahead)
2. Some specific combination of strikes/timing we haven't tested
3. A known matching engine quirk that pays off massively

## Run Log Analysis (2026-04-25)

### Submission 383883 — r3_v3 algorithmic
- Total profit: **+1,177.52** (day 2 only, 1,000 ticks)
- HYDROGEL_PACK: +610 | VELVETFRUIT_EXTRACT: +526 | VEV_5000-5200: +41 (small) | rest: 0
- XIRECS (manual): +88,759 (pre-submitted bids)
- Final positions: HP -19, VE +19, VEV_5000/5100/5200: +3 each (tiny inventory)

### Submission 384367 — god_logger_r3
- Total profit: 0 (logger doesn't trade — confirmed)
- **Critical finding: stdout NOT captured by website.** Print statements thrown away.
- ActivitiesLog confirms 1,000 ticks per day (not 10,000). 10× less data than BT.
- Order books match BT exactly at all sampled timestamps.

### Calibrated expectation
- Website day 2 (1k ticks): $1,177 ≈ BT 1k-tick $1,013 × 1.16 noise factor
- For 3-day final (if 10k each): expected ~$8-12k website PnL
- BT $28k (10k×3 days) → divide by 10x tick count → $2.8k 1k-equivalent → 3 days × ~$1.2k = $3.6k expected if final uses 1k tickeach. Likely 10k for final.

## v7 BREAKTHROUGH: Wall Mid (2026-04-25)

Discovered the **Wall Mid** insight from `imc_prosperity_playbook.md` §4:

> Wall Mid = midpoint of HIGHEST-VOLUME bid/ask levels.
> Tracks IMC's hidden fair value far more accurately than (best_bid+best_ask)/2.
> **Every 2nd-place team across all three editions used this technique.**

```python
# jmerle's reference implementation
popular_buy_price = max(buy_orders.items(), key=lambda kv: kv[1])[0]
popular_sell_price = min(sell_orders.items(), key=lambda kv: kv[1])[0]  # most-negative vol = largest size
true_value = (popular_buy_price + popular_sell_price) / 2
```

**v7 PnL impact** vs v3 baseline:

| Component | v3 | v7 | Δ |
|---|---:|---:|---:|
| VELVETFRUIT_EXTRACT day 2 (10k) | -$563 | **+$11,437** | **+$12,000** |
| VELVETFRUIT_EXTRACT 3-day (10k) | $512 | $19,888 | +$19k |
| HYDROGEL_PACK | $23,247 | $23,247 | 0 (kept plain mid — Wall Mid hurt 1k-tick) |
| Vouchers | $4,253 | $4,253 | 0 (no change) |
| **Total 3-day BT** | **$28,013** | **$47,388** | **+$19,375 (+69%)** |
| **1k-tick day 2** | **$1,013** | **$2,538** | **+$1,525 (+151%)** |

**Key finding**: Wall Mid for HYDROGEL_PACK HURTS on 1k-tick window (loses -$2k) but helps on full 10k. Used hybrid: Wall Mid for VFE only.

## Open Items

- [ ] Submit **r3_v7** (primary) or r3_v3 (safer fallback) to website, record per-product PnL.
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
