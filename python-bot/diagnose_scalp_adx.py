import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

d1 = pd.read_parquet("data/EURUSD_D1.parquet")
d1["time"] = pd.to_datetime(d1["time"], utc=True)
d1 = d1.set_index("time").sort_index()

d1["ema_mid"] = ta.ema(d1["close"], length=50)
d1["ema_slow"] = ta.ema(d1["close"], length=200)
d1["adx"] = ta.adx(
    d1["high"],
    d1["low"],
    d1["close"],
    length=14
)["ADX_14"]

rows = []

for _, trade in trades.iterrows():
    t = pd.to_datetime(trade["signal_time"], utc=True)

    # Use the most recent completed D1 candle at/before signal time.
    available = d1.loc[:t]

    if available.empty:
        continue

    row = available.iloc[-1]

    if pd.isna(row["adx"]) or pd.isna(row["ema_mid"]) or pd.isna(row["ema_slow"]):
        continue

    if row["ema_mid"] > row["ema_slow"]:
        d1_trend = "BULLISH"
    elif row["ema_mid"] < row["ema_slow"]:
        d1_trend = "BEARISH"
    else:
        d1_trend = "FLAT"

    rows.append({
        "signal_time": t,
        "direction": trade["direction"],
        "d1_trend": d1_trend,
        "d1_adx": row["adx"],
        "r_multiple": trade["r_multiple"],
        "stop_pips": trade["stop_pips"],
    })

out = pd.DataFrame(rows)

print("SCALP TRAIN - D1 ADX / REGIME ANALYSIS")
print()
print("Trades classified:", len(out))
print()

print("D1 ADX BUCKETS")

out["adx_bucket"] = pd.cut(
    out["d1_adx"],
    bins=[0, 15, 20, 25, 30, 40, 100],
    right=False
)

print(
    out.groupby("adx_bucket", observed=True)
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
        avg_stop_pips=("stop_pips", "mean"),
    )
    .round(3)
    .to_string()
)

print()
print("D1 TREND")
print(
    out.groupby("d1_trend")
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
print("D1 ADX THRESHOLD SENSITIVITY")

for threshold in [15, 18, 20, 22, 25, 30]:
    subset = out[out["d1_adx"] >= threshold]

    print(
        "ADX >= {} | trades={} | win_rate={:.2f}% | avg_R={:.3f} | total_R={:.3f}".format(
            threshold,
            len(subset),
            (subset["r_multiple"] > 0).mean() * 100 if len(subset) else 0,
            subset["r_multiple"].mean() if len(subset) else 0,
            subset["r_multiple"].sum() if len(subset) else 0,
        )
    )

out.to_csv("diagnose_scalp_adx.csv", index=False)

print()
print("Saved: diagnose_scalp_adx.csv")
