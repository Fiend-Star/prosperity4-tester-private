# Round 3 Manual Challenge — Celestial Gardeners' Guild

## Problem

Submit two integer bids `b1 <= b2` in `[670, 920]`. Each counterparty has an IID reserve `r` uniform on the 51-value discrete set `{670, 675, ..., 915, 920}`. Sell price next day = 920.

**Trade rules:**
1. If `r < b1`: both bids exceed → they take the *lower* → profit `920 - b1`.
2. Elif `r < b2`: only `b2` exceeds → trade at `b2`, with global-mean check:
   - If `b2 > mean_b2`: profit `920 - b2`.
   - If `b2 <= mean_b2`: effective profit = `(920 - mean_b2)**3 / (920 - b2)**2` (convex penalty).
3. Else: no trade.

`mean_b2` is the mean of all players' second bids — endogenous, so this is a game.

## Solver

`manual_r3_solver.py` computes:
- **Best-response grid**: integer `(b1, b2)` with `b1 <= b2`, both in `[670, 920]`, maximizing `EV(b1, b2, mu) = (1/51) * sum_r profit(b1, b2, r, mu)`.
- **Nash fixed-point**: symmetric equilibrium via damped iteration `mu := 0.5*mu + 0.5*b2_best(mu)`.
- **Robust grid**: max expected EV over `mu ~ N(mu_star, mu_std^2)` for various `mu_std`.
- **Candidate comparison**: EV table across scenarios for several pair choices.

## Key Finding — Multiple Nash Equilibria

Fixed-point iteration converges to different stable points depending on seed:

| Seed | Equilibrium `(b1, b2)` | EV at `mu*` |
|---|---|---|
| 800 | `(751, 836)` | 84.33 |
| 850 | `(756, 851)` | 83.59 |
| 870 | `(766, 871)` | 80.57 |
| 890 | `(776, 891)` | 75.20 |

Any of these is self-consistent: "if everyone bids b2, the best response is b2". The actual realized `mu` depends on player coordination, which is uncertain.

## Candidate EV Table

EV per counterparty at various realized `mu`:

| Pair | mu=830 | mu=850 | mu=855 | mu=860 | mu=865 | mu=870 | mu=880 |
|---|---|---|---|---|---|---|---|
| `(756, 851)` — Nash(850) | 83.59 | 83.59 | 79.37 | 74.78 | 70.90 | 67.66 | 62.89 |
| `(761, 856)` — UI default | 83.08 | 83.08 | 83.08 | 78.88 | 74.37 | 70.60 | 65.06 |
| **`(766, 866)` — Robust(850,10)** | **81.57** | **81.57** | **81.57** | **81.57** | **81.57** | **77.20** | **69.00** |
| `(770, 871)` — Safe high | 79.00 | 79.00 | 79.00 | 79.00 | 79.00 | 79.00 | 69.80 |
| `(751, 836)` — Nash(836) | 84.33 | 72.54 | 69.31 | 66.54 | 64.19 | 62.24 | 59.36 |

## Three-agent synthesis (2026-04-25)

After exhaustive analysis by quant-finance (game theory), competitive-programming (exhaustive search), and ml-research (behavioral posterior) specialists, the converged answer is below. Worker artifacts at `manual_r3_deep.py`, `manual_exhaustive/`, and the leaderboard mining results.

### Posterior on `avg_b2` (the endogenous mean)

Empirical-Bayesian posterior built from R1+R2 leaderboards (44k team-rows, 4,021 R3-eligible) plus a 14-bucket behavioral model:

```
P(avg_b2) = 0.80 · N(858.94, 4.0)   "base"
          + 0.15 · N(866.0, 4.0)    "Discord-focal at 866 goes viral"
          + 0.05 · N(871.0, 4.0)    "Discord-focal at 871 goes viral"
```

Mixture mean = **860.6**, SD = **5.5**, 95% CI ≈ [851, 870]. The 200k gate filtered out the bottom 82% of R1 entrants — surviving field is sophisticated, but bucket-fraction uncertainty (Dirichlet α=10) gives σ ≈ 4 even with N=4,021 averaging.

### Per-μ structure (key finding)

