from dataclasses import dataclass

from src.datamodel import Trade


@dataclass
class TradeRow:
    trade: Trade

    @property
    def timestamp(self) -> int:
        return self.trade.timestamp

    def with_offset(self, timestamp_offset: int) -> "TradeRow":
        return TradeRow(
            Trade(
                self.trade.symbol,
                self.trade.price,
                self.trade.quantity,
                self.trade.buyer,
                self.trade.seller,
                self.trade.timestamp + timestamp_offset,
            )
        )

    def __str__(self) -> str:
        return (
            "  "
            + f"""
  {{
    "timestamp": {self.trade.timestamp},
    "buyer": "{self.trade.buyer}",
    "seller": "{self.trade.seller}",
    "symbol": "{self.trade.symbol}",
    "currency": "SEASHELLS",
    "price": {self.trade.price},
    "quantity": {self.trade.quantity},
  }}
        """.strip()
        )