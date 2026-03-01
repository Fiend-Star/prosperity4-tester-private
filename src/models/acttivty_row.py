from dataclasses import dataclass
from typing import Any

@dataclass
class ActivityLogRow:
    columns: list[Any]

    @property
    def timestamp(self) -> int:
        return self.columns[1]

    @property
    def symbol(self) -> str:
        return self.columns[2]

    @property
    def profit_loss(self) -> float:
        return self.columns[-1]

    def with_offset(self, timestamp_offset: int, profit_loss_offset: float) -> "ActivityLogRow":
        new_columns = self.columns[:]
        new_columns[1] += timestamp_offset
        new_columns[-1] += profit_loss_offset

        return ActivityLogRow(new_columns)

    def __str__(self) -> str:
        return ";".join(map(str, self.columns))
