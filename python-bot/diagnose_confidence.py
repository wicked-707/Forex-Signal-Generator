import pandas as pd

trades = pd.read_csv("backtest_scalp_trades.csv")

print("SCALP TRAIN - CONFIDENCE ANALYSIS")
print()

result = (
    trades.groupby("confidence")
    .agg(
        trades=("r_multiple", "size"),
        wins=("r_multiple", lambda x: (x > 0).sum()),
        losses=("r_multiple", lambda x: (x < 0).sum()),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
        avg_MFE_R=("mfe_R", "mean") if "mfe_R" in trades.columns else ("r_multiple", "mean"),
    )
)

print(result.round(3).to_string())
print()

for minimum in [4, 5]:
    subset = trades[trades["confidence"] >= minimum]

    print(f"CONFIDENCE >= {minimum}")
    print("Trades:", len(subset))
    print("Win rate: {:.2f}%".format((subset["r_multiple"] > 0).mean() * 100))
    print("Average R: {:.3f}".format(subset["r_multiple"].mean()))
    print("Total R: {:.3f}".format(subset["r_multiple"].sum()))
    print()

print("BY CONFIDENCE AND EXIT")
print(
    trades.groupby(["confidence", "exit_reason"])
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
    )
    .round(3)
    .to_string()
)
