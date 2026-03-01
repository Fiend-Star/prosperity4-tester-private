from dataclasses import dataclass
from src.datamodel import Trade


@dataclass
class MarketTrade:
    trade: Trade
    buy_quantity: int
    sell_quantity: int