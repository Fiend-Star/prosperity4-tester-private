"""
Uniform-price clearing auction optimizer for IMC Prosperity manual challenges.

Given stale order books + a guaranteed buyback price, finds the profit-maximizing
limit order (price, volume) accounting for:
  - Clearing price = price that maximizes traded volume (tie-break: highest price)
  - Price-time priority allocation (we are LAST in time at our price level)
  - Trading fees

Usage: update the order book dicts below and run:
    python trader-logic/auction_solver.py
"""

from __future__ import annotations


def compute_clearing(
    bids: dict[int, int],
    asks: dict[int, int],
    our_side: str,
    our_price: int,
    our_volume: int,
) -> tuple[int, int, int]:
    """
    Returns (clearing_price, total_traded, our_fills).

    bids/asks: {price: volume} for existing book (ask volumes are positive here).
    our_side: "buy" or "sell"
    our_price, our_volume: our limit order
    """
    all_prices = sorted(set(list(bids.keys()) + list(asks.keys()) + [our_price]))

    # Build merged book including our order
    merged_bids: dict[int, list[tuple[int, bool]]] = {}  # price -> [(vol, is_ours)]
    merged_asks: dict[int, list[tuple[int, bool]]] = {}

    for p, v in bids.items():
        merged_bids.setdefault(p, []).append((v, False))
    for p, v in asks.items():
        if v > 0:
            merged_asks.setdefault(p, []).append((v, False))

    if our_side == "buy":
        merged_bids.setdefault(our_price, []).append((our_volume, True))
    else:
        merged_asks.setdefault(our_price, []).append((our_volume, True))

    # For each candidate clearing price, compute traded volume
    best_vol = -1
    best_price = -1

    for cp in all_prices:
        cum_bids = sum(v for p in merged_bids for v, _ in merged_bids[p] if p >= cp)
        cum_asks = sum(v for p in merged_asks for v, _ in merged_asks[p] if p <= cp)
        traded = min(cum_bids, cum_asks)

        if traded > best_vol or (traded == best_vol and cp > best_price):
            best_vol = traded
            best_price = cp

    # Allocate fills at clearing price using price-time priority
    cp = best_price
    traded = best_vol

    if our_side == "buy":
        # Bids filled in order: highest price first, then time priority (we are last)
        remaining = traded
        our_fills = 0
        for p in sorted(merged_bids.keys(), reverse=True):
            if p < cp:
                break
            for vol, is_ours in merged_bids[p]:
                fill = min(vol, remaining)
                if is_ours:
                    our_fills += fill
                remaining -= fill
                if remaining <= 0:
                    break
            if remaining <= 0:
                break
    else:
        # Asks filled: lowest price first, then time priority (we are last)
        remaining = traded
        our_fills = 0
        for p in sorted(merged_asks.keys()):
            if p > cp:
                break
            for vol, is_ours in merged_asks[p]:
                fill = min(vol, remaining)
                if is_ours:
                    our_fills += fill
                remaining -= fill
                if remaining <= 0:
                    break
            if remaining <= 0:
                break

    return cp, traded, our_fills


def optimize_buy(
    bids: dict[int, int],
    asks: dict[int, int],
    buyback: float,
    fee: float,
    max_volume: int,
    product: str,
) -> None:
    """Sweep all buy prices and print profit table."""
    min_price = min(asks.keys())
    max_price = int(buyback)

    print(f"\n{'='*70}")
    print(f"  {product}  |  buyback={buyback}  fee={fee}  max_vol={max_volume:,}")
    print(f"{'='*70}")
    print(f"{'Bid':>5} {'Clear':>6} {'Traded':>10} {'MyFills':>10} {'Edge/u':>8} {'Profit':>12}")
    print(f"{'-'*5:>5} {'-'*6:>6} {'-'*10:>10} {'-'*10:>10} {'-'*8:>8} {'-'*12:>12}")

    best_profit = -1e18
    best_row = None

    for bid_price in range(min_price, max_price + 1):
        cp, traded, fills = compute_clearing(bids, asks, "buy", bid_price, max_volume)
        edge = buyback - cp - fee
        profit = fills * edge

        marker = ""
        if profit > best_profit:
            best_profit = profit
            best_row = (bid_price, cp, traded, fills, edge, profit)

        print(
            f"{bid_price:>5} {cp:>6} {traded:>10,} {fills:>10,} {edge:>8.2f} {profit:>12,.0f}"
        )

    print(f"{'-'*70}")
    if best_row:
        bp, cp, traded, fills, edge, profit = best_row
        print(f"  >>> OPTIMAL: BUY at {bp}, clearing={cp}, fills={fills:,}, profit={profit:,.0f}")
    print()


