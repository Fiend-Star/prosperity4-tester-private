from enum import Enum


class TradeMatchingMode(str, Enum):
    all = "all"
    worse = "worse"
    none = "none"
