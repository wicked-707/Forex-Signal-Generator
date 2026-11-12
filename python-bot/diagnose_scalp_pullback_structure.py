import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

h1 = pd.read_parquet("data/EURUSD_H1.parquet")

h1["time"] = pd.to_datetime(h1["time"], utc=True)
h1 = h1.set_index("time").sort_index()

h1["ema20"] = ta.ema(h1["close"], length=20)
h1["ema50"] = ta.ema(h1["close"], length=50)
h1["ema200"] = ta.ema(h1["close"], length=200)
h1["atr"] = ta.atr(
    h1["high"],
    h1["low"],
    h1["close"],
    length=14
)

rows = []

for _, trade in trades.iterrows():

    t = pd.to_datetime(trade["signal_time"], utc=True)

    # Shift H1 one candle back to match historical anti-lookahead.
    available = h1.shift(1).loc[:t]

    if len(available) < 8:
        continue

    row = available.iloc[-1]
    prev6 = available.iloc[-7:-1]

    required = [
        row["ema20"],
        row["ema50"],
        row["ema200"],
        row["atr"],
    ]

    if any(pd.isna(x) for x in required):
        continue

    direction = trade["direction"]

    # Price movement over previous 6 H1 candles.
    move_6 = row["close"] - prev6.iloc[0]["open"]

    if direction == "BUY":
        directional_move = move_6
    else:
        directional_move = -move_6

    directional_move_atr = directional_move / row["atr"]

    # Current candle.
    body = abs(row["close"] - row["open"])
    body_atr = body / row["atr"]

    if direction == "BUY":
        bullish_candle = row["close"] > row["open"]

        # Did candle touch EMA20?
        ema20_touch = (
            row["low"] <= row["ema20"]
            <= row["high"]
        )

        ema50_touch = (
            row["low"] <= row["ema50"]
            <= row["high"]
        )

        # Close recovered above EMA after touching it.
        ema20_rejection = (
            ema20_touch and
            row["close"] > row["ema20"]
        )

        ema50_rejection = (
            ema50_touch and
            row["close"] > row["ema50"]
        )

    else:
        bullish_candle = row["close"] > row["open"]

        ema20_touch = (
            row["low"] <= row["ema20"]
            <= row["high"]
        )

        ema50_touch = (
            row["low"] <= row["ema50"]
            <= row["high"]
        )

        ema20_rejection = (
            ema20_touch and
            row["close"] < row["ema20"]
        )

        ema50_rejection = (
            ema50_touch and
            row["close"] < row["ema50"]
        )

    rows.append({
        "signal_time": t,
        "direction": direction,
        "directional_move_atr": directional_move_atr,
        "body_atr": body_atr,
        "ema20_touch": ema20_touch,
        "ema50_touch": ema50_touch,
        "ema20_rejection": ema20_rejection,
        "ema50_rejection": ema50_rejection,
        "r_multiple": trade["r_multiple"],
        "stop_pips": trade["stop_pips"],
    })


out = pd.DataFrame(rows)

print("SCALP TRAIN - H1 PULLBACK STRUCTURE")
print()
print("Trades classified:", len(out))
print()

print("PREVIOUS 6-HOUR DIRECTIONAL MOVE")

out["move_bucket"] = pd.cut(
    out["directional_move_atr"],
    bins=[-100, -1, -.5, 0, .5, 1, 1.5, 2, 100],
    right=False
)

print(
    out.groupby("move_bucket", observed=True)
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
print("EMA20 TOUCH / REJECTION")

print(
    out.groupby("ema20_touch")
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

print(
    out.groupby("ema20_rejection")
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
print("EMA50 TOUCH / REJECTION")

print(
    out.groupby("ema50_touch")
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

print(
    out.groupby("ema50_rejection")
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
print("CANDLE BODY SIZE")

out["body_bucket"] = pd.cut(
    out["body_atr"],
    bins=[0, .25, .5, .75, 1, 1.5, 2, 100],
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
print("SAVED: diagnose_scalp_pullback_structure.csv")

out.to_csv(
    "diagnose_scalp_pullback_structure.csv",
    index=False
)