EV is **piecewise constant** with sharp jumps at each reserve crossing:
- For `b2 > μ` (no penalty): `EV = (1/51)·[N1·(920−b1) + N2·(920−b2)]` — depends only on N1/N2 partitioning of 51 reserves.
- For `b2 ≤ μ` (penalty): convex `(920−μ)³/(920−b2)²` term, dominated by no-penalty branch in expectation.
- **Each +5 to b2 sacrifices ~1.0 EV/cp but extends the flat region by 5.**
- **Each +0.01 to b1 (just past a reserve) captures +1.96 EV** if it crosses a reserve.

### EV decision matrix under realistic posterior (σ≈4 mixture)

| Pair | E[EV] | Best-case | Worst-case (95%) | P(cliff) | Type |
|---|---:|---:|---:|---:|---|
| `(760.01, 860.01)` | ~78.5 | 83.14 | 65 | **~39%** | Aggressive — too cliff-exposed |
| `(761, 861)` integer | ~79.5 | 82.37 | 70 | ~32% | Tight-prior optimum |
| **`(765.01, 865.01)`** | **~81.5** | **82.35** | 73 | ~12% | **Best fractional + safety** |
| **`(766, 866)`** | **80.99** | **81.57** | 77.20 | ~9% | **Best integer (3-agent consensus)** |
| `(771, 871)` | 80.45 | 80.57 | 80.57 | ~2% | Pareto-immune flat |
| `(771, 876)` | 79.46 | 79.47 | 79.47 | <1% | Over-cushioned |

### Recommendation (decision tree)

**Primary submission depends on whether the UI accepts non-integer bids:**

```
Does the UI accept fractional bids (e.g., 765.01)?
├── YES → Submit (b1, b2) = (765.01, 865.01)
│         E[EV] ≈ 82.35 in ~93% of posterior, ~81.5 expected
│         +0.5 EV/cp over (766, 866) ≈ +$500 on N=1000
│         +0.78 EV/cp in 70% modal scenario
│
└── NO  → Submit (b1, b2) = (766, 866)
          E[EV] ≈ 80.99 expected, 81.57 in flat zone
          Robust to ±50% bucket misspecification
          Wins under quant-finance meta + ml posterior + bimodal stress
```

R2 leaderboard had non-integer entries (34.01, 42.1, 61.1) — likely the form accepts fractionals, but verify before round close.

### Why each alternative loses

- **(760.01, 860.01)**: peak EV 83.14 but 39% cliff probability under realistic σ=4. Expected drops to ~78.5.
- **(761, 861) integer**: same — wins +0.80 if μ≤861, loses ~6 EV if μ ∈ [862, 870] (32% mass).
- **(771, 871)**: only beats (766, 866) if μ > 866.9. P(μ > 866.9) ≈ 23%. Expected loss vs (766, 866) ≈ $0.54/cp. Insurance not worth it.
- **(776, 881) "minimax"**: pays $2.81/cp for tail prob ~5%. Bad Kelly trade.
- **`(751, 836)` Nash(836)**: collapses at μ > 840.

### Two non-obvious findings

1. **Penalty-branch lever**: bidding `b2 = μ−1` gives slightly *higher* payoff than `b2 = μ+1` because `(920−μ)³/(920−b2)² > (920−μ)`. But under σ=4 you can't bet on it — explains why `(761, 856)` "almost works" as a deliberate penalty-side bid.

2. **Fractional-bid kink**: EV jumps by ~+1.96 every time b1 crosses a reserve from above. So `b1 = 765.01` (just past the 765 reserve) captures all 20 below-reserves at the high price. This is the entire +0.78 fractional advantage over (766, 866).

### Validation: 289-team R2 cluster

The ml-research agent found **289 R2 teams played `(23, 77, 0)` exactly** — the strongest single piece of evidence for an "extreme rank-interpretation" bucket. R3 analog: ~5-7% of survivors play conservative-low b2 (≤836). Consistent with bucket model.

### Submission

```
PRIMARY (if fractional accepted):  Lowest Bid: 765.01,  Highest Bid: 865.01
FALLBACK (integer only):           Lowest Bid: 766,      Highest Bid: 866
```

Test the UI form for fractional acceptance before round close. If the form silently rounds, both reduce to (766, 866). Do NOT enter (765, 865) as fallback — that fails to capture the 765 reserve. Re-submittable until round end.
