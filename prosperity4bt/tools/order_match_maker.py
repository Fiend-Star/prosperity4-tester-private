from prosperity4bt.datamodel import TradingState, Order, Symbol, Trade
from prosperity4bt.models.input import BacktestData, MarketTrade
from prosperity4bt.models.output import TradeRow
from prosperity4bt.models.test_options import TradeMatchingMode, MatchMode


class OrderMatchMaker:

    def __init__(self, state: TradingState, back_data: BacktestData, orders: dict[Symbol, list[Order]],
                 trade_matching_mode: TradeMatchingMode, match_mode: MatchMode = MatchMode.default):
        self.state = state
        self.back_data = back_data
        self.orders = orders
        self.trade_matching_mode = trade_matching_mode
        self.match_mode = match_mode

    def match(self) -> list[TradeRow]:
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
