import zlib
from prosperity4bt.datamodel import TradingState, Order, Symbol, Trade
from prosperity4bt.models.input import BacktestData, MarketTrade
from prosperity4bt.models.output import TradeRow
from prosperity4bt.models.test_options import TradeMatchingMode, MatchMode


# =========================================================================
# Bot parameters (reverse-engineered from website submissions)
# =========================================================================
# extra_rate is the per-tick probability that an inside-spread taker arrives
# and fills our resting quote. These takers are invisible in the CSV trades
# file — they materialise only when our post improves the MM's best, which
# is the mechanism behind the website's extra fill count.
TAKER_PARAMS = {
    "INTARIAN_PEPPER_ROOT": {"qty_range": (3, 17),
                              "extra_rate": 0.0},   # R2 IPR BT 7,354 vs website 7,464 (1.5% err, no supplement needed)
    "ASH_COATED_OSMIUM": {"qty_range": (2, 10),
                           "extra_rate": 0.030},    # R2-calibrated against round98 (submission 275130). R2 ACO BT 1,465 vs website 1,451 (1.0% err). R1 day 0 drifts ~32% at this rate — R1 used 0.064 pre-determinism fix; re-run calibrate_imc.py per round.
}


class OrderMatchMaker:

    def __init__(self, state: TradingState, back_data: BacktestData, orders: dict[Symbol, list[Order]],
                 trade_matching_mode: TradeMatchingMode, match_mode: MatchMode = MatchMode.default):
        self.state = state
        self.back_data = back_data
        self.orders = orders
        self.trade_matching_mode = trade_matching_mode
        self.match_mode = match_mode

    def match(self) -> list[TradeRow]:
        if self.match_mode == MatchMode.imc:
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
    # IMC MODE: == exact matching with deterministic taker supplement.
    #
    # Tick sequence:
    # 1. MM bot posts orders (from CSV order_depths)
    # 2. Our orders added — aggressive takes clamped to best bid/ask
    # 3. Match: == exact price only (takes fill, posts rest)
    # 4. Inside-spread taker hits our resting order at the calibrated rate
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
            resting_buys = []   # (price, remaining_qty, order_ref)
            resting_sells = []  # (price, remaining_qty, order_ref)

            for order in our_orders:
                if order.quantity > 0:
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
                        resting_buys.append((order.price, order.quantity, order))

                elif order.quantity < 0:
                    if best_bid is not None and order.price <= best_bid:
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

            # --- Phase 2: Inside-spread taker fills ---
            # Our inside-spread orders attract takers that wouldn't trade against
            # the MM's wider quotes. Strategy-independent across 10 runs.
            params = TAKER_PARAMS.get(product)
            if params and params.get("extra_rate", 0) > 0:
                extra_rate = params["extra_rate"]
                ts = self.state.timestamp
                # Deterministic hash for reproducibility (CRC32 is stable across Python processes; hash() is not).
                tick_hash = (ts * 2654435761 + zlib.crc32(product.encode())) & 0xFFFFFFFF
                if (tick_hash % 10000) < int(extra_rate * 10000):
                    qty_lo, qty_hi = params["qty_range"]
                    taker_qty = qty_lo + (tick_hash >> 16) % (qty_hi - qty_lo + 1)
                    taker_sells = (tick_hash >> 8) % 2 == 0

                    # Only fill if our resting order improves the MM's best
                    if taker_sells and resting_buys:
                        resting_buys.sort(key=lambda x: -x[0])
                        for i, (rp, rq, order_ref) in enumerate(resting_buys):
                            if rq > 0 and (best_bid is None or rp > best_bid):
                                vol = min(rq, taker_qty)
                                if vol > 0:
                                    fill = self.__create_buy_order(
                                        order_ref, vol, rp, "TAKER")
                                    our_trades.append(fill)
                                    resting_buys[i] = (rp, rq - vol, order_ref)
                                break
                    elif not taker_sells and resting_sells:
                        resting_sells.sort(key=lambda x: x[0])
                        for i, (rp, rq, order_ref) in enumerate(resting_sells):
                            if rq > 0 and (best_ask is None or rp < best_ask):
                                vol = min(rq, taker_qty)
                                if vol > 0:
                                    fill = self.__create_sell_order(
                                        order_ref, vol, rp, "TAKER")
                                    our_trades.append(fill)
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
