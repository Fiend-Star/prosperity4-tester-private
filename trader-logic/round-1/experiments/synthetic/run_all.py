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
from statistics import mean, median

SEEDS = [42, 123, 456, 789]
STRATEGIES = {
    "r1_v4": "trader-logic/round-1/r1_v4.py",
    "r1_v7": "trader-logic/round-1/r1_v7.py",
    "r1_v9_def": "trader-logic/round-1/r1_v9_defensive.py",
}
REGIMES = ["UPTREND", "FLAT", "DOWNTREND", "REVERSAL"]
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
    results = {s: {d: [] for d in range(4)} for s in STRATEGIES}

    for seed in SEEDS:
        print(f"\n{'='*70}\nSeed {seed}\n{'='*70}")
        regenerate(seed)
        for name, path in STRATEGIES.items():
            pnl = run_strategy(path)
            for day in range(4):
                results[name][day].append(pnl.get(day, 0))
            total = sum(pnl.values())
            per_day = " | ".join(f"{REGIMES[d]}={pnl.get(d, 0):>8,}" for d in range(4))
            print(f"  {name:12s}: {per_day} | total={total:>9,}")

    # Aggregate
    print("\n" + "=" * 100)
    print(f"AGGREGATE ACROSS {len(SEEDS)} SEEDS (mean, [min..max])")
    print("=" * 100)
    print(f"  {'Strategy':<12s} | " + " | ".join(f"{r:^22s}" for r in REGIMES) + " | " + "TOTAL (mean)".center(14))
    print("  " + "-" * 12 + "-|-" + "-|-".join(["-" * 22] * 4) + "-|-" + "-" * 14)
    for name in STRATEGIES:
        cells = []
        total_mean = 0
        for day in range(4):
            vals = results[name][day]
            m = mean(vals)
            total_mean += m
            cells.append(f"{m:>8,.0f} [{min(vals):>6,.0f}..{max(vals):>6,.0f}]")
        print(f"  {name:<12s} | " + " | ".join(cells) + f" | {total_mean:>12,.0f}")

    # Ranking by total mean
    print("\nRanking by total mean PnL:")
    ranked = sorted(
        [(n, sum(mean(results[n][d]) for d in range(4))) for n in STRATEGIES],
        key=lambda x: -x[1],
    )
    for i, (n, tot) in enumerate(ranked):
        print(f"  {i + 1}. {n:12s}  {tot:>12,.0f}")

    # Specific comparison: v9_def vs v4 per regime (insurance cost/benefit)
    print("\nr1_v9_def vs r1_v4 per regime (mean delta):")
    for day in range(4):
        v4 = mean(results["r1_v4"][day])
        v9 = mean(results["r1_v9_def"][day])
        print(f"  {REGIMES[day]:>10s}: v4={v4:>9,.0f}  v9={v9:>9,.0f}  delta={v9 - v4:+9,.0f}")

    print("\nr1_v9_def vs r1_v7 per regime (mean delta):")
    for day in range(4):
        v7 = mean(results["r1_v7"][day])
        v9 = mean(results["r1_v9_def"][day])
        print(f"  {REGIMES[day]:>10s}: v7={v7:>9,.0f}  v9={v9:>9,.0f}  delta={v9 - v7:+9,.0f}")


if __name__ == "__main__":
    main()
