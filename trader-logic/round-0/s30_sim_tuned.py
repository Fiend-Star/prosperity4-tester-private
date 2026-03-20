import json
from datamodel import Order, TradingState

"""
s30_sim_tuned: s25 with only HIGH-CONFIDENCE changes from sim Cartesian sweep.

Changes from s25 (2,855 website):
  1. EM_AGGRESSION=1 → EMERALDS takes at 9999/10001 when pos>40 (was 10000/10000)
  2. FLOW_COEF=1.0 (was 1.5) — 100% in top 50 of sim sweep

Everything else IDENTICAL to s25. Minimal risk of regression.
"""

class Trader:
    def __init__(self):
        self.tc = []
        self.tf = []
        self.ew = []
        self.prev_bid = None
        self.signal = 0

    def bid(self):
        return 15

    def run(self, state: TradingState):
        td = json.loads(state.traderData) if state.traderData else None
        if td:
            self.tc = td.get("c", [])
            self.tf = td.get("f", [])
            self.ew = td.get("w", [])
            self.prev_bid = td.get("pb")
            self.signal = td.get("sg", 0)

        orders = {}

        # ═══ EMERALDS (EM_AGGRESSION=1: take at 9999/10001 when pos>40) ═══
        if "EMERALDS" in state.order_depths:
            od = state.order_depths["EMERALDS"]
            if od.buy_orders and od.sell_orders:
                eo = []
                pos = state.position.get("EMERALDS", 0)
                tb, ts = 80 - pos, 80 + pos
                buys = sorted(od.buy_orders.items(), reverse=True)
                sells = sorted(od.sell_orders.items())
                self.ew.append(abs(pos) == 80)
                if len(self.ew) > 10: self.ew = self.ew[-10:]
                soft = len(self.ew) == 10 and sum(self.ew) >= 5 and self.ew[-1]
                hard = len(self.ew) == 10 and all(self.ew)
                # CHANGE: position aggression on EMERALDS (EM_AGGRESSION=1)
                mbp = 9999 if pos > 40 else 10000
                msp = 10001 if pos < -40 else 10000
                for p, v in sells:
                    if tb > 0 and p <= mbp:
                        q = min(tb, -v); eo.append(Order("EMERALDS", p, q)); tb -= q
                if tb > 0 and hard:
                    q = tb // 2; eo.append(Order("EMERALDS", 10000, q)); tb -= q
                if tb > 0 and soft:
                    q = tb // 2; eo.append(Order("EMERALDS", 9998, q)); tb -= q
                if tb > 0:
                    eo.append(Order("EMERALDS", min(mbp, buys[0][0] + 1), tb))
                for p, v in buys:
                    if ts > 0 and p >= msp:
                        q = min(ts, v); eo.append(Order("EMERALDS", p, -q)); ts -= q
                if ts > 0 and hard:
                    q = ts // 2; eo.append(Order("EMERALDS", 10000, -q)); ts -= q
                if ts > 0 and soft:
                    q = ts // 2; eo.append(Order("EMERALDS", 10002, -q)); ts -= q
                if ts > 0:
                    eo.append(Order("EMERALDS", max(msp, sells[0][0] - 1), -ts))
                orders["EMERALDS"] = eo

        # ═══ TOMATOES (identical to s25 except FLOW_COEF=1.0) ═══
        if "TOMATOES" in state.order_depths:
            od = state.order_depths["TOMATOES"]
            if od.buy_orders and od.sell_orders:
                to = []
                bb, ba = max(od.buy_orders), min(od.sell_orders)
                pos = state.position.get("TOMATOES", 0)
                mid = (bb + ba) * 0.5

                bv = sum(od.buy_orders.values())
                av = sum(-v for v in od.sell_orders.values())
                mp = bb + (bv / (bv + av)) * (ba - bb) if (bv + av) > 0 else mid

                c = self.tc
                if len(c) >= 4: c = c[1:]
                c.append(mp)
                self.tc = c

                if len(c) == 4:
                    fv = 7.388073 + 0.059509*c[0] + 0.117116*c[1] + 0.243910*c[2] + 0.577988*c[3]
                else:
                    fv = mp

                trades = state.market_trades.get("TOMATOES")
                if trades:
                    sv = sum(t.quantity if t.price >= mid else -t.quantity for t in trades)
                    self.tf.append(sv)
                else:
                    self.tf.append(0.0)
                if len(self.tf) > 5: self.tf = self.tf[-5:]
                fs = max(-1.0, min(1.0, sum(self.tf) / 15.0))
                # CHANGE: FLOW_COEF=1.0 (was 1.5)
                fv -= fs * 1.0

                tv = round(fv)

                if self.prev_bid is not None:
                    bid_change = bb - self.prev_bid
                    if bid_change >= 4:
                        self.signal = -1
                    elif bid_change <= -4:
                        self.signal = 1
                    elif abs(bid_change) <= 1:
                        self.signal *= 0.7
                self.prev_bid = bb

                tb = 80 - pos
                ts = 80 + pos

                mbp = tv - 1 if pos > 40 else tv
                msp = tv + 1 if pos < -40 else tv

                for p, v in sorted(od.sell_orders.items()):
                    if tb > 0 and p <= mbp:
                        q = min(tb, -v); to.append(Order("TOMATOES", p, q)); tb -= q
                for p, v in sorted(od.buy_orders.items(), reverse=True):
                    if ts > 0 and p >= msp:
                        q = min(ts, v); to.append(Order("TOMATOES", p, -q)); ts -= q

                if self.signal > 0.5:
                    if tb > 0:
                        to.append(Order("TOMATOES", min(tv - 1, bb + 1), tb))
                    if ts > 0:
                        ask_price = max(tv + 3, ba - 1)
                        to.append(Order("TOMATOES", max(ask_price, bb + 1), -ts))
                elif self.signal < -0.5:
                    if ts > 0:
                        to.append(Order("TOMATOES", max(tv + 1, ba - 1), -ts))
                    if tb > 0:
                        bid_price = min(tv - 3, bb + 1)
                        to.append(Order("TOMATOES", min(bid_price, ba - 1), tb))
                else:
                    if tb > 0:
                        to.append(Order("TOMATOES", min(tv - 1, bb + 1), tb))
                    if ts > 0:
                        to.append(Order("TOMATOES", max(tv + 1, ba - 1), -ts))

                orders["TOMATOES"] = to

        return orders, 0, json.dumps({
            "c": self.tc, "f": self.tf, "w": self.ew,
            "pb": self.prev_bid, "sg": round(self.signal, 3)
        }, separators=(",", ":"))
