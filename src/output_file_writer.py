from pathlib import Path
from src.models.backtest_result import BacktestResult


class OutputFileWriter:

    @staticmethod
    def write_to_file(output_file: Path, result: BacktestResult):
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w+", encoding="utf-8") as file:
            file.write("Sandbox logs:\n")
            for row in result.sandbox_logs:
                file.write(str(row))

            file.write("\n\n\nActivities log:\n")
            file.write(
                "day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;mid_price;profit_and_loss\n"
            )
            file.write("\n".join(map(str, result.activity_logs)))

            file.write("\n\n\n\n\nTrade History:\n")
            file.write("[\n")
            file.write(",\n".join(map(str, result.trades)))
            file.write("]")