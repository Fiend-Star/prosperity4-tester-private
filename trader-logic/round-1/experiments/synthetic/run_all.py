"""
Multi-seed, multi-strategy synthetic regime test runner.

For each seed: generates round99 CSVs, runs each strategy, captures per-day PnL.
Aggregates mean/median/min/max across seeds per (strategy, regime).

Run:
  python trader-logic/round-1/experiments/synthetic/run_all.py
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from statistics import mean, median, stdev

import os as _os
# Default to 25 seeds; override via env SEEDS=N for 50+ runs.
_SEED_COUNT = int(_os.environ.get("SEEDS", "25"))
SEEDS = [42 + 73 * i for i in range(_SEED_COUNT)]
STRATEGIES = {
    "r1_v4": "trader-logic/round-1/r1_v4.py",
    "r1_v9_def": "trader-logic/round-1/r1_v9_defensive.py",
    "r1_v10_def": "trader-logic/round-1/r1_v10_defensive.py",
    "r1_v11_def": "trader-logic/round-1/r1_v11_defensive.py",
}
REGIMES = ["UPTREND", "FLAT", "DOWNTREND", "REVERSAL", "ACO_CRASH", "ACO_FLASH", "PERMANENT"]
TICKS = 10_000

REPO = Path(__file__).resolve().parents[4]
GENERATOR = REPO / "trader-logic/round-1/experiments/synthetic/generate.py"

DAY_RE = re.compile(r"Round 99 day (\d+): ([-\d,]+)")


def run_strategy(strategy_path: str) -> dict[int, int]:
    """Return {day: pnl} for a single strategy run on round99."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO / "prosperity4bt")
    cmd = [
        sys.executable, "-m", "prosperity4bt",
        strategy_path, "99",
        "--ticks", str(TICKS), "--no-out", "--no-progress",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, env=env)
    pnl = {}
    for line in result.stdout.splitlines():
        m = DAY_RE.search(line)
        if m:
            pnl[int(m.group(1))] = int(m.group(2).replace(",", ""))
    return pnl


def regenerate(seed: int):
    subprocess.run(
        [sys.executable, str(GENERATOR), str(seed)],
        cwd=REPO, check=True, capture_output=True,
    )


def main():
    # results[strategy][regime_idx] = [pnl_seed1, pnl_seed2, ...]
    results = {s: {d: [] for d in range(len(REGIMES))} for s in STRATEGIES}

    for seed in SEEDS:
        print(f"\n{'='*70}\nSeed {seed}\n{'='*70}")
        regenerate(seed)
        for name, path in STRATEGIES.items():
            pnl = run_strategy(path)
            for day in range(len(REGIMES)):
                results[name][day].append(pnl.get(day, 0))
            total = sum(pnl.values())
            per_day = " | ".join(f"{REGIMES[d]}={pnl.get(d, 0):>8,}" for d in range(len(REGIMES)))
            print(f"  {name:12s}: {per_day} | total={total:>9,}")

    # Aggregate
    print("\n" + "=" * 100)
    print(f"AGGREGATE ACROSS {len(SEEDS)} SEEDS (mean, [min..max])")
    print("=" * 100)
    print(f"  {'Strategy':<12s} | " + " | ".join(f"{r:^22s}" for r in REGIMES) + " | " + "TOTAL (mean)".center(14))
    print("  " + "-" * 12 + "-|-" + "-|-".join(["-" * 22] * len(REGIMES)) + "-|-" + "-" * 14)
    for name in STRATEGIES:
        cells = []
        total_mean = 0
        for day in range(len(REGIMES)):
            vals = results[name][day]
            m = mean(vals)
            total_mean += m
            cells.append(f"{m:>8,.0f} [{min(vals):>6,.0f}..{max(vals):>6,.0f}]")
        print(f"  {name:<12s} | " + " | ".join(cells) + f" | {total_mean:>12,.0f}")

    # Ranking by total mean
    print("\nRanking by total mean PnL:")
    ranked = sorted(
        [(n, sum(mean(results[n][d]) for d in range(len(REGIMES)))) for n in STRATEGIES],
        key=lambda x: -x[1],
    )
    for i, (n, tot) in enumerate(ranked):
        print(f"  {i + 1}. {n:12s}  {tot:>12,.0f}")

    # Specific comparison: v9_def vs v4 per regime (insurance cost/benefit)
    print("\nr1_v9_def vs r1_v4 per regime (mean delta):")
    for day in range(len(REGIMES)):
        v4 = mean(results["r1_v4"][day])
        v9 = mean(results["r1_v9_def"][day])
        print(f"  {REGIMES[day]:>10s}: v4={v4:>9,.0f}  v9={v9:>9,.0f}  delta={v9 - v4:+9,.0f}")

    print("\nr1_v10_def vs r1_v9_def per regime (mean delta):")
    for day in range(len(REGIMES)):
        v9 = mean(results["r1_v9_def"][day])
        v10 = mean(results["r1_v10_def"][day])
        print(f"  {REGIMES[day]:>10s}: v9={v9:>9,.0f}  v10={v10:>9,.0f}  delta={v10 - v9:+9,.0f}")

    print("\nr1_v11_def vs r1_v10_def per regime (mean delta with SE, significance):")
    import math as _math
    for day in range(len(REGIMES)):
        v10_vals = results["r1_v10_def"][day]
        v11_vals = results["r1_v11_def"][day]
        v10_m = mean(v10_vals)
        v11_m = mean(v11_vals)
        delta = v11_m - v10_m
        # Paired-difference SE (same seeds = paired samples)
        diffs = [a - b for a, b in zip(v11_vals, v10_vals)]
        se = stdev(diffs) / _math.sqrt(len(diffs)) if len(diffs) > 1 else 0
        sig = "***" if abs(delta) > 2 * se else ("*" if abs(delta) > se else " ")
        print(f"  {REGIMES[day]:>10s}: v10={v10_m:>9,.0f}  v11={v11_m:>9,.0f}  delta={delta:+9,.0f}  SE={se:>5,.0f}  {sig}")


if __name__ == "__main__":
    main()
