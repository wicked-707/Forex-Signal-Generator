import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

h1 = pd.read_parquet("data/EURUSD_H1.parquet")

h1["time"] = pd.to_datetime(h1["time"], utc=True)
h1 = h1.set_index("time").sort_index()

h1["ema_fast"] = ta.ema(h1["close"], length=20)
h1["ema_mid"] = ta.ema(h1["close"], length=50)
h1["ema_slow"] = ta.ema(h1["close"], length=200)

h1["rsi"] = ta.rsi(
    h1["close"],
    length=14
)

h1["atr"] = ta.atr(
    h1["high"],
    h1["low"],
    h1["close"],
    length=14
)

rows = []

for _, trade in trades.iterrows():

    t = pd.to_datetime(trade["signal_time"], utc=True)

    available = h1.shift(1).loc[:t]

    if available.empty:
        continue

    row = available.iloc[-1]

    required = [
        row["close"],
        row["ema_fast"],
        row["ema_mid"],
        row["ema_slow"],
        row["rsi"],
        row["atr"],
    ]

    if any(pd.isna(x) for x in required):
        continue

    direction = trade["direction"]

    if direction == "BUY":
        trend_aligned = row["close"] > row["ema_slow"]

        directional_ema20 = (
            row["close"] - row["ema_fast"]
        ) / row["atr"]

        directional_ema50 = (
            row["close"] - row["ema_mid"]
        ) / row["atr"]

    else:
        trend_aligned = row["close"] < row["ema_slow"]

        directional_ema20 = (
            row["ema_fast"] - row["close"]
        ) / row["atr"]

        directional_ema50 = (
            row["ema_mid"] - row["close"]
        ) / row["atr"]

    rows.append({
        "signal_time": t,
        "direction": direction,
        "trend_aligned": trend_aligned,
        "rsi": row["rsi"],
        "ema20_distance_atr": abs(
            row["close"] - row["ema_fast"]
        ) / row["atr"],
        "ema50_distance_atr": abs(
            row["close"] - row["ema_mid"]
        ) / row["atr"],
        "ema200_distance_atr": abs(
            row["close"] - row["ema_slow"]
        ) / row["atr"],
        "directional_ema20_atr": directional_ema20,
        "directional_ema50_atr": directional_ema50,
        "r_multiple": trade["r_multiple"],
        "stop_pips": trade["stop_pips"],
    })


out = pd.DataFrame(rows)

print("SCALP TRAIN - H1 PULLBACK QUALITY")
print()
print("Trades classified:", len(out))
print()

print("H1 EMA20 DISTANCE")

out["ema20_bucket"] = pd.cut(
    out["ema20_distance_atr"],
    bins=[0, .25, .5, .75, 1, 1.5, 2, 100],
    right=False
)

print(
    out.groupby("ema20_bucket", observed=True)
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
    )
    .round(3)
    .to_string()
)

print()
print("H1 EMA50 DISTANCE")

out["ema50_bucket"] = pd.cut(
    out["ema50_distance_atr"],
    bins=[0, .25, .5, .75, 1, 1.5, 2, 100],
    right=False
)

print(
    out.groupby("ema50_bucket", observed=True)
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
    )
    .round(3)
    .to_string()
)

print()
print("H1 RSI")

out["rsi_bucket"] = pd.cut(
    out["rsi"],
    bins=[0, 35, 40, 45, 50, 55, 60, 65, 100],
    right=False
)

print(
    out.groupby("rsi_bucket", observed=True)
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
    )
    .round(3)
    .to_string()
)

print()
print("DIRECTIONAL EMA20 EXTENSION")

out["extension_bucket"] = pd.cut(
    out["directional_ema20_atr"],
    bins=[-100, 0, .25, .5, .75, 1, 1.5, 2, 100],
    right=False
)

print(
    out.groupby("extension_bucket", observed=True)
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
    )
    .round(3)
    .to_string()
)

print()
print("SAVED: diagnose_scalp_h1_pullback.csv")

out.to_csv("diagnose_scalp_h1_pullback.csv", index=False)
