import json
from datamodel import Order, TradingState

LIMIT = 80

# --- IPR Parameters ---
IPR = "INTARIAN_PEPPER_ROOT"
IPR_TARGET_POS = 20    # Asset drifts up, maintain a base long position
EMA_ALPHA = 0.2        # Smooths price without the heavy OLS array
SPREAD_HALF = 7        # Base spread edge (average 14 ticks / 2)

# --- ACO Parameters ---
ACO = "ASH_COATED_OSMIUM"
ACO_FV = 10000
ACO_TAKE_WIDTH = 1
ACO_DISREGARD_EDGE = 1
ACO_JOIN_EDGE = 2
ACO_DEFAULT_EDGE = 4
ACO_ADVERSE_VOL = 15


class Trader:
    def __init__(self):
        self.ipr_ema = None

    def _aco(self, state):
        """Pure MM/MT for ACO. No forced liquidation."""
        book = state.order_depths[ACO]
        if not (book.buy_orders or book.sell_orders):
            return []

        pos = state.position.get(ACO, 0)
        fv = ACO_FV
        buy_cap = LIMIT - pos
        sell_cap = LIMIT + pos
        orders = []

        # --- 1. Aggressive Taker Logic ---
        for price, vol in sorted(book.sell_orders.items()):
            if buy_cap <= 0 or price > fv - ACO_TAKE_WIDTH:
                break
            if abs(vol) >= ACO_ADVERSE_VOL:
                continue
            qty = min(buy_cap, -vol)
            orders.append(Order(ACO, price, qty))
            buy_cap -= qty

        for price, vol in sorted(book.buy_orders.items(), reverse=True):
            if sell_cap <= 0 or price < fv + ACO_TAKE_WIDTH:
                break
            if vol >= ACO_ADVERSE_VOL:
                continue
            qty = min(sell_cap, vol)
            orders.append(Order(ACO, price, -qty))
            sell_cap -= qty

        # --- 2. Passive Maker Logic ---
        asks_above = [p for p in book.sell_orders if p > fv + ACO_DISREGARD_EDGE]
        bids_below = [p for p in book.buy_orders if p < fv - ACO_DISREGARD_EDGE]

        if asks_above:
            ref = min(asks_above)
            ask_price = ref if (ref - fv) <= ACO_JOIN_EDGE else ref - 1
        else:
            ask_price = round(fv + ACO_DEFAULT_EDGE)

        if bids_below:
            ref = max(bids_below)
            bid_price = ref if (fv - ref) <= ACO_JOIN_EDGE else ref + 1
        else:
            bid_price = round(fv - ACO_DEFAULT_EDGE)

        # Safety check
        if bid_price >= ask_price:
            ask_price = bid_price + 1

        if buy_cap > 0:
            orders.append(Order(ACO, bid_price, buy_cap))
        if sell_cap > 0:
            orders.append(Order(ACO, ask_price, -sell_cap))

        return orders

    def _ipr(self, state):
        """Micro-structure MT/MM for IPR. Biased long for macro drift."""
        book = state.order_depths[IPR]
        bids = sorted(book.buy_orders.items(), reverse=True) 
        asks = sorted(book.sell_orders.items()) 

        if not (bids and asks):
            return []

        pos = state.position.get(IPR, 0)
        buy_cap = LIMIT - pos
        sell_cap = LIMIT + pos
        orders = []

        best_bid, bid_vol_1 = bids[0]
        best_ask, ask_vol_1 = asks[0]
        ask_vol_1 = abs(ask_vol_1) # Standardize to positive for OBI math

        l1_mid = (best_bid + best_ask) / 2.0

        # Update EMA
        if self.ipr_ema is None:
            self.ipr_ema = l1_mid
        else:
            self.ipr_ema = (l1_mid * EMA_ALPHA) + (self.ipr_ema * (1 - EMA_ALPHA))

        # Calculate Signals
        total_vol = bid_vol_1 + ask_vol_1
        obi = (bid_vol_1 - ask_vol_1) / total_vol if total_vol > 0 else 0

        l2_div = 0
        if len(bids) > 1 and len(asks) > 1:
            l2_mid = (bids[1][0] + asks[1][0]) / 2.0
            l2_div = l2_mid - l1_mid

        # --- 1. Aggressive Taker Logic ---
        # If L1 OBI is heavily skewed Bid OR L2 is dragging price up, cross the spread
        if obi > 0.7 or l2_div > 2:
            qty = min(buy_cap, ask_vol_1)
            if qty > 0:
                orders.append(Order(IPR, best_ask, qty))
                buy_cap -= qty
        
        # --- 2. Passive Maker Logic ---
        pos_offset = pos - IPR_TARGET_POS
        
        # Skew shifts quotes down if inventory is high, up if inventory is low
        skew = pos_offset / 20.0  

        bid_price = round(l1_mid - SPREAD_HALF - skew)
        ask_price = round(l1_mid + SPREAD_HALF - skew)

        # Safety: keep quotes outside the immediate L1 spread
        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)
        if bid_price >= ask_price:
            ask_price = bid_price + 1

        # Asymmetric Sizing: Post heavier on the bid to accumulate the long position
        if buy_cap > 0:
            orders.append(Order(IPR, bid_price, buy_cap))
        
        if sell_cap > 0:
            # Offer less Ask liquidity when we want to build our long position
            offer_qty = max(1, sell_cap // 2) if pos < IPR_TARGET_POS else sell_cap
            orders.append(Order(IPR, ask_price, -offer_qty))

        return orders

    def run(self, state: TradingState):
        saved = json.loads(state.traderData) if state.traderData else None
        if saved and isinstance(saved, dict):
            self.ipr_ema = saved.get("ema", None)

        result = {}
        
        if ACO in state.order_depths:
            result[ACO] = self._aco(state)
            
        if IPR in state.order_depths:
            result[IPR] = self._ipr(state)

        return result, 0, json.dumps(
            {"ema": self.ipr_ema},
            separators=(",", ":")
        )