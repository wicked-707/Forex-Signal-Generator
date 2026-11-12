import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

m15 = pd.read_parquet("data/EURUSD_M15.parquet")

m15["time"] = pd.to_datetime(
    m15["time"],
    utc=True
)

m15 = (
    m15
    .set_index("time")
    .sort_index()
)

m15["atr"] = ta.atr(
    m15["high"],
    m15["low"],
    m15["close"],
    length=14
)

results = []

for _, trade in trades.iterrows():

    signal_time = pd.to_datetime(
        trade["signal_time"],
        utc=True
    )

    direction = trade["direction"]

    try:
        signal_idx = m15.index.get_loc(
            signal_time
        )
    except KeyError:
        continue

    first_idx = signal_idx + 1
    second_idx = signal_idx + 2
    entry_idx = signal_idx + 3

    if entry_idx >= len(m15):
        continue

    first = m15.iloc[first_idx]
    second = m15.iloc[second_idx]
    entry = m15.iloc[entry_idx]

    # Same confirmation rule used in the grid.
    if direction == "BUY":

        confirmed = (
            first["close"] > first["open"]
            and
            second["close"] > second["open"]
        )

    else:

        confirmed = (
            first["close"] < first["open"]
            and
            second["close"] < second["open"]
        )

    if not confirmed:
        continue

    signal_price = float(
        m15.iloc[signal_idx]["close"]
    )

    entry_price = float(
        entry["open"]
    )

    atr = m15.iloc[signal_idx]["atr"]

    if pd.isna(atr) or atr <= 0:
        continue

    if direction == "BUY":

        movement = entry_price - signal_price

    else:

        movement = signal_price - entry_price

    movement_atr = movement / atr

    results.append({
        "direction": direction,
        "movement_atr": movement_atr,
        "movement_pips": movement / 0.0001
    })

out = pd.DataFrame(results)

print()
print("SCALP V2 CONFIRMATION ENTRY EXTENSION")
print("--------------------------------------")
print()
print(
    f"Confirmed signals: {len(out)}"
)

print()
print("OVERALL")
print(
    out[
        ["movement_atr", "movement_pips"]
    ]
    .describe()
    .round(3)
    .to_string()
)

print()
print("BY DIRECTION")
print(
    out.groupby("direction")[
        ["movement_atr", "movement_pips"]
    ]
    .agg(
        [
            "count",
            "mean",
            "median",
            "min",
            "max"
        ]
    )
    .round(3)
    .to_string()
)

print()
print("SAVED: diagnose_scalp_confirmation_extension.csv")

out.to_csv(
    "diagnose_scalp_confirmation_extension.csv",
    index=False
)
