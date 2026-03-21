import json
from datamodel import Order, TradingState

"""
s35_ar2_trailing.py — AR(2) Mean-Reversion MM + Trailing Stop Skew

TOMATOES: +-3 spread, full capacity
  FV = blend of AR(2)-corrected EMA (50%), VWAP (30%), OBI shift (20%)
  AR(2): phi1=-0.44, phi2=-0.20 (calibrated from lag-1 AC=-0.44)
  EMA alpha=0.3 smooths AR(2) prediction

EMERALDS: +-7 from FV=10000, full capacity
  Trailing stop PnL management: track peak PnL, ramp skew on drawdowns
  Tier 0 (<50 dd): symmetric +-7
  Tier 1 (50-150): 1-tick flatten skew
  Tier 2 (150-300): 2-tick flatten skew
  Tier 3 (>300): 3-tick skew + aggressive take at fair
"""

# ═══ TOMATOES CONFIG ═══
PHI1 = -0.44
PHI2 = -0.20
EMA_ALPHA = 0.3
W_AR2 = 0.5
W_VWAP = 0.3
OBI_K = 2.0          # max OBI shift in ticks
HALF_SPREAD_T = 3    # post at FV +/- 3
VWAP_WINDOW = 10

# ═══ EMERALDS CONFIG ═══
FV_EM = 10000
HALF_SPREAD_E = 7    # post at FV +/- 7
LIMIT = 80


