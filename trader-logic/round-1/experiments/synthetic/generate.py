"""
Synthetic regime generator for Round 1 stress testing.

Usage:
  python trader-logic/round-1/experiments/synthetic/generate.py [seed]
  (default seed=42)

Generates 5 days in prosperity4bt/resources/round99/:
  day 0 — UPTREND      (IPR drift +100/1k, ACO stable at 10000)
  day 1 — FLAT         (IPR zero drift, ACO stable)
  day 2 — DOWNTREND    (IPR drift -100/1k, ACO stable)
  day 3 — REVERSAL     (IPR uptrend first 5k, downtrend second 5k, ACO stable)
  day 4 — ACO_CRASH    (IPR uptrend baseline; ACO drops 10000->9940 gradually
                        over ticks 4000-5000, sustained at 9940 through 6000,
                        recovers to 10000 by 7000. Tests circuit-breaker logic.)
  day 5 — ACO_FLASH    (IPR uptrend baseline; ACO drops INSTANTANEOUSLY 10000
                        ->9950 at tick 5000, holds 1000 ticks, snaps back.
                        Tests circuit-breaker REACTIVITY (MA lag vulnerability).)
  day 6 — PERMANENT    (IPR uptrend baseline; ACO drops 10000 -> 9950 at tick
                        5000 and NEVER RECOVERS. Tests persistent regime change
                        where detection lag leaves toxic inventory stuck.)

Regenerate with different seed to test robustness.
"""

import random
import sys
from pathlib import Path

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 42
TICKS = 10_000
OUT = Path("prosperity4bt/resources/round99")
OUT.mkdir(parents=True, exist_ok=True)

PRICE_HEADER = (
    "day;timestamp;product;"
    "bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;"
    "ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;"
    "mid_price;profit_and_loss"
)
TRADE_HEADER = "timestamp;buyer;seller;symbol;currency;price;quantity"


def ipr_mid(tick: int, day: int, rng: random.Random) -> float:
    base = 12_000.0
    noise = rng.gauss(0, 1.0)
    if day in (0, 4, 5, 6):  # uptrend baseline (days 4/5/6 isolate ACO crash events)
        drift = 0.01 * tick
    elif day == 1:
        drift = 0.0
    elif day == 2:
        drift = -0.01 * tick
    else:
        drift = 0.02 * tick if tick < 5000 else 0.02 * 5000 - 0.02 * (tick - 5000)
    return base + drift + noise


def aco_mid(tick: int, day: int, rng: random.Random) -> float:
    if day == 4:
        # ACO_CRASH: gradual 10000 -> 9940 -> 10000 over ticks 4000-7000
        if tick < 4000:
            base = 10_000.0
        elif tick < 5000:
            base = 10_000.0 - 60.0 * (tick - 4000) / 1000.0
        elif tick < 6000:
            base = 9_940.0
        elif tick < 7000:
            base = 9_940.0 + 60.0 * (tick - 6000) / 1000.0
        else:
            base = 10_000.0
        return base + rng.gauss(0, 1.5)
    if day == 5:
        # ACO_FLASH: instantaneous drop at tick 5000, snap back at 6000
        if 5000 <= tick < 6000:
            base = 9_950.0
        else:
            base = 10_000.0
        return base + rng.gauss(0, 1.5)
    if day == 6:
        # PERMANENT: instantaneous drop at tick 5000, NEVER recovers
        base = 10_000.0 if tick < 5000 else 9_950.0
        return base + rng.gauss(0, 1.5)
    return 10_000.0 + rng.gauss(0, 2.0)


def snap_half(x: float) -> float:
    return round(x * 2) / 2.0


def build_book(mid: float, spread: int, rng: random.Random) -> tuple:
    half = spread / 2
    bid1 = int(mid - half)
    ask1 = int(mid + half)
    b1v = rng.randint(5, 20)
    a1v = rng.randint(5, 20)
    bid2 = bid1 - rng.randint(1, 3)
    ask2 = ask1 + rng.randint(1, 3)
    b2v = int(b1v * rng.uniform(1.5, 3.0))
    a2v = int(a1v * rng.uniform(1.5, 3.0))
    if rng.random() < 0.3:
        bid3 = bid2 - rng.randint(1, 2)
        ask3 = ask2 + rng.randint(1, 2)
        b3v = rng.randint(10, 30)
        a3v = rng.randint(10, 30)
    else:
        bid3, ask3, b3v, a3v = None, None, None, None
    return (bid1, b1v, bid2, b2v, bid3, b3v), (ask1, a1v, ask2, a2v, ask3, a3v)


def fmt_book(bids, asks):
    def cell(x):
        return "" if x is None else str(x)
    return ";".join(cell(v) for v in bids) + ";" + ";".join(cell(v) for v in asks)


def write_day(day: int):
    rng = random.Random(SEED + day)
    prices_path = OUT / f"prices_round_99_day_{day}.csv"
    trades_path = OUT / f"trades_round_99_day_{day}.csv"

    price_rows = [PRICE_HEADER]
    trade_rows = [TRADE_HEADER]

    for tick in range(TICKS):
        ts = tick * 100

        ipr_m = ipr_mid(tick, day, rng)
        spread_ipr = rng.choice([12, 14, 14, 15])
        ipr_bids, ipr_asks = build_book(ipr_m, spread_ipr, rng)
        ipr_mid_snap = snap_half((ipr_bids[0] + ipr_asks[0]) / 2)
        price_rows.append(
            f"{day};{ts};INTARIAN_PEPPER_ROOT;{fmt_book(ipr_bids, ipr_asks)};{ipr_mid_snap};0.0"
        )

        aco_m = aco_mid(tick, day, rng)
        spread_aco = rng.choice([16, 18, 18, 20])
        aco_bids, aco_asks = build_book(aco_m, spread_aco, rng)
        aco_mid_snap = snap_half((aco_bids[0] + aco_asks[0]) / 2)
        price_rows.append(
            f"{day};{ts};ASH_COATED_OSMIUM;{fmt_book(aco_bids, aco_asks)};{aco_mid_snap};0.0"
        )

        for product, bids, asks in [
            ("INTARIAN_PEPPER_ROOT", ipr_bids, ipr_asks),
            ("ASH_COATED_OSMIUM", aco_bids, aco_asks),
        ]:
            if rng.random() < 0.30:
                side = rng.choice(["buy", "sell"])
                qty = rng.randint(2, 15)
                price = asks[0] if side == "buy" else bids[0]
                buyer = "TAKER" if side == "buy" else ""
                seller = "" if side == "buy" else "TAKER"
                trade_rows.append(f"{ts};{buyer};{seller};{product};XIRECS;{price}.0;{qty}")

    prices_path.write_text("\n".join(price_rows) + "\n", encoding="utf-8")
    trades_path.write_text("\n".join(trade_rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    print(f"Generating synthetic round99 data (seed={SEED}, {TICKS} ticks/day):")
    for d, label in enumerate(["UPTREND", "FLAT", "DOWNTREND", "REVERSAL", "ACO_CRASH", "ACO_FLASH", "PERMANENT"]):
        write_day(d)
        print(f"  day {d}: {label}")
    print("Done.")
