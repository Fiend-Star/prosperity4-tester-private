from pathlib import Path
from src.models.trade_matching_mode import TradeMatchingMode


class TestOptions:
    def __init__(self, algorithm_path: Path, round_day: list[str], output_file: Path):
        self.algorithm_path = algorithm_path
        self.round_day = round_day
        self.output_file = output_file
        self.back_data_dir = None
        self.print_output = False
        self.trade_matching_mode = TradeMatchingMode.all
        self.show_progress = False
        self.merge_profit_loss = False
        self.show_visualizer = False
        self.merge_timestamps = True
