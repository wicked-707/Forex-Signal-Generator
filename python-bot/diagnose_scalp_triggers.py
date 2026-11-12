import pandas as pd
import pandas_ta_classic as ta

PIP_SIZE = 0.0001

trades = pd.read_csv("backtest_scalp_trades.csv")

m15 = pd.read_parquet("data/EURUSD_M15.parquet")
m15["time"] = pd.to_datetime(m15["time"], utc=True)
m15 = m15.set_index("time").sort_index()

m15["ema_fast"] = ta.ema(m15["close"], length=20)
m15["rsi"] = ta.rsi(m15["close"], length=14)

rows = []

for _, trade in trades.iterrows():
    signal_time = pd.to_datetime(trade["signal_time"], utc=True)

    if signal_time not in m15.index:
        continue

    pos = m15.index.get_loc(signal_time)

    if pos < 1:
        continue

    row = m15.iloc[pos]
    prev = m15.iloc[pos - 1]

    direction = trade["direction"]

    if direction == "BUY":
        rsi_trigger = (
            prev["rsi"] < 50 and
            row["rsi"] >= 50
        )

        momentum_trigger = (
            row["close"] > row["ema_fast"] and
            row["close"] > row["open"]
        )

        if rsi_trigger:
            trigger = "RSI"
        elif momentum_trigger:
            trigger = "MOMENTUM"
        else:
            trigger = "UNKNOWN"

    else:
        rsi_trigger = (
            prev["rsi"] > 50 and
            row["rsi"] <= 50
        )

        momentum_trigger = (
            row["close"] < row["ema_fast"] and
            row["close"] < row["open"]
        )

        if rsi_trigger:
            trigger = "RSI"
        elif momentum_trigger:
            trigger = "MOMENTUM"
        else:
            trigger = "UNKNOWN"

    both = rsi_trigger and momentum_trigger

    rows.append({
        "signal_time": signal_time,
        "direction": direction,
        "trigger": trigger,
        "both_conditions": both,
        "confidence": trade["confidence"],
        "stop_pips": trade["stop_pips"],
        "r_multiple": trade["r_multiple"],
        "exit_reason": trade["exit_reason"],
    })

out = pd.DataFrame(rows)

print("SCALP TRAIN - TRIGGER ANALYSIS")
print()
print("Trades classified:", len(out))
print()

print("TRIGGER COUNTS")
print(
    out.groupby("trigger")
    .agg(
        trades=("r_multiple", "size"),
        wins=("r_multiple", lambda x: (x > 0).sum()),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
        avg_stop_pips=("stop_pips", "mean"),
    )
    .round(3)
    .to_string()
)

print()
print("BOTH CONDITIONS")
print(
    out.groupby("both_conditions")
    .agg(
        trades=("r_multiple", "size"),
        wins=("r_multiple", lambda x: (x > 0).sum()),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
    )
    .round(3)
    .to_string()
)

print()
print("TRIGGER + CONFIDENCE")
print(
    out.groupby(["trigger", "confidence"])
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
    )
    .round(3)
    .to_string()
)

out.to_csv("diagnose_scalp_triggers.csv", index=False)

print()
print("Saved: diagnose_scalp_triggers.csv")
