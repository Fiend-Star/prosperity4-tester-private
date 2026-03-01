from dataclasses import dataclass
from src.models.acttivty_row import ActivityLogRow
from src.models.sandbox_log_row import SandboxLogRow
from src.models.trader_row import TradeRow


@dataclass
class BacktestResult:
    round_num: int
    day_num: int
    sandbox_logs: list[SandboxLogRow]
    activity_logs: list[ActivityLogRow]
    trades: list[TradeRow]

    def __init__(self, round_num: int, day_num: int, sandbox_logs: list[SandboxLogRow]=None, activity_logs: list[ActivityLogRow]=None, trades: list[TradeRow]=None):
        self.round_num = round_num
        self.day_num = day_num
        self.sandbox_logs = sandbox_logs if sandbox_logs is not None else []
        self.activity_logs = activity_logs if activity_logs is not None else []
        self.trades = trades if trades is not None else []

    # return a list of activities that happened at the end of the day, i.e. last timestamp
    def final_activities(self) -> list[ActivityLogRow]:
        last_time_stamp = self.activity_logs[-1].timestamp
        return [activity for activity in self.activity_logs if activity.timestamp == last_time_stamp]