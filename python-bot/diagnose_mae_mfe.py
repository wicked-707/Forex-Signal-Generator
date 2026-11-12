import pandas as pd

PIP_SIZE = 0.0001

trades = pd.read_csv("backtest_scalp_trades.csv")

m15 = pd.read_parquet("data/EURUSD_M15.parquet")
m15["time"] = pd.to_datetime(m15["time"], utc=True)
m15 = m15.set_index("time").sort_index()

rows = []

for _, r in trades.iterrows():
    entry_time = pd.to_datetime(r["entry_time"], utc=True)
    exit_time = pd.to_datetime(r["exit_time"], utc=True)

    candles = m15.loc[entry_time:exit_time]

    if candles.empty:
        continue

    entry = r["entry_price"]
    direction = r["direction"]
    stop_pips = r["stop_pips"]

    if direction == "BUY":
        mae_pips = (entry - candles["low"].min()) / PIP_SIZE
        mfe_pips = (candles["high"].max() - entry) / PIP_SIZE
    else:
        mae_pips = (candles["high"].max() - entry) / PIP_SIZE
        mfe_pips = (entry - candles["low"].min()) / PIP_SIZE

    rows.append({
        "direction": direction,
        "entry_time": entry_time,
        "exit_time": exit_time,
        "stop_pips": stop_pips,
        "r_multiple": r["r_multiple"],
        "exit_reason": r["exit_reason"],
        "mae_pips": mae_pips,
        "mfe_pips": mfe_pips,
        "mae_R": mae_pips / stop_pips,
        "mfe_R": mfe_pips / stop_pips,
    })

out = pd.DataFrame(rows)

print("SCALP TRAIN - MAE/MFE")
print()

print("Trades processed:", len(out))
print()

print("OVERALL")
print(
    out[["mae_pips", "mfe_pips", "mae_R", "mfe_R"]]
    .agg(["mean", "median", "min", "max"])
    .round(3)
    .to_string()
)

print()
print("BY EXIT")
print(
    out.groupby("exit_reason")
    .agg(
        trades=("r_multiple", "size"),
        avg_R=("r_multiple", "mean"),
        avg_MAE_R=("mae_R", "mean"),
        median_MAE_R=("mae_R", "median"),
        avg_MFE_R=("mfe_R", "mean"),
        median_MFE_R=("mfe_R", "median"),
    )
    .round(3)
    .to_string()
)

print()
print("LOSERS - MFE")
losers = out[out["r_multiple"] < 0]

print(
    losers[["mfe_R", "mae_R"]]
    .agg(["mean", "median", "min", "max"])
    .round(3)
    .to_string()
)

print()
print("WINNERS - MFE")
winners = out[out["r_multiple"] > 0]

print(
    winners[["mfe_R", "mae_R"]]
    .agg(["mean", "median", "min", "max"])
    .round(3)
    .to_string()
)

out.to_csv("backtest_scalp_mae_mfe.csv", index=False)

print()
print("Saved: backtest_scalp_mae_mfe.csv")
