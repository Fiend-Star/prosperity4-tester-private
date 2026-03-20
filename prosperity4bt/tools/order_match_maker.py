import math
import random
from prosperity4bt.datamodel import TradingState, Order, Symbol, Trade
from prosperity4bt.models.input import BacktestData, MarketTrade
from prosperity4bt.models.output import TradeRow
from prosperity4bt.models.test_options import TradeMatchingMode, MatchMode


# =========================================================================
# Bot parameters (reverse-engineered from tutorial round data)
# =========================================================================
TAKER_PARAMS = {
    # Calibrated to match website scores (s25: TOM~1,800, EM~1,050)
    # Raw observed cadences: TOM=2430ms, EM=4910ms
    # Sim cadences adjusted for unified-book competition model
    "TOMATOES": {"cadence_ms": 1300, "qty_range": (2, 5)},
    "EMERALDS": {"cadence_ms": 7000, "qty_range": (3, 8)},
}
TICK_MS = 100


# =========================================================================
# Inline OrderBook — port of extracted IMC simulation/orderbook.py
# Uses sorted lists instead of SortedKeyList (no external dependency)
# =========================================================================
class _SimOrder:
    __slots__ = ('price', 'quantity', 'user_id', 'seq')
    def __init__(self, price, quantity, user_id, seq):
        self.price = price
        self.quantity = quantity
        self.user_id = user_id
        self.seq = seq

class SimOrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.buy_orders: list[_SimOrder] = []   # sorted: highest price first, then seq asc
        self.sell_orders: list[_SimOrder] = []   # sorted: lowest price first, then seq asc
        self._seq = 0

    def add_buy(self, price: int, qty: int, user_id: str):
        self._seq += 1
        self.buy_orders.append(_SimOrder(price, qty, user_id, self._seq))
        self.buy_orders.sort(key=lambda o: (-o.price, o.seq))

    def add_sell(self, price: int, qty: int, user_id: str):
        self._seq += 1
        # Store sell qty as NEGATIVE (IMC convention: sell_orders have negative quantities)
        self.sell_orders.append(_SimOrder(price, -abs(qty), user_id, self._seq))
        self.sell_orders.sort(key=lambda o: (o.price, o.seq))

    def add_orders(self, orders: list[_SimOrder]):
        """Batch add and match — mirrors IMC's OrderBook.add()"""
        for o in orders:
            self._seq += 1
            o.seq = self._seq
            if o.quantity > 0:
                self.buy_orders.append(o)
            else:
                self.sell_orders.append(o)
        self.buy_orders.sort(key=lambda o: (-o.price, o.seq))
        self.sell_orders.sort(key=lambda o: (o.price, o.seq))
        return self._match()

    def _match(self) -> list[Trade]:
        """Match while best_bid.price == best_ask.price (IMC's exact == logic)"""
        trades = []
        while (self.buy_orders and self.sell_orders
               and self.buy_orders[0].price == self.sell_orders[0].price):
            bb = self.buy_orders[0]
            ba = self.sell_orders[0]
            price = bb.price
            qty = min(bb.quantity, -ba.quantity)
            trades.append(Trade(self.symbol, price, qty, bb.user_id, ba.user_id, 0))
            bb.quantity -= qty
            ba.quantity += qty
            if bb.quantity == 0:
                self.buy_orders.pop(0)
            if ba.quantity == 0:
                self.sell_orders.pop(0)
        return trades

    @property
    def best_bid(self) -> int | None:
        return self.buy_orders[0].price if self.buy_orders else None

    @property
    def best_ask(self) -> int | None:
        return self.sell_orders[0].price if self.sell_orders else None


