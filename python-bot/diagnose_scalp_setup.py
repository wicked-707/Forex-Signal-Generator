import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

m15 = pd.read_parquet("data/EURUSD_M15.parquet")
m15["time"] = pd.to_datetime(m15["time"], utc=True)
m15 = m15.set_index("time").sort_index()

m15["ema_fast"] = ta.ema(m15["close"], length=20)
m15["ema_mid"] = ta.ema(m15["close"], length=50)
m15["ema_slow"] = ta.ema(m15["close"], length=200)
m15["rsi"] = ta.rsi(m15["close"], length=14)
m15["atr"] = ta.atr(m15["high"], m15["low"], m15["close"], length=14)

rows = []

for _, trade in trades.iterrows():
    t = pd.to_datetime(trade["signal_time"], utc=True)

    if t not in m15.index:
        continue

    row = m15.loc[t]

    atr = row["atr"]

    if pd.isna(atr) or atr <= 0:
        continue

    close = row["close"]
    direction = trade["direction"]

    distance_ema20_atr = abs(close - row["ema_fast"]) / atr
    distance_ema50_atr = abs(close - row["ema_mid"]) / atr
    distance_ema200_atr = abs(close - row["ema_slow"]) / atr

    if direction == "BUY":
        ema200_aligned = close > row["ema_slow"]
        ema20_aligned = close > row["ema_fast"]
        ema50_aligned = close > row["ema_mid"]
    else:
        ema200_aligned = close < row["ema_slow"]
        ema20_aligned = close < row["ema_fast"]
        ema50_aligned = close < row["ema_mid"]

    rows.append({
        "direction": direction,
        "confidence": trade["confidence"],
        "r_multiple": trade["r_multiple"],
        "stop_pips": trade["stop_pips"],
        "rsi": row["rsi"],
        "atr_pips": atr / 0.0001,
        "distance_ema20_atr": distance_ema20_atr,
        "distance_ema50_atr": distance_ema50_atr,
        "distance_ema200_atr": distance_ema200_atr,
        "ema200_aligned": ema200_aligned,
        "ema20_aligned": ema20_aligned,
        "ema50_aligned": ema50_aligned,
    })

out = pd.DataFrame(rows)

print("SCALP TRAIN - SETUP ANALYSIS")
print()
print("Trades classified:", len(out))
print()

def summarize(df, label):
    print(label)
    print("Trades:", len(df))
    if len(df):
        print("Win rate: {:.2f}%".format((df["r_multiple"] > 0).mean() * 100))
        print("Avg R: {:.3f}".format(df["r_multiple"].mean()))
        print("Total R: {:.3f}".format(df["r_multiple"].sum()))
    print()

summarize(out[out["ema200_aligned"]], "EMA200 ALIGNED")
summarize(out[~out["ema200_aligned"]], "EMA200 NOT ALIGNED")

print("RSI BUCKETS")
out["rsi_bucket"] = pd.cut(
    out["rsi"],
    bins=[0, 40, 45, 50, 55, 60, 100],
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
print("DISTANCE FROM EMA20")
out["ema20_bucket"] = pd.cut(
    out["distance_ema20_atr"],
    bins=[0, 0.25, 0.50, 0.75, 1.00, 2.00, 100],
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
print("DISTANCE FROM EMA50")
out["ema50_bucket"] = pd.cut(
    out["distance_ema50_atr"],
    bins=[0, 0.25, 0.50, 0.75, 1.00, 2.00, 100],
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
print("EMA ALIGNMENT")
print(
    out.groupby(["ema20_aligned", "ema50_aligned"])
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
    )
    .round(3)
    .to_string()
)

out.to_csv("diagnose_scalp_setup.csv", index=False)

print()
print("Saved: diagnose_scalp_setup.csv")
