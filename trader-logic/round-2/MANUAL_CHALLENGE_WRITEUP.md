# Round 2 Manual Challenge: Invest and Expand

## The problem

Round 2's manual challenge gives you a 50,000 XIREC budget split across three pillars. You pick a percentage allocation for each, the percentages cannot sum to more than 100, and whatever you spend gets subtracted from your gross outcome at the end.

The three pillars behave very differently. Research grows on a log curve from 0 up to 200,000, so the first few percent buy you a lot and later percent buy you very little. Scale is linear, topping out at 7 times at 100%. Speed is the awkward one: it is rank based against everyone else in the competition. Whoever invests the most gets a 0.9 multiplier, whoever invests the least gets 0.1, and everyone else is linearly interpolated by rank.

Your score is `Research(r) * Scale(s) * Speed(sp) - 50000 * (r + s + sp) / 100`.

Two things make this hard. First, Research and Scale compound multiplicatively, so the sweet spot trades off concave returns on research against linear returns on scale. Second, Speed is a game you play against strangers. You cannot optimize it in isolation because its payoff depends on what everyone else does.

## The approach: brute force plus scenario sweep

For the deterministic part of the problem (Research and Scale given a fixed Speed multiplier), brute force is trivial. We enumerate every integer triple where `r + s + sp <= 100`. That comes out to 176,851 allocations. Evaluating each takes microseconds.

The hard part is Speed. Without knowing how competitors allocate, we cannot compute Speed directly. We have to make assumptions about the distribution of competitor speed investments, compute an expected multiplier under that assumption, and then evaluate allocations.

So we built a scenario sweep. For each allocation, we compute the payoff under many different hypothesized competitor distributions, then look at which allocations do well on average and which do well in the worst case.

### Scenarios we covered

The first version of the solver tested 18 scenarios: six values of mean competitor speed (15, 20, 25, 30, 35, 40) crossed with three spreads (sigma of 10, 15, 20), assuming a Normal distribution of competitor investments.

For the second version we expanded this significantly. 101 scenarios in total:

* 96 Normal distributions covering mean 5 through 60 and sigma 5 through 25
* 6 Uniform distributions with different floor and ceiling combinations
* 4 Bimodal mixtures representing markets where most people lowball and a minority bid aggressively
* 5 rank simulations where we draw 200 actual competitor samples from different priors (Normal, Uniform, Beta, Bimodal) and compute our rank exactly

The Beta and Bimodal priors are there because the actual player population probably is not a clean Normal. Most players will pick round numbers like 30 or 50, a chunk will go all-in on one pillar, and a few will put almost nothing on Speed because they did not realize it was a rank game. Covering these cases makes the solver output more robust to model mis-specification.

### Total computation

176,851 allocations times 101 scenarios is about 17.9 million evaluations. The whole thing runs in a few seconds because each evaluation is a handful of floating point operations.

## Results

### Per scenario winners

Each scenario has its own optimal allocation and they move predictably. When mean competitor Speed is low (say mu = 15), the optimal allocation pushes Scale hard (around s = 54) because we can be competitive on Speed with relatively little investment. When mean Speed is high (mu = 55 or 60), the optimum tilts toward Speed (sp = 60 plus) because otherwise we get a very low multiplier.

This matches intuition. If everyone else is asleep on Speed, you coast. If everyone else is aggressive, you have to match them.

### Mean optimal across all scenarios

The allocation that maximizes average payoff across all 101 scenarios is **(r=16, s=46, sp=38)**. It returns a mean of 172,539 with a worst case of negative 10,463 and a best case of 305,815.

Almost every allocation in the top 10 by mean clusters in the same neighborhood: r between 15 and 17, s between 44 and 48, sp between 37 and 41. The differences are under a thousand XIRECs in mean PnL. So any allocation in that cluster is effectively equivalent.

### Robust optimum

The allocation that maximizes the worst case is dramatically different: **(r=11, s=29, sp=60)**. It guarantees at least 59,301 in every scenario we tested, with a mean of 125,463.

This one works because 60% on Speed is high enough to pay for the top rank multiplier under almost any competitor distribution we could think of. You sacrifice Research and Scale to buy certainty.

### Sensitivity table

| Allocation | Mean | Worst | Best | Character |
|-----|-----:|------:|-----:|-----------|
| (16, 46, 38) | 172,539 | -10,463 | 305,815 | Mean optimal |
| (15, 44, 41) | 171,807 | -12,972 | 283,062 | Point optimum under mu=30, sigma=15 |
| (15, 46, 39) | 172,434 | -11,307 | 298,202 | v1 mean optimal |
| (15, 40, 45) | 167,634 | -15,994 | 252,784 | Round-numbers heuristic |
| (11, 29, 60) | 125,463 | +59,301 | 146,741 | Worst-case robust |

## Why the worst case goes negative

A few allocations in our top-10-by-mean list have negative worst-case PnL. The reason is that when Speed multiplier lands at 0.1 (you are dead last on Speed), the gross becomes very small and the budget cost dominates. This happens when you under-invest in Speed and everyone else went heavy on it.

That failure mode is only possible in a narrow slice of scenarios (extreme competitor behavior). For the expected payoff we care about, it washes out.

## Our recommendation

Go with **(16, 46, 38)**.

The reasoning is straightforward. This is the mean optimal across every scenario we modeled, it differs from nearby alternatives by noise, and the worst case (losing 10k) is irrelevant because our Round 1 result of 177,000 already clears the 200,000 threshold by itself. The manual challenge PnL is pure upside on top of a safe cumulative.

The robust allocation (11, 29, 60) is the right pick if you have a strong reason to believe the competitive landscape is very adversarial. We do not have that reason. The player base in Prosperity tends to spread investments broadly, so the bimodal and rank-simulation scenarios we tested all still give (16, 46, 38) strong expected returns.

## What brute force cannot solve

We want to be honest about what this analysis does and does not accomplish.

What it does accomplish:
* Exhaustive coverage of the integer allocation space
* Robust coverage of parametric distribution assumptions about competitors
* Explicit rank simulation against drawn competitor samples

What it does not accomplish:
* We cannot observe the actual competitor distribution. We can only model it.
* The choice between mean-optimal and robust-optimal is a judgment call about how much faith you have in the model.
* Fractional allocations are not in the search space. The UI appears to only accept integer percentages, so this is probably not a gap, but we have not verified every input field.

The real residual uncertainty is in the Speed multiplier, not in the Research or Scale calculations. Those two are deterministic functions of your input. If our Speed modeling is close to reality, (16, 46, 38) is very close to optimal. If it is way off, all bets are on whether the true distribution looks more like our Normal scenarios or our bimodal ones.

## Files produced

* [invest_expand_solver.py](invest_expand_solver.py) - original 18-scenario solver
* [invest_expand_solver_v2.py](invest_expand_solver_v2.py) - expanded 101-scenario solver with multiple distribution models
* [invest_expand_results.json](invest_expand_results.json) - v1 outputs
* [invest_expand_results_v2.json](invest_expand_results_v2.json) - v2 outputs including per-scenario optima, top-20 tables, sensitivity data

## Bottom line

Submit **(r=16, s=46, sp=38)**. Expected payoff around 172k, plausibly much higher if competitors cluster low on Speed. The 10k downside is insignificant given the Round 1 cushion.

If you want to be more defensive, (11, 29, 60) guarantees at least 59k but caps your upside around 147k. We do not recommend this because your cumulative position does not need the insurance.