def optimize_sell(
    bids: dict[int, int],
    asks: dict[int, int],
    buyback: float,
    fee: float,
    max_volume: int,
    product: str,
) -> None:
    """Sweep sell prices — short position costs buyback to close."""
    max_price = max(bids.keys())
    min_price = int(buyback)

    # Only profitable if we sell ABOVE buyback
    if min_price > max_price:
        print(f"\n  {product} SELL: no profitable sell prices (buyback {buyback} > max bid {max_price})")
        return

    print(f"\n  {product} SELL analysis:")
    print(f"{'Ask':>5} {'Clear':>6} {'Traded':>10} {'MyFills':>10} {'Edge/u':>8} {'Profit':>12}")

    for ask_price in range(min_price, max_price + 1):
        cp, traded, fills = compute_clearing(bids, asks, "sell", ask_price, max_volume)
        edge = cp - buyback - fee  # sell at clearing, buy back at buyback
        profit = fills * edge
        print(
            f"{ask_price:>5} {cp:>6} {traded:>10,} {fills:>10,} {edge:>8.2f} {profit:>12,.0f}"
        )


# ============================================================
#  ORDER BOOK DATA — update these for each manual challenge
# ============================================================

flax_bids = {30: 30_000, 29: 5_000, 28: 12_000, 27: 28_000}
flax_asks = {28: 40_000, 31: 20_000, 32: 20_000, 33: 30_000}
FLAX_BUYBACK = 30
FLAX_FEE = 0.0
FLAX_MAX_VOL = 30_000

mushroom_bids = {
    20: 43_000, 19: 17_000, 18: 6_000, 17: 5_000,
    16: 10_000, 15: 5_000, 14: 10_000, 13: 7_000,
}
mushroom_asks = {
    12: 20_000, 13: 25_000, 14: 35_000, 15: 6_000,
    16: 5_000, 17: 0, 18: 10_000, 19: 12_000,
}
MUSHROOM_BUYBACK = 20
MUSHROOM_FEE = 0.10  # 0.05 buy + 0.05 sell
MUSHROOM_MAX_VOL = 43_000

# ============================================================