class OrderMatchMaker:

    def __init__(self, state: TradingState, back_data: BacktestData, orders: dict[Symbol, list[Order]],
                 trade_matching_mode: TradeMatchingMode, match_mode: MatchMode = MatchMode.default):
        self.state = state
        self.back_data = back_data
        self.orders = orders
        self.trade_matching_mode = trade_matching_mode
        self.match_mode = match_mode

    def match(self) -> list[TradeRow]:
        if self.match_mode == MatchMode.sim:
            return self._match_sim()
        if self.match_mode in (MatchMode.imc, MatchMode.strict):
            return self._match_imc()
        return self._match_default()

    # =========================================================================
    # DEFAULT MODE: original >= crossing + market trade fallback
    # =========================================================================

    def _match_default(self) -> list[TradeRow]:
        result = []
        market_trades = self.back_data.get_market_trades_at(self.state.timestamp)

        for product in self.back_data.products:
            new_trades = []
            for order in self.orders.get(product, []):
                new_trade = self.__match_order(order, market_trades.get(product, []))
                new_trades.extend(new_trade)

            if len(new_trades) > 0:
                self.state.own_trades[product] = new_trades
                result.extend([TradeRow(trade) for trade in new_trades])

        for product, trades in market_trades.items():
            for trade in trades:
                trade.trade.quantity = min(trade.buy_quantity, trade.sell_quantity)
            remaining_market_trades = [t.trade for t in trades if t.trade.quantity > 0]
            self.state.market_trades[product] = remaining_market_trades
            result.extend([TradeRow(trade) for trade in remaining_market_trades])

        return result

    def __match_order(self, order: Order, market_trades: list[MarketTrade]) -> list[Trade]:
        if order.quantity > 0:
            return self.__match_buy_order(order, market_trades)
        elif order.quantity < 0:
            return self.__match_sell_order(order, market_trades)
        return []

    def __match_buy_order(self, order, market_trades) -> list[Trade]:
        trades = []
        sell_orders = self.state.order_depths[order.symbol].sell_orders
        price_matched = sorted(price for price in sell_orders.keys() if price <= order.price)
        for price in price_matched:
            volume = min(order.quantity, abs(sell_orders[price]))
            self.__deduct_volume_from_order(sell_orders, price, volume)
            trade = self.__create_buy_order(order, volume, price, "")
            trades.append(trade)
            if order.quantity == 0:
                return trades

        if self.trade_matching_mode == TradeMatchingMode.none:
            return trades

        matched_market_trades = [t for t in market_trades if self.__can_match_buy_order(order, t)]
        for market_trade in matched_market_trades:
            volume = min(order.quantity, market_trade.sell_quantity)
            market_trade.sell_quantity -= volume
            trade = self.__create_buy_order(order, volume, order.price, market_trade.trade.seller)
            trades.append(trade)
            if order.quantity == 0:
                return trades
        return trades

    def __match_sell_order(self, order, market_trades) -> list[Trade]:
        trades = []
        buy_orders = self.state.order_depths[order.symbol].buy_orders
        price_matches = sorted((price for price in buy_orders.keys() if price >= order.price), reverse=True)
        for price in price_matches:
            volume = min(abs(order.quantity), buy_orders[price])
            self.__deduct_volume_from_order(buy_orders, price, volume)
            trade = self.__create_sell_order(order, volume, price, "")
            trades.append(trade)
            if order.quantity == 0:
                return trades

        if self.trade_matching_mode == TradeMatchingMode.none:
            return trades

        matched_market_trades = [t for t in market_trades if self.__can_match_sell_order(order, t)]
        for market_trade in matched_market_trades:
            volume = min(abs(order.quantity), market_trade.buy_quantity)
            market_trade.buy_quantity -= volume
            trade = self.__create_sell_order(order, volume, order.price, market_trade.trade.buyer)
            trades.append(trade)
            if order.quantity == 0:
                return trades
        return trades

    def __can_match_buy_order(self, order: Order, market_trade: MarketTrade) -> bool:
        if market_trade.sell_quantity == 0:
            return False
        if market_trade.trade.price > order.price:
            return False
        if market_trade.trade.price == order.price:
            return self.trade_matching_mode == TradeMatchingMode.all
        return True

    def __can_match_sell_order(self, order: Order, market_trade: MarketTrade) -> bool:
        if market_trade.buy_quantity == 0:
            return False
        if market_trade.trade.price < order.price:
            return False
        if market_trade.trade.price == order.price:
            return self.trade_matching_mode == TradeMatchingMode.all
        return True

    # =========================================================================
    # IMC / STRICT MODE: == exact matching based on extracted orderbook.py
    #
    # Tick sequence:
    # 1. MM bot posts orders (from CSV order_depths)
    # 2. Our orders added — aggressive takes clamped to best bid/ask
    # 3. Match: == exact price only (takes fill, posts rest)
    # 4. Taker bot arrives (from CSV market_trades), hits current best bid/ask
    # 5. Match: taker crosses our resting orders if we're at best
    # =========================================================================

    def _match_imc(self) -> list[TradeRow]:
        result = []
        market_trades = self.back_data.get_market_trades_at(self.state.timestamp)

        for product in self.back_data.products:
            od = self.state.order_depths.get(product)
            if not od:
                continue

            our_orders = self.orders.get(product, [])
            our_trades = []

            # Snapshot the MM bot's book
            mm_sells = dict(od.sell_orders)  # {price: -volume}
            mm_buys = dict(od.buy_orders)    # {price: +volume}

            best_ask = min(mm_sells.keys()) if mm_sells else None
            best_bid = max(mm_buys.keys()) if mm_buys else None

            # --- Phase 1: Match our aggressive takes (== with price clamping) ---
            # Separate our orders into takes and posts
            resting_buys = []   # (price, remaining_qty, order_ref)
            resting_sells = []  # (price, remaining_qty, order_ref)

            for order in our_orders:
                if order.quantity > 0:
                    # Buy order
                    if best_ask is not None and order.price >= best_ask:
                        # Aggressive take — clamp to best_ask, fill at ascending ask prices
                        prices = sorted(p for p in mm_sells if p <= order.price)
                        for price in prices:
                            if order.quantity <= 0:
                                break
                            avail = abs(mm_sells[price])
                            vol = min(order.quantity, avail)
                            self.__deduct_volume_from_order(mm_sells, price, vol)
                            trade = self.__create_buy_order(order, vol, price, "")
                            our_trades.append(trade)
                    if order.quantity > 0:
                        # Remaining quantity rests in the book
                        resting_buys.append((order.price, order.quantity, order))

                elif order.quantity < 0:
                    # Sell order
                    if best_bid is not None and order.price <= best_bid:
                        # Aggressive take — clamp to best_bid, fill at descending bid prices
                        prices = sorted((p for p in mm_buys if p >= order.price), reverse=True)
                        for price in prices:
                            if order.quantity >= 0:
                                break
                            avail = mm_buys[price]
                            vol = min(abs(order.quantity), avail)
                            self.__deduct_volume_from_order(mm_buys, price, vol)
                            trade = self.__create_sell_order(order, vol, price, "")
                            our_trades.append(trade)
                    if order.quantity < 0:
                        resting_sells.append((order.price, abs(order.quantity), order))

            # Update order_depths with remaining MM volumes
            od.sell_orders = mm_sells
            od.buy_orders = mm_buys

            # --- Phase 2: Taker simulation (imc mode only, skip for strict) ---
            if self.match_mode == MatchMode.imc:
                # Compute effective best bid/ask including our resting orders
                eff_best_bid = best_bid
                if resting_buys:
                    our_best_bid = max(p for p, _, _ in resting_buys)
                    eff_best_bid = max(our_best_bid, best_bid) if best_bid else our_best_bid

                eff_best_ask = best_ask
                if resting_sells:
                    our_best_ask = min(p for p, _, _ in resting_sells)
                    eff_best_ask = min(our_best_ask, best_ask) if best_ask else our_best_ask

                mid = ((best_bid or 0) + (best_ask or 99999)) / 2

                for mt in market_trades.get(product, []):
                    trade = mt.trade

                    if trade.price <= mid:
                        # Taker SOLD — hits the effective best bid
                        # Check if our resting buy is at the effective best bid
                        if eff_best_bid is not None and resting_buys:
                            # Sort resting buys: highest price first (best bid), then by insertion order
                            resting_buys.sort(key=lambda x: -x[0])
                            for i, (rp, rq, order_ref) in enumerate(resting_buys):
                                if rp == eff_best_bid and rq > 0:
                                    vol = min(rq, mt.sell_quantity)
                                    if vol > 0:
                                        mt.sell_quantity -= vol
                                        fill_trade = self.__create_buy_order(order_ref, vol, rp, "TAKER")
                                        our_trades.append(fill_trade)
                                        resting_buys[i] = (rp, rq - vol, order_ref)
                                        break
                    else:
                        # Taker BOUGHT — hits the effective best ask
                        if eff_best_ask is not None and resting_sells:
                            resting_sells.sort(key=lambda x: x[0])
                            for i, (rp, rq, order_ref) in enumerate(resting_sells):
                                if rp == eff_best_ask and rq > 0:
                                    vol = min(rq, mt.buy_quantity)
                                    if vol > 0:
                                        mt.buy_quantity -= vol
                                        fill_trade = self.__create_sell_order(order_ref, vol, rp, "TAKER")
                                        our_trades.append(fill_trade)
                                        resting_sells[i] = (rp, rq - vol, order_ref)
                                        break

            # Record our fills
            if our_trades:
                self.state.own_trades[product] = our_trades
                result.extend([TradeRow(t) for t in our_trades])

            # Remaining market trades visible to trader
            mts = market_trades.get(product, [])
            for mt in mts:
                mt.trade.quantity = min(mt.buy_quantity, mt.sell_quantity)
            remaining = [mt.trade for mt in mts if mt.trade.quantity > 0]
            self.state.market_trades[product] = remaining
            result.extend([TradeRow(t) for t in remaining])

        return result

    # =========================================================================
    # SIM MODE: Full agent-based simulation with extracted IMC OrderBook
    #
    # Per tick:
    # 1. MM bot orders loaded from CSV OrderDepth into unified book
    # 2. Our orders added → == matching (aggressive takes fill immediately)
    # 3. Taker bot arrives probabilistically → hits current best bid/ask
    # 4. == matching again (taker fills us or MM based on price-time priority)
    # =========================================================================

    def _match_sim(self) -> list[TradeRow]:
        result = []
        ts = self.state.timestamp

        for product in self.back_data.products:
            od = self.state.order_depths.get(product)
            if not od:
                continue

            book = SimOrderBook(product)

            # Step 1: Add MM bot orders from CSV OrderDepth
            mm_orders = []
            for price, vol in od.buy_orders.items():
                mm_orders.append(_SimOrder(price, vol, "MM_BOT", 0))
            for price, vol in od.sell_orders.items():
                mm_orders.append(_SimOrder(price, abs(vol), "MM_BOT", 0))
                mm_orders[-1].quantity = vol  # keep negative for sells

            for o in mm_orders:
                if o.quantity > 0:
                    book.add_buy(o.price, o.quantity, "MM_BOT")
                elif o.quantity < 0:
                    book.add_sell(o.price, abs(o.quantity), "MM_BOT")

            # Step 2: Add our orders — aggressive takes get clamped for == matching
            our_orders = self.orders.get(product, [])
            for order in our_orders:
                if order.quantity > 0:
                    if book.best_ask is not None and order.price >= book.best_ask:
                        # Aggressive buy — walk through ask levels
                        asks_to_hit = [(o.price, -o.quantity) for o in book.sell_orders
                                       if o.price <= order.price]
                        for ask_price, ask_vol in asks_to_hit:
                            if order.quantity <= 0:
                                break
                            fill_qty = min(order.quantity, ask_vol)
                            # Direct fill against the MM at this ask level
                            book.add_buy(ask_price, fill_qty, "SUBMISSION")
                            trades = book._match()
                            for t in trades:
                                if t.buyer == "SUBMISSION":
                                    self._sim_fill_buy(order, t, product)
                                    result.append(TradeRow(t))
                    # Post remaining at our price
                    if order.quantity > 0:
                        book.add_buy(order.price, order.quantity, "SUBMISSION")

                elif order.quantity < 0:
                    if book.best_bid is not None and order.price <= book.best_bid:
                        # Aggressive sell — walk through bid levels
                        bids_to_hit = [(o.price, o.quantity) for o in book.buy_orders
                                       if o.price >= order.price]
                        for bid_price, bid_vol in bids_to_hit:
                            if order.quantity >= 0:
                                break
                            fill_qty = min(abs(order.quantity), bid_vol)
                            book.add_sell(bid_price, fill_qty, "SUBMISSION")
                            trades = book._match()
                            for t in trades:
                                if t.seller == "SUBMISSION":
                                    self._sim_fill_sell(order, t, product)
                                    result.append(TradeRow(t))
                    if order.quantity < 0:
                        book.add_sell(order.price, abs(order.quantity), "SUBMISSION")

            # Step 3: Taker bot — Poisson arrival
            params = TAKER_PARAMS.get(product)
            if params:
                p_arrive = TICK_MS / params["cadence_ms"]
                if random.random() < p_arrive:
                    qty_lo, qty_hi = params["qty_range"]
                    taker_qty = random.randint(qty_lo, qty_hi)
                    taker_sells = random.random() < 0.5  # 50/50 side

                    if taker_sells and book.best_bid is not None:
                        # Taker sells → hits best bid (could be our posted buy)
                        hit_price = book.best_bid
                        book.add_sell(hit_price, taker_qty, "TAKER")
                    elif not taker_sells and book.best_ask is not None:
                        # Taker buys → hits best ask (could be our posted sell)
                        hit_price = book.best_ask
                        book.add_buy(hit_price, taker_qty, "TAKER")

                    # Match taker crosses
                    taker_trades = book._match()
                    bot_trades = []
                    for t in taker_trades:
                        t.timestamp = ts
                        if t.buyer == "SUBMISSION":
                            # Find which of our orders this fills
                            for order in our_orders:
                                if order.quantity > 0 and order.price == t.price:
                                    self._sim_fill_buy(order, t, product)
                                    break
                            result.append(TradeRow(t))
                        elif t.seller == "SUBMISSION":
                            for order in our_orders:
                                if order.quantity < 0 and order.price == t.price:
                                    self._sim_fill_sell(order, t, product)
                                    break
                            result.append(TradeRow(t))
                        else:
                            bot_trades.append(t)

                    # Bot-to-bot trades visible as market_trades
                    if bot_trades:
                        self.state.market_trades.setdefault(product, []).extend(bot_trades)
                        result.extend([TradeRow(t) for t in bot_trades])

            # Record our fills
            our_fills = [tr.trade for tr in result
                         if tr.trade.symbol == product and
                         (tr.trade.buyer == "SUBMISSION" or tr.trade.seller == "SUBMISSION")]
            if our_fills:
                self.state.own_trades[product] = our_fills

        return result

    def _sim_fill_buy(self, order: Order, trade: Trade, product: str):
        trade.timestamp = self.state.timestamp
        vol = trade.quantity
        self.state.position[product] = self.state.position.get(product, 0) + vol
        self.back_data.profit_loss[product] -= trade.price * vol
        order.quantity -= vol

    def _sim_fill_sell(self, order: Order, trade: Trade, product: str):
        trade.timestamp = self.state.timestamp
        vol = trade.quantity
        self.state.position[product] = self.state.position.get(product, 0) - vol
        self.back_data.profit_loss[product] += trade.price * vol
        order.quantity += vol

    # =========================================================================
    # Shared helpers
    # =========================================================================

    def __create_buy_order(self, order: Order, volume: int, price: int, seller: str):
        self.state.position[order.symbol] = self.state.position.get(order.symbol, 0) + volume
        self.back_data.profit_loss[order.symbol] -= price * volume
        order.quantity -= volume
        return Trade(order.symbol, price, volume, "SUBMISSION", seller, self.state.timestamp)

    def __create_sell_order(self, order: Order, volume: int, price: int, buyer: str):
        self.state.position[order.symbol] = self.state.position.get(order.symbol, 0) - volume
        self.back_data.profit_loss[order.symbol] += price * volume
        order.quantity += volume
        return Trade(order.symbol, price, volume, buyer, "SUBMISSION", self.state.timestamp)

    def __deduct_volume_from_order(self, orders: dict[int, int], price: int, volume_to_be_deducted: int):
        if orders[price] > 0:
            orders[price] -= volume_to_be_deducted
        elif orders[price] < 0:
            orders[price] += volume_to_be_deducted
        if orders[price] == 0:
            orders.pop(price)
