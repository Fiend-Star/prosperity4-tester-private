from dataclasses import dataclass

@dataclass
class ObservationRow:
    timestamp: int
    bidPrice: float
    askPrice: float
    transportFees: float
    exportTariff: float
    importTariff: float
    sugarPrice: float
    sunlightIndex: float

    @classmethod
    def parse_from_str(cls, line: str):
        columns = line.split(";")
        return ObservationRow(
            timestamp = int(columns[0]),
            bidPrice = float(columns[1]),
            askPrice = float(columns[2]),
            transportFees = float(columns[3]),
            exportTariff = float(columns[4]),
            importTariff = float(columns[5]),
            sugarPrice = float(columns[6]),
            sunlightIndex = float(columns[7]),
        )

    def to_dic(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "bidPrice": self.bidPrice,
            "askPrice": self.askPrice,
            "transportFees": self.transportFees,
            "exportTariff": self.exportTariff,
            "importTariff": self.importTariff,
            "sugarPrice": self.sugarPrice,
            "sunlightIndex": self.sunlightIndex,
        }