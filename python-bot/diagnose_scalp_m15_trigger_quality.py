import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

m15 = pd.read_parquet("data/EURUSD_M15.parquet")

m15["time"] = pd.to_datetime(m15["time"], utc=True)
m15 = m15.set_index("time").sort_index()

m15["ema20"] = ta.ema(m15["close"], length=20)
m15["ema50"] = ta.ema(m15["close"], length=50)
m15["rsi"] = ta.rsi(m15["close"], length=14)
m15["atr"] = ta.atr(
    m15["high"],
    m15["low"],
    m15["close"],
    length=14
)

rows = []

for _, trade in trades.iterrows():

    t = pd.to_datetime(trade["signal_time"], utc=True)

    available = m15.shift(1).loc[:t]

    if len(available) < 5:
        continue

    row = available.iloc[-1]
    prev = available.iloc[-2]

    if pd.isna(row["atr"]) or pd.isna(row["rsi"]):
        continue

    direction = trade["direction"]

    candle_range = row["high"] - row["low"]
    body = abs(row["close"] - row["open"])

    if candle_range > 0:
        body_ratio = body / candle_range
    else:
        body_ratio = 0

    if direction == "BUY":
        directional_body = (
            row["close"] - row["open"]
        ) / row["atr"]

        close_position = (
            row["close"] - row["low"]
        ) / candle_range if candle_range > 0 else 0

        ema20_distance = (
            row["close"] - row["ema20"]
        ) / row["atr"]

        rsi_change = row["rsi"] - prev["rsi"]

    else:
        directional_body = (
            row["open"] - row["close"]
        ) / row["atr"]

        close_position = (
            row["high"] - row["close"]
        ) / candle_range if candle_range > 0 else 0

        ema20_distance = (
            row["ema20"] - row["close"]
        ) / row["atr"]

        rsi_change = prev["rsi"] - row["rsi"]

    rows.append({
        "signal_time": t,
        "direction": direction,
        "directional_body_atr": directional_body,
        "body_ratio": body_ratio,
        "close_position": close_position,
        "rsi_change": rsi_change,
        "ema20_distance_directional": ema20_distance,
        "r_multiple": trade["r_multiple"],
    })


out = pd.DataFrame(rows)

print("SCALP TRAIN - M15 TRIGGER QUALITY")
print()
print("Trades classified:", len(out))
print()

print("DIRECTIONAL CANDLE BODY")

out["body_bucket"] = pd.cut(
    out["directional_body_atr"],
    bins=[-100, 0, .1, .25, .5, .75, 1, 1.5, 2, 100],
    right=False
)

print(
    out.groupby("body_bucket", observed=True)
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
print("CANDLE BODY / RANGE")

out["body_ratio_bucket"] = pd.cut(
    out["body_ratio"],
    bins=[0, .25, .5, .65, .75, .85, 1.01],
    right=False
)

print(
    out.groupby("body_ratio_bucket", observed=True)
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
print("CLOSE LOCATION")

out["close_position_bucket"] = pd.cut(
    out["close_position"],
    bins=[0, .25, .5, .65, .75, .85, 1.01],
    right=False
)

print(
    out.groupby("close_position_bucket", observed=True)
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
print("RSI MOMENTUM")

out["rsi_change_bucket"] = pd.cut(
    out["rsi_change"],
    bins=[-100, 0, 1, 2, 3, 5, 10, 100],
    right=False
)

print(
    out.groupby("rsi_change_bucket", observed=True)
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
print("SAVED: diagnose_scalp_m15_trigger_quality.csv")

out.to_csv(
    "diagnose_scalp_m15_trigger_quality.csv",
    index=False
)
