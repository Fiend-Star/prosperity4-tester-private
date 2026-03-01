from dataclasses import dataclass

from src.datamodel import Symbol, Trade
from src.models.market_trade import MarketTrade
from src.models.observation_row import ObservationRow
from src.models.price_row import PriceRow


@dataclass
class BacktestData:
    round_num: int
    day_num: int
    prices: dict[int, dict[Symbol, PriceRow]]
    trades: dict[int, dict[Symbol, list[Trade]]]
    observations: dict[int, ObservationRow]
    products: list[Symbol]
    profit_loss: dict[Symbol, float]

    def to_dict(self):
        return {
            "round_num": self.round_num,
            "day_num": self.day_num,
            "prices": {
                    outer_key: {
                        inner_key: price_row.to_dict() for inner_key, price_row in inner_dict.items()
                    }
                    for outer_key, inner_dict in self.prices.items()
                },
            "trades": {
                    outer_key: {
                        inner_key: [trade.__str__() for trade in trade_list] for inner_key, trade_list in inner_dict.items()
                    }
                    for outer_key, inner_dict in self.trades.items()
                },
            "observations": { k: v.to_dic() for k, v in self.observations.items() },
            "products": self.products,
            "profit_loss": self.profit_loss
        }


    def get_market_trades_at(self, timestamp: int) -> dict[Symbol, list[MarketTrade]]:
        return {
            product: [MarketTrade(t, t.quantity, t.quantity) for t in trades] for product, trades in self.trades[timestamp].items()
        }