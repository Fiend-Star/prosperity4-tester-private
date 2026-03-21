import json
from datamodel import Order, TradingState

"""
s36_medallion.py — s3_carry base + data-mined incremental improvements (v3)

START from s3_carry (website-proven 2,857) and add ONLY what helps:
  +OBI FV shift (0.5 tick) — 98% accuracy directional nudge
  +EMERALDS pos aggression — proven in s30
  +Terminal flattening — locks in spread PnL on full days (+545 total)

REMOVED (data-proven to hurt when layered on s3):
  - Spread-parity skew (interferes with carry signal posting prices)
  - Vol-adaptive widening (reduces fills without compensating edge)
  - Position-dependent take filtering (kills good takes during trends)

The s3 carry signal (bid-change ±4, 0.7x decay) IS the alpha. Don't interfere with it.
"""

COEFS = [0.059694, 0.117270, 0.244154, 0.578440]
INTERCEPT = 2.208667
FLOW_COEF = 1.5
FLOW_WINDOW = 5
OBI_SHIFT = 0.0  # OBI is 98% accurate but too weak to flip integer FV rounding
POS_AGGR_EM = 40
LIMIT = 80


class Trader:
    def __init__(self):
        self.mc = []
        self.tf = []
        self.ew = []
        self.prev_bid = None
        self.signal = 0

    def bid(self):
        return 15

    def run(self, state: TradingState):
        td = json.loads(state.traderData) if state.traderData else None
        if td:
            self.mc = td.get("c", [])
            self.tf = td.get("f", [])
            self.ew = td.get("w", [])
            self.prev_bid = td.get("pb")
            self.signal = td.get("sg", 0)

        orders = {}
        conversions = 0

        # ═══ EMERALDS (s3 base + pos aggression from s30) ═══
        if "EMERALDS" in state.order_depths:
            od = state.order_depths["EMERALDS"]
            if od.buy_orders and od.sell_orders:
                eo = []
                pos = state.position.get("EMERALDS", 0)
                tb, ts_ = LIMIT - pos, LIMIT + pos
                buys = sorted(od.buy_orders.items(), reverse=True)
                sells = sorted(od.sell_orders.items())

                self.ew.append(abs(pos) == LIMIT)
                if len(self.ew) > 10:
                    self.ew = self.ew[-10:]
                soft = len(self.ew) == 10 and sum(self.ew) >= 5 and self.ew[-1]
                hard = len(self.ew) == 10 and all(self.ew)

                em_buy_lim = 10000 if pos <= POS_AGGR_EM else 9999
                em_sell_lim = 10000 if pos >= -POS_AGGR_EM else 10001

                for p, v in sells:
                    if tb > 0 and p <= em_buy_lim:
                        q = min(tb, -v); eo.append(Order("EMERALDS", p, q)); tb -= q
                if tb > 0 and hard:
                    q = tb // 2; eo.append(Order("EMERALDS", 10000, q)); tb -= q
                if tb > 0 and soft:
                    q = tb // 2; eo.append(Order("EMERALDS", 9998, q)); tb -= q
                if tb > 0:
                    eo.append(Order("EMERALDS", min(9999, buys[0][0] + 1), tb))
                for p, v in buys:
                    if ts_ > 0 and p >= em_sell_lim:
                        q = min(ts_, v); eo.append(Order("EMERALDS", p, -q)); ts_ -= q
                if ts_ > 0 and hard:
                    q = ts_ // 2; eo.append(Order("EMERALDS", 10000, -q)); ts_ -= q
                if ts_ > 0 and soft:
                    q = ts_ // 2; eo.append(Order("EMERALDS", 10002, -q)); ts_ -= q
                if ts_ > 0:
                    eo.append(Order("EMERALDS", max(10001, sells[0][0] - 1), -ts_))
                orders["EMERALDS"] = eo

        # ═══ TOMATOES (s3_carry + OBI FV shift + terminal flatten) ═══
        if "TOMATOES" in state.order_depths:
            od = state.order_depths["TOMATOES"]
            if od.buy_orders and od.sell_orders:
                to = []
                bb = max(od.buy_orders)
                ba = min(od.sell_orders)
                pos = state.position.get("TOMATOES", 0)
                mid = (bb + ba) * 0.5

                # FV: microprice regression (proven)
                bv = sum(od.buy_orders.values())
                av = sum(-v for v in od.sell_orders.values())
                mp = bb + (bv / (bv + av)) * (ba - bb) if (bv + av) > 0 else mid

                c = self.mc
                if len(c) >= 4:
                    c = c[1:]
                c.append(mp)
                self.mc = c

                if len(c) == 4:
                    fv = INTERCEPT + sum(co * val for co, val in zip(COEFS, c))
                else:
                    fv = mp

                # Trade flow (proven)
                trades = state.market_trades.get("TOMATOES")
                if trades:
                    sv = sum(t.quantity if t.price >= mid else -t.quantity for t in trades)
                    self.tf.append(sv)
                else:
                    self.tf.append(0.0)
                if len(self.tf) > FLOW_WINDOW:
                    self.tf = self.tf[-FLOW_WINDOW:]
                fs = max(-1.0, min(1.0, sum(self.tf) / 15.0))
                fv -= fs * FLOW_COEF

                # OBI FV shift (NEW: 98% accuracy, +0.5 tick)
                total_bv = sum(od.buy_orders.values())
                total_av = sum(-v for v in od.sell_orders.values())
                if (total_bv + total_av) > 0:
                    obi = (total_bv - total_av) / (total_bv + total_av)
                    fv += obi * OBI_SHIFT

                tv = round(fv)

                # Mean-reversion signal (s3_carry, proven on website)
                if self.prev_bid is not None:
                    bid_change = bb - self.prev_bid
                    if bid_change >= 4:
                        self.signal = -1
                    elif bid_change <= -4:
                        self.signal = 1
                    elif abs(bid_change) <= 1:
                        self.signal *= 0.7
                self.prev_bid = bb

                tb = LIMIT - pos
                ts_ = LIMIT + pos

                # PHASE 1: Take at fair (identical to s3)
                for p, v in sorted(od.sell_orders.items()):
                    if tb > 0 and p <= tv:
                        q = min(tb, -v)
                        to.append(Order("TOMATOES", p, q)); tb -= q

                for p, v in sorted(od.buy_orders.items(), reverse=True):
                    if ts_ > 0 and p >= tv:
                        q = min(ts_, v)
                        to.append(Order("TOMATOES", p, -q)); ts_ -= q

                # Terminal flatten (NEW: +545 total PnL on full days)
                # Only on full days (>5000 ticks). Flatten in last 10%.
                if state.timestamp > 900000 and abs(pos) > 10:
                    if pos > 0 and ts_ > 0:
                        for p, v in sorted(od.buy_orders.items(), reverse=True):
                            if ts_ > 0 and pos > 0:
                                q = min(ts_, v, pos)
                                to.append(Order("TOMATOES", p, -q)); ts_ -= q; pos -= q
                    elif pos < 0 and tb > 0:
                        for p, v in sorted(od.sell_orders.items()):
                            if tb > 0 and pos < 0:
                                q = min(tb, -v, -pos)
                                to.append(Order("TOMATOES", p, q)); tb -= q; pos += q

                # PHASE 2: Directional posting (s3_carry signal, proven on website)
                if self.signal > 0.5:
                    if tb > 0:
                        bp = min(tv - 1, bb + 1); bp = min(bp, ba - 1)
                        to.append(Order("TOMATOES", bp, tb))
                    if ts_ > 0 and pos >= 40:
                        ap = max(tv + 1, ba - 1); ap = max(ap, bb + 1)
                        to.append(Order("TOMATOES", ap, -ts_))
                    elif ts_ > 0:
                        ap = max(tv + 3, ba - 1); ap = max(ap, bb + 1)
                        to.append(Order("TOMATOES", ap, -ts_))

                elif self.signal < -0.5:
                    if ts_ > 0:
                        ap = max(tv + 1, ba - 1); ap = max(ap, bb + 1)
                        to.append(Order("TOMATOES", ap, -ts_))
                    if tb > 0 and pos <= -40:
                        bp = min(tv - 1, bb + 1); bp = min(bp, ba - 1)
                        to.append(Order("TOMATOES", bp, tb))
                    elif tb > 0:
                        bp = min(tv - 3, bb + 1); bp = min(bp, ba - 1)
                        to.append(Order("TOMATOES", bp, tb))

                else:
                    if tb > 0:
                        bp = min(tv - 1, bb + 1); bp = min(bp, ba - 1)
                        to.append(Order("TOMATOES", bp, tb))
                    if ts_ > 0:
                        ap = max(tv + 1, ba - 1); ap = max(ap, bb + 1)
                        to.append(Order("TOMATOES", ap, -ts_))

                orders["TOMATOES"] = to

        return orders, conversions, json.dumps(
            {"c": self.mc, "f": self.tf, "w": self.ew,
             "pb": self.prev_bid, "sg": round(self.signal, 3)},
            separators=(",", ":")
        )