def global_optimum_2d(
    bids: dict[int, int],
    asks: dict[int, int],
    buyback: float,
    fee: float,
    max_volume: int,
    product: str,
    vol_step: int = 1_000,
) -> tuple[str, int, int, int, int, float]:
    """
    Full 2D sweep over (price, volume) to find the true global maximum.
    Returns (side, price, volume, clearing, fills, profit).
    """
    min_price = min(asks.keys())
    max_price = int(buyback)

    best = ("buy", min_price, 0, 0, 0, 0.0)

    # --- BUY side ---
    print(f"\n{'='*80}")
    print(f"  {product} — GLOBAL 2D SWEEP (buy side, step={vol_step:,})")
    print(f"{'='*80}")

    # Header
    volumes_to_show = list(range(0, max_volume + 1, vol_step))
    if volumes_to_show[-1] != max_volume:
        volumes_to_show.append(max_volume)

    # For each price, find the best volume and print the profit landscape
    print(f"\n  Profit landscape (price × volume, in thousands):")
    print(f"  {'Price':>5} |", end="")
    col_vols = list(range(0, max_volume + 1, max(vol_step, 5_000)))
    if col_vols[-1] != max_volume:
        col_vols.append(max_volume)
    for v in col_vols:
        print(f" {v//1000:>5}k", end="")
    print(f" | {'Best Vol':>9} {'Profit':>10}")
    print(f"  {'-'*5}-+-" + "-" * (len(col_vols) * 7) + "-+-" + "-" * 21)

    for bid_price in range(min_price, max_price + 1):
        row_best_profit = -1e18
        row_best_vol = 0
        row_best_fills = 0
        row_best_cp = 0

        print(f"  {bid_price:>5} |", end="")
        for v in col_vols:
            if v == 0:
                profit = 0.0
            else:
                cp, traded, fills = compute_clearing(bids, asks, "buy", bid_price, v)
                edge = buyback - cp - fee
                profit = fills * edge

            print(f" {profit/1000:>5.1f}k", end="")

            if profit > row_best_profit:
                row_best_profit = profit
                row_best_vol = v
                row_best_cp = cp if v > 0 else 0
                row_best_fills = fills if v > 0 else 0

        # Also check intermediate volumes for true optimum
        for v in volumes_to_show:
            if v == 0:
                continue
            cp, traded, fills = compute_clearing(bids, asks, "buy", bid_price, v)
            edge = buyback - cp - fee
            profit = fills * edge
            if profit > row_best_profit:
                row_best_profit = profit
                row_best_vol = v
                row_best_cp = cp
                row_best_fills = fills

        print(f" | {row_best_vol:>7,}  {row_best_profit:>9,.0f}")

        if row_best_profit > best[5]:
            best = ("buy", bid_price, row_best_vol, row_best_cp, row_best_fills, row_best_profit)

    # --- SELL side (quick check) ---
    max_bid = max(bids.keys())
    for ask_price in range(int(buyback), max_bid + 1):
        for v in volumes_to_show:
            if v == 0:
                continue
            cp, traded, fills = compute_clearing(bids, asks, "sell", ask_price, v)
            edge = cp - buyback - fee
            profit = fills * edge
            if profit > best[5]:
                best = ("sell", ask_price, v, cp, fills, profit)

    side, price, vol, cp, fills, profit = best
    print(f"\n  >>> GLOBAL OPTIMUM: {side.upper()} at {price}, volume={vol:,}")
    print(f"      clearing={cp}, fills={fills:,}, profit={profit:,.0f}")

    return best


def find_volume_breakpoints(
    bids: dict[int, int],
    asks: dict[int, int],
    buyback: float,
    fee: float,
    max_volume: int,
    product: str,
    bid_price: int,
) -> None:
    """
    For a given bid price, trace how clearing price and profit
    change as volume increases — find the exact breakpoints.
    """
    print(f"\n  {product} @ bid={bid_price}: volume breakpoint analysis")
    print(f"  {'Volume':>8} {'Clear':>6} {'Traded':>8} {'Fills':>8} {'Edge':>6} {'Profit':>10}")

    prev_cp = -1
    for v in range(0, max_volume + 1, 500):
        if v == 0:
            continue
        cp, traded, fills = compute_clearing(bids, asks, "buy", bid_price, v)
        edge = buyback - cp - fee
        profit = fills * edge
        marker = "  <<<" if cp != prev_cp and prev_cp != -1 else ""
        if cp != prev_cp or v == max_volume or v <= 2000:
            print(f"  {v:>8,} {cp:>6} {traded:>8,} {fills:>8,} {edge:>6.2f} {profit:>10,.0f}{marker}")
        prev_cp = cp