class Trader:
    def __init__(self):
        self.mids = []       # TOMATOES mid history [lag2, lag1]
        self.ema = None      # EMA of AR(2) prediction
        self.vwap_buf = []   # [(price, qty), ...] for rolling VWAP
        self.em_rpnl = 0.0   # EMERALDS realized PnL
        self.em_peak = 0.0   # EMERALDS peak total PnL (high-water mark)
        self.em_last_pos = 0 # last known EMERALDS position

    def bid(self):
        return 15

    def run(self, state: TradingState):
        td = json.loads(state.traderData) if state.traderData else None
        if td:
            self.mids = td.get("m", [])
            self.ema = td.get("e")
            self.vwap_buf = td.get("vt", [])
            self.em_rpnl = td.get("ep", 0.0)
            self.em_peak = td.get("pk", 0.0)
            self.em_last_pos = td.get("lp", 0)

        orders = {}
        conversions = 0

        # ════════════════════════════════════════════
        # TOMATOES — AR(2) + VWAP + OBI blended FV, ±3 MM
        # ════════════════════════════════════════════
        if "TOMATOES" in state.order_depths:
            od = state.order_depths["TOMATOES"]
            if od.buy_orders and od.sell_orders:
                to = []
                bb = max(od.buy_orders)
                ba = min(od.sell_orders)
                mid = (bb + ba) * 0.5
                pos = state.position.get("TOMATOES", 0)

                # ── 1. AR(2) corrected EMA ──
                self.mids.append(mid)
                if len(self.mids) > 3:
                    self.mids = self.mids[-3:]

                if len(self.mids) >= 3:
                    dm1 = self.mids[-1] - self.mids[-2]
                    dm2 = self.mids[-2] - self.mids[-3]
                    ar2_pred = mid + PHI1 * dm1 + PHI2 * dm2
                else:
                    ar2_pred = mid

                if self.ema is None:
                    self.ema = ar2_pred
                else:
                    self.ema = EMA_ALPHA * ar2_pred + (1 - EMA_ALPHA) * self.ema
                fv_ar2 = self.ema

                # ── 2. VWAP from market trades ──
                trades = state.market_trades.get("TOMATOES", [])
                for t in trades:
                    self.vwap_buf.append([t.price, t.quantity])
                self.vwap_buf = self.vwap_buf[-VWAP_WINDOW:]

                if self.vwap_buf:
                    pv_sum = sum(p * q for p, q in self.vwap_buf)
                    q_sum = sum(q for _, q in self.vwap_buf)
                    fv_vwap = pv_sum / q_sum if q_sum > 0 else mid
                else:
                    fv_vwap = mid

                # ── 3. OBI (Order Book Imbalance) ──
                bid_vol = sum(od.buy_orders.values())
                ask_vol = sum(-v for v in od.sell_orders.values())
                total_vol = bid_vol + ask_vol
                if total_vol > 0:
                    obi = (bid_vol - ask_vol) / total_vol
                else:
                    obi = 0.0
                obi_shift = obi * OBI_K

                # ── 4. Blend ──
                fv = W_AR2 * fv_ar2 + W_VWAP * fv_vwap + (1 - W_AR2 - W_VWAP) * mid + obi_shift
                tv = round(fv)

                tb = LIMIT - pos
                ts = LIMIT + pos

                # Phase 1: Take at fair value
                for p, v in sorted(od.sell_orders.items()):
                    if tb > 0 and p <= tv:
                        q = min(tb, -v)
                        to.append(Order("TOMATOES", p, q))
                        tb -= q

                for p, v in sorted(od.buy_orders.items(), reverse=True):
                    if ts > 0 and p >= tv:
                        q = min(ts, v)
                        to.append(Order("TOMATOES", p, -q))
                        ts -= q

                # Phase 2: Post at ±3 from FV, full remaining capacity
                if tb > 0:
                    bid_price = tv - HALF_SPREAD_T
                    bid_price = min(bid_price, ba - 1)  # never cross the spread
                    to.append(Order("TOMATOES", bid_price, tb))
                if ts > 0:
                    ask_price = tv + HALF_SPREAD_T
                    ask_price = max(ask_price, bb + 1)
                    to.append(Order("TOMATOES", ask_price, -ts))

                orders["TOMATOES"] = to

        # ════════════════════════════════════════════
        # EMERALDS — Fixed FV ±7, trailing stop skew
        # ════════════════════════════════════════════
        if "EMERALDS" in state.order_depths:
            od = state.order_depths["EMERALDS"]
            if od.buy_orders and od.sell_orders:
                eo = []
                bb = max(od.buy_orders)
                ba = min(od.sell_orders)
                mid = (bb + ba) * 0.5
                pos = state.position.get("EMERALDS", 0)

                # ── Track realized PnL from own trades ──
                own = state.own_trades.get("EMERALDS", [])
                for t in own:
                    if t.buyer == "SUBMISSION":
                        self.em_rpnl -= t.price * t.quantity   # bought: cash out
                    elif t.seller == "SUBMISSION":
                        self.em_rpnl += t.price * t.quantity   # sold: cash in

                # ── Total PnL = realized + mark-to-market ──
                unrealized = pos * (mid - FV_EM)
                total_pnl = self.em_rpnl + unrealized
                self.em_peak = max(self.em_peak, total_pnl)
                drawdown = max(0.0, self.em_peak - total_pnl)

                # ── Drawdown tier → skew magnitude ──
                if drawdown < 50:
                    skew = 0
                    aggressive_flatten = False
                elif drawdown < 150:
                    skew = 1
                    aggressive_flatten = False
                elif drawdown < 300:
                    skew = 2
                    aggressive_flatten = False
                else:
                    skew = 3
                    aggressive_flatten = True

                # ── Compute skewed quotes ──
                # If long and drawdown: tighten ask, widen bid → encourages selling
                # If short and drawdown: tighten bid, widen ask → encourages buying
                if pos > 0:
                    bid_offset = HALF_SPREAD_E + skew   # widen bid (less eager to buy more)
                    ask_offset = HALF_SPREAD_E - skew   # tighten ask (more eager to sell)
                elif pos < 0:
                    bid_offset = HALF_SPREAD_E - skew   # tighten bid (more eager to buy)
                    ask_offset = HALF_SPREAD_E + skew   # widen ask (less eager to sell more)
                else:
                    bid_offset = HALF_SPREAD_E
                    ask_offset = HALF_SPREAD_E

                # Floor: never let offset go below 1 (never cross FV)
                bid_offset = max(1, bid_offset)
                ask_offset = max(1, ask_offset)

                tb = LIMIT - pos
                ts = LIMIT + pos

                # Phase 1: Take at fair value (always)
                for p, v in sorted(od.sell_orders.items()):
                    if tb > 0 and p <= FV_EM:
                        q = min(tb, -v)
                        eo.append(Order("EMERALDS", p, q))
                        tb -= q
                for p, v in sorted(od.buy_orders.items(), reverse=True):
                    if ts > 0 and p >= FV_EM:
                        q = min(ts, v)
                        eo.append(Order("EMERALDS", p, -q))
                        ts -= q

                # Phase 1.5: Aggressive flatten during severe drawdown
                if aggressive_flatten and abs(pos) > 20:
                    if pos > 0 and ts > 0:
                        # Hit best bid to flatten
                        for p, v in sorted(od.buy_orders.items(), reverse=True):
                            if ts > 0 and p >= FV_EM - 2:
                                q = min(ts, v, pos)
                                eo.append(Order("EMERALDS", p, -q))
                                ts -= q
                    elif pos < 0 and tb > 0:
                        for p, v in sorted(od.sell_orders.items()):
                            if tb > 0 and p <= FV_EM + 2:
                                q = min(tb, -v, -pos)
                                eo.append(Order("EMERALDS", p, q))
                                tb -= q

                # Phase 2: Post skewed quotes, full remaining capacity
                if tb > 0:
                    bid_price = FV_EM - bid_offset
                    bid_price = min(bid_price, ba - 1)
                    eo.append(Order("EMERALDS", bid_price, tb))
                if ts > 0:
                    ask_price = FV_EM + ask_offset
                    ask_price = max(ask_price, bb + 1)
                    eo.append(Order("EMERALDS", ask_price, -ts))

                orders["EMERALDS"] = eo
                self.em_last_pos = pos

        return orders, conversions, json.dumps(
            {
                "m": self.mids,
                "e": self.ema,
                "vt": self.vwap_buf,
                "ep": round(self.em_rpnl, 2),
                "pk": round(self.em_peak, 2),
                "lp": self.em_last_pos,
            },
            separators=(",", ":"),
        )
