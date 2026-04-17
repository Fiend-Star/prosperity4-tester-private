"""
Synthetic regime generator for Round 1 stress testing.

Usage:
  python trader-logic/round-1/experiments/synthetic/generate.py [seed]
  (default seed=42)

Generates 13 days in prosperity4bt/resources/round99/:
  day 0 — UPTREND       (IPR drift +100/1k, ACO stable at 10000)
  day 1 — FLAT          (IPR zero drift, ACO stable)
  day 2 — DOWNTREND     (IPR drift -100/1k, ACO stable)
  day 3 — REVERSAL      (IPR uptrend first 5k, downtrend second 5k, ACO stable)
  day 4 — ACO_CRASH     (IPR uptrend; ACO gradient 10000->9940 over 4-5k, hold,
                         recover by 7k. Tests circuit-breaker on slow drops.)
  day 5 — ACO_FLASH     (IPR uptrend; ACO INSTANT drop to 9950 at 5k, snap back
                         at 6k. Tests circuit-breaker reactivity / MA lag.)
  day 6 — PERMANENT     (IPR uptrend; ACO instant drop to 9950 at 5k, no recovery.
                         Tests toxic-maker fix in persistent regime change.)
  day 7 — CRASH_DEEP    (IPR uptrend; ACO instant 150-tick drop to 9850 at 5k,
                         no recovery. Stresses trapped-inventory scenarios.)
  day 8 — ALT_FV_HIGH   (IPR uptrend; ACO stable at 14000 throughout. Tests
                         whether strategies hardcoded to FV=10000 survive a
                         non-10000 starting regime. v14 should fail here; v17
                         bootstrap-anchor should succeed.)
  day 9 — ALT_FV_LOW    (IPR uptrend; ACO stable at 9500. Symmetric test.)
  day 10 — MID_SHIFT    (IPR uptrend; ACO 10000 for first 5k, small legitimate
                         shift to 9990 thereafter. Tests anchor adaptation to
                         legitimate FV shifts that DON'T trigger crash_mode.
                         v14/v17 frozen anchor cannot adapt; v15/v16 adaptive
                         anchor should win here if the shift is below crash
                         threshold.)
  day 11 — DEFENSE_BOT  (IPR uptrend; ACO stable at 10000 + synthetic defense
                         bot that posts big bids at local 50-tick lows and big
                         asks at local 50-tick highs, signaling coming reversal.
                         Tests whether strategies exploit the reversion signal
                         or get adversely selected against big sizes.)
  day 12 — VOLUME_BURST (IPR uptrend; ACO stable at 10000 + informational
                         volume bursts — when next 5 ticks will rise >3 ticks,
                         we boost ASK volume this tick 3x; symmetric for falls.
                         Tests whether volume-imbalance signals predict moves
                         and whether our strategies act on them.)

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


UPTREND_DAYS = {0, 4, 5, 6, 7, 8, 9, 10, 11, 12}  # IPR uptrend baseline for crash/FV test days


def ipr_mid(tick: int, day: int, rng: random.Random) -> float:
    base = 12_000.0
    noise = rng.gauss(0, 1.0)
    if day in UPTREND_DAYS:
        drift = 0.01 * tick
    elif day == 1:
        drift = 0.0
    elif day == 2:
        drift = -0.01 * tick
    else:
        drift = 0.02 * tick if tick < 5000 else 0.02 * 5000 - 0.02 * (tick - 5000)
    return base + drift + noise


def _aco_crash_base(tick: int) -> float:
    # ACO_CRASH: gradient 10000 -> 9940 over 4-5k, hold, recover by 7k
    if tick < 4000:
        return 10_000.0
    if tick < 5000:
        return 10_000.0 - 60.0 * (tick - 4000) / 1000.0
    if tick < 6000:
        return 9_940.0
    if tick < 7000:
        return 9_940.0 + 60.0 * (tick - 6000) / 1000.0
    return 10_000.0


# Per-day base-price functions. Noise scale attached too because some regimes
# have wider noise (ALT_FV_* and default use sigma=2, crash regimes use 1.5).
_ACO_BASES: dict[int, "tuple[callable, float]"] = {
    4: (_aco_crash_base, 1.5),
    5: (lambda t: 9_950.0 if 5000 <= t < 6000 else 10_000.0, 1.5),
    6: (lambda t: 10_000.0 if t < 5000 else 9_950.0, 1.5),
    7: (lambda t: 10_000.0 if t < 5000 else 9_850.0, 1.5),
    8: (lambda t: 14_000.0, 2.0),
    9: (lambda t: 9_500.0, 2.0),
    10: (lambda t: 10_000.0 if t < 5000 else 9_990.0, 1.5),
    11: (lambda t: 10_000.0, 2.0),  # DEFENSE_BOT: signal in book, not mid
    12: (lambda t: 10_000.0, 2.0),  # VOLUME_BURST: signal in book, not mid
}


def aco_mid(tick: int, day: int, rng: random.Random) -> float:
    base_fn, sigma = _ACO_BASES.get(day, (lambda t: 10_000.0, 2.0))
    return base_fn(tick) + rng.gauss(0, sigma)


def snap_half(x: float) -> float:
    return round(x * 2) / 2.0


DEFENSE_LOOKBACK = 50      # window for local-extreme detection
DEFENSE_BIG_VOL = 28       # size of informational big order at extremes
VOLUME_LOOKAHEAD = 5       # ticks of future mid to peek at
VOLUME_MOVE_THRESH = 8.0   # future move magnitude that triggers volume burst
                           # (chosen so signal fires ~5-10% of ticks vs σ=2 noise,
                           # making it meaningfully informational rather than constant)
VOLUME_BURST_MULT = 3      # multiplier applied to the predicted side


def _local_extreme(cur_mid: float, recent: list) -> int:
    """Return +1 if cur is local max of recent+cur window, -1 if local min, 0 otherwise."""
    if len(recent) < DEFENSE_LOOKBACK:
        return 0
    window = recent[-DEFENSE_LOOKBACK:]
    if cur_mid >= max(window):
        return +1
    if cur_mid <= min(window):
        return -1
    return 0


def _apply_informational_signal(b1v: int, a1v: int, mid: float, day: int,
                                aco_recent_mids: list | None,
                                aco_future_mids: list | None) -> tuple[int, int]:
    """Day 11 (DEFENSE_BOT) and Day 12 (VOLUME_BURST) size adjustments."""
    if day == 11 and aco_recent_mids is not None:
        extreme = _local_extreme(mid, aco_recent_mids)
        if extreme == -1:
            b1v = max(b1v, DEFENSE_BIG_VOL)
        elif extreme == +1:
            a1v = max(a1v, DEFENSE_BIG_VOL)
    elif day == 12 and aco_future_mids:
        next_block = aco_future_mids[:VOLUME_LOOKAHEAD]
        if next_block:
            if max(next_block) - mid > VOLUME_MOVE_THRESH:
                a1v *= VOLUME_BURST_MULT
            if mid - min(next_block) > VOLUME_MOVE_THRESH:
                b1v *= VOLUME_BURST_MULT
    return b1v, a1v


def build_book(mid: float, spread: int, rng: random.Random,
               day: int = 0,
               aco_recent_mids: list | None = None,
               aco_future_mids: list | None = None) -> tuple:
    half = spread / 2
    bid1 = int(mid - half)
    ask1 = int(mid + half)
    b1v = rng.randint(5, 20)
    a1v = rng.randint(5, 20)

    b1v, a1v = _apply_informational_signal(
        b1v, a1v, mid, day, aco_recent_mids, aco_future_mids
    )

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


def _emit_product(day: int, ts: int, product: str, bids, asks) -> str:
    mid_snap = snap_half((bids[0] + asks[0]) / 2)
    return f"{day};{ts};{product};{fmt_book(bids, asks)};{mid_snap};0.0"


def _maybe_trade(rng: random.Random, ts: int, product: str, bids, asks) -> str | None:
    if rng.random() >= 0.30:
        return None
    side = rng.choice(["buy", "sell"])
    qty = rng.randint(2, 15)
    price = asks[0] if side == "buy" else bids[0]
    buyer = "TAKER" if side == "buy" else ""
    seller = "" if side == "buy" else "TAKER"
    return f"{ts};{buyer};{seller};{product};XIRECS;{price}.0;{qty}"


def _precompute_future_mids(day: int) -> list[float] | None:
    """Pre-generate full ACO mid series for regimes that require lookahead.
    Uses a SIDE rng so the main stream stays identical to days 0-10."""
    if day != 12:
        return None
    side_rng = random.Random(SEED + day + 997)
    return [aco_mid(t, day, side_rng) for t in range(TICKS)]


def write_day(day: int):
    rng = random.Random(SEED + day)
    aco_mids_full = _precompute_future_mids(day)
    aco_recent: list[float] = []

    price_rows = [PRICE_HEADER]
    trade_rows = [TRADE_HEADER]

    for tick in range(TICKS):
        ts = tick * 100

        ipr_m = ipr_mid(tick, day, rng)
        ipr_bids, ipr_asks = build_book(ipr_m, rng.choice([12, 14, 14, 15]), rng)
        price_rows.append(_emit_product(day, ts, "INTARIAN_PEPPER_ROOT", ipr_bids, ipr_asks))

        aco_m = aco_mid(tick, day, rng)
        aco_future = aco_mids_full[tick + 1:tick + 1 + VOLUME_LOOKAHEAD] if aco_mids_full else None
        aco_bids, aco_asks = build_book(
            aco_m, rng.choice([16, 18, 18, 20]), rng,
            day=day,
            aco_recent_mids=aco_recent if day == 11 else None,
            aco_future_mids=aco_future,
        )
        price_rows.append(_emit_product(day, ts, "ASH_COATED_OSMIUM", aco_bids, aco_asks))

        if day == 11:
            aco_recent.append(aco_m)
            if len(aco_recent) > DEFENSE_LOOKBACK:
                aco_recent = aco_recent[-DEFENSE_LOOKBACK:]

        for product, bids, asks in [
            ("INTARIAN_PEPPER_ROOT", ipr_bids, ipr_asks),
            ("ASH_COATED_OSMIUM", aco_bids, aco_asks),
        ]:
            row = _maybe_trade(rng, ts, product, bids, asks)
            if row is not None:
                trade_rows.append(row)

    (OUT / f"prices_round_99_day_{day}.csv").write_text("\n".join(price_rows) + "\n", encoding="utf-8")
    (OUT / f"trades_round_99_day_{day}.csv").write_text("\n".join(trade_rows) + "\n", encoding="utf-8")


REGIME_LABELS = [
    "UPTREND", "FLAT", "DOWNTREND", "REVERSAL",
    "ACO_CRASH", "ACO_FLASH", "PERMANENT", "CRASH_DEEP",
    "ALT_FV_HIGH", "ALT_FV_LOW", "MID_SHIFT", "DEFENSE_BOT", "VOLUME_BURST",
]


if __name__ == "__main__":
    print(f"Generating synthetic round99 data (seed={SEED}, {TICKS} ticks/day):")
    for d, label in enumerate(REGIME_LABELS):
        write_day(d)
        print(f"  day {d}: {label}")
    print("Done.")
