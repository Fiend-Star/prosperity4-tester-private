from prosperity4bt.models.output import BacktestResult

# Empirical correction factor for inside-spread market-making strategies.
# The default/imc/strict match modes replay CSV taker arrivals exactly, but
# the website evaluates each submission with a fresh RNG seed, generating
# ~12 extra TOMATOES taker fills per 2000-tick window that never appear in
# the CSV.  Over a full 10 000-tick scoring day this adds ~8 % extra TOMATOES
# PnL.  At-spread strategies that don't improve on the MM's price do NOT
# receive these extra taker fills, so their gap is ≈ 0 %.
#
# Use --match-mode sim to let the backtester generate its own taker arrivals
# (stochastic, so results vary across runs).  In default mode, multiply the
# backtester total by INSIDE_SPREAD_CORRECTION to estimate the website score:
#   estimated_website ≈ backtest_pnl * INSIDE_SPREAD_CORRECTION
INSIDE_SPREAD_CORRECTION = 1.07


class SummaryPrinter:

    @staticmethod
    def print_day_summary(result: BacktestResult):
        final_activities = result.final_activities()
        product_lines = [f"{a.symbol}: {a.profit_loss:,.0f}" for a in final_activities]
        total_profit = sum(a.profit_loss for a in final_activities)
        print(*reversed(product_lines), sep="\n")
        print(f"Total profit: {total_profit:,.0f}")
        estimated = total_profit * INSIDE_SPREAD_CORRECTION
        msg = (f"  (est. website ≈ {estimated:,.0f}"
               f"  [×{INSIDE_SPREAD_CORRECTION} inside-spread correction;"
               f" use --match-mode sim for agent-based estimate])")
        print(msg)


    @staticmethod
    def print_overall_summary(results: list[BacktestResult]):
        print("Profit summary:")

        total_profit = 0
        for result in results:
            final_activities = result.final_activities()
            profit = sum(a.profit_loss for a in final_activities)
            print(f"Round {result.round_num} day {result.day_num}: {profit:,.0f}")
            total_profit += profit

        print(f"Total profit: {total_profit:,.0f}")
        estimated = total_profit * INSIDE_SPREAD_CORRECTION
        print(f"  (est. website ≈ {estimated:,.0f}  [×{INSIDE_SPREAD_CORRECTION} inside-spread correction])")