def exhaustive_search(
    bids: dict[int, int],
    asks: dict[int, int],
    buyback: float,
    fee: float,
    max_volume: int,
    product: str,
    price_range: tuple[int, int] | None = None,
) -> tuple[str, int, int, int, int, float]:
    """
    Brute-force every (side, price, volume) combination.
    Volume step = 1 at clearing-price boundaries, coarser elsewhere.
    Returns (side, price, volume, clearing, fills, profit).
    """
    if price_range is None:
        min_p = min(min(asks.keys()), min(bids.keys()))
        max_p = max(max(asks.keys()), max(bids.keys()))
    else:
        min_p, max_p = price_range

    best = ("buy", 0, 0, 0, 0, 0.0)

    # --- Find clearing-price breakpoints per bid price ---
    # At each bid price, sweep volume 0..max and track where clearing changes
    print(f"\n{'='*85}")
    print(f"  {product} — EXHAUSTIVE SEARCH (vol step=1 at boundaries)")
    print(f"{'='*85}")

    for side in ["buy", "sell"]:
        for price in range(min_p, max_p + 1):
            # Phase 1: coarse scan (step=1000) to find approximate breakpoints
            breakpoints = set()
            prev_cp = -1
            for v in range(1, max_volume + 1, 1000):
                cp, _, _ = compute_clearing(bids, asks, side, price, v)
                if cp != prev_cp and prev_cp != -1:
                    breakpoints.add(v)
                prev_cp = cp
            breakpoints.add(max_volume)

            # Phase 2: fine scan (step=1) around each breakpoint ±1500
            fine_volumes = set()
            for bp in breakpoints:
                for v in range(max(1, bp - 1500), min(max_volume, bp + 1500) + 1):
                    fine_volumes.add(v)
            # Also check a coarse grid everywhere
            for v in range(1, max_volume + 1, 500):
                fine_volumes.add(v)
            fine_volumes.add(max_volume)

            for v in sorted(fine_volumes):
                cp, traded, fills = compute_clearing(bids, asks, side, price, v)
                if side == "buy":
                    edge = buyback - cp - fee
                else:
                    edge = cp - buyback - fee
                profit = fills * edge

                if profit > best[5]:
                    best = (side, price, v, cp, fills, profit)

    side, price, vol, cp, fills, profit = best
    print(f"\n  >>> GLOBAL OPTIMUM: {side.upper()} at {price}, volume={vol:,}")
    print(f"      clearing={cp}, fills={fills:,}, profit={profit:,.1f}")

    # Show the neighborhood around the optimum
    print(f"\n  Neighborhood (price={price}, side={side}):")
    print(f"  {'Vol':>8} {'Clear':>6} {'Traded':>8} {'Fills':>8} {'Edge':>6} {'Profit':>12}")
    for dv in range(-10, 11):
        v = vol + dv
        if v < 1 or v > max_volume:
            continue
        c, t, f = compute_clearing(bids, asks, side, price, v)
        if side == "buy":
            e = buyback - c - fee
        else:
            e = c - buyback - fee
        p = f * e
        marker = "  <<<" if v == vol else ""
        print(f"  {v:>8,} {c:>6} {t:>8,} {f:>8,} {e:>6.2f} {p:>12,.1f}{marker}")

    return best


if __name__ == "__main__":
    flax_opt = exhaustive_search(
        flax_bids, flax_asks, FLAX_BUYBACK, FLAX_FEE, FLAX_MAX_VOL, "DRYLAND_FLAX"
    )
    mush_opt = exhaustive_search(
        mushroom_bids, mushroom_asks, MUSHROOM_BUYBACK, MUSHROOM_FEE, MUSHROOM_MAX_VOL, "EMBER_MUSHROOM"
    )

    # ---- Final summary ----
    print("\n" + "=" * 85)
    print("  EXHAUSTIVE GLOBAL SUMMARY")
    print("=" * 85)
    total = flax_opt[5] + mush_opt[5]
    for name, opt in [("DRYLAND_FLAX", flax_opt), ("EMBER_MUSHROOM", mush_opt)]:
        side, price, vol, cp, fills, profit = opt
        print(f"  {name}: {side.upper()} at {price}, vol={vol:,} -> clearing={cp}, fills={fills:,}, profit={profit:,.1f}")
    print(f"\n  TOTAL PROFIT: {total:,.1f} XIRECs")
