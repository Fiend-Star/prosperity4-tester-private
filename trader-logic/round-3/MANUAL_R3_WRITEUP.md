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

## Recommendation

**Primary pick: `(b1 = 766, b2 = 866)`**

Reasoning:
1. **Flat EV across the likely `mu` range**: 81.57 whenever `mu <= 865`, drops only at `mu >= 870`.
2. **Dominates UI default for `mu >= 860`**: competitors who herd on `(761, 856)` push `mu` upward via their own overbidding; `(766, 866)` sidesteps this.
3. **Better than Nash(850) for `mu >= 855`**: `(756, 851)` takes penalty hits as `mu` drifts above 851, dropping to 67 at `mu=870`. `(766, 866)` stays above 77.
4. **Better than safe-high `(770, 871)`** when `mu <= 865` (+2.57) with only a small cost when `mu = 870` (-1.80).

**Alternate pick: `(770, 871)`** — for maximum risk-aversion. EV flat at 79 up to `mu=870`. Trades ~2.5 EV for robustness against a high-coordinating player pool.

**Do NOT pick** `(751, 836)` — highest EV only if `mu <= 836`, otherwise falls off a cliff.

## Why the UI Default `(761, 856)` Isn't Our Top Pick

- Penalty factor at `b2 = 856` equals `((920-mu)/(920-856))^3`. When `mu = 856` exactly, factor = 1 (no effective penalty — EV = 83.08).
- But if *any* non-trivial fraction of the player pool overbids (e.g., risk-averse competitors picking 866+), `mu` exceeds 856 and penalty bites. EV drops to 79 at `mu=860`, 74 at `mu=865`.
- The asymmetric risk (sharp convex penalty below `mu`, flat profit above) argues for bidding slightly above consensus.

## Submission

```
Lowest Bid:  766
Highest Bid: 866
```

Can be re-submitted until round end. If new information emerges about competitor behavior (leaderboard hints, IMC patches), update via solver.
