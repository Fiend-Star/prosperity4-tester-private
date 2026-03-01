from dataclasses import dataclass
from src.datamodel import Symbol


@dataclass
class PriceRow:
    day: int
    timestamp: int
    product: Symbol
    bid_prices: list[int]
    bid_volumes: list[int]
    ask_prices: list[int]
    ask_volumes: list[int]
    mid_price: float
    profit_loss: float

    @classmethod
    def parse_from_str(cls, line: str):
        columns = line.split(";")
        return PriceRow(
            day=int(columns[0]),
            timestamp=int(columns[1]),
            product=columns[2],
            bid_prices=cls.__get_column_values(columns, [3, 5, 7]),
            bid_volumes=cls.__get_column_values(columns, [4, 6, 8]),
            ask_prices=cls.__get_column_values(columns, [9, 11, 13]),
            ask_volumes=cls.__get_column_values(columns, [10, 12, 14]),
            mid_price=float(columns[15]),
            profit_loss=float(columns[16]),
        )

    @staticmethod
    def __get_column_values(columns: list[str], indices: list[int]) -> list[int]:
        values = []
        for index in indices:
            value = columns[index]
            if value == "":
                break
            values.append(int(value))
        return values

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "timestamp": self.timestamp,
            "product": self.product,
            "bid_prices": self.bid_prices,
            "bid_volumes": self.bid_volumes,
            "ask_prices": self.ask_prices,
            "ask_volumes": self.ask_volumes,
            "mid_price": self.mid_price,
            "profit_loss": self.profit_loss
        }