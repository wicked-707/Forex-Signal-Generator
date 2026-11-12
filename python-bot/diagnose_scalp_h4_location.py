import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

def load_tf(tf):
    df = pd.read_parquet(f"data/EURUSD_{tf}.parquet")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()

    df["ema_fast"] = ta.ema(df["close"], length=20)
    df["ema_mid"] = ta.ema(df["close"], length=50)
    df["ema_slow"] = ta.ema(df["close"], length=200)

    df["atr"] = ta.atr(
        df["high"],
        df["low"],
        df["close"],
        length=14
    )

    return df


d1 = load_tf("D1")
h4 = load_tf("H4")

# Match historical anti-lookahead behavior.
d1 = d1.shift(1)
h4 = h4.shift(1)

rows = []

for _, trade in trades.iterrows():

    t = pd.to_datetime(trade["signal_time"], utc=True)

    d1_available = d1.loc[:t]
    h4_available = h4.loc[:t]

    if d1_available.empty or h4_available.empty:
        continue

    d = d1_available.iloc[-1]
    h = h4_available.iloc[-1]

    required = [
        d["ema_mid"],
        d["ema_slow"],
        h["close"],
        h["ema_fast"],
        h["ema_mid"],
        h["ema_slow"],
        h["atr"],
    ]

    if any(pd.isna(x) for x in required):
        continue

    # Reconstruct D1/H4 regime.
    if d["ema_mid"] > d["ema_slow"]:
        d1_trend = "BULLISH"
    elif d["ema_mid"] < d["ema_slow"]:
        d1_trend = "BEARISH"
    else:
        d1_trend = "FLAT"

    if h["close"] > h["ema_mid"]:
        h4_trend = "BULLISH"
    elif h["close"] < h["ema_mid"]:
        h4_trend = "BEARISH"
    else:
        h4_trend = "FLAT"

    if d1_trend == h4_trend:
        alignment = d1_trend
    else:
        alignment = "MIXED"

    # H4 price location in ATR units.
    dist_ema20 = abs(h["close"] - h["ema_fast"]) / h["atr"]
    dist_ema50 = abs(h["close"] - h["ema_mid"]) / h["atr"]
    dist_ema200 = abs(h["close"] - h["ema_slow"]) / h["atr"]

    # Directional extension.
    if trade["direction"] == "BUY":
        extension_ema20 = (h["close"] - h["ema_fast"]) / h["atr"]
        extension_ema50 = (h["close"] - h["ema_mid"]) / h["atr"]
    else:
        extension_ema20 = (h["ema_fast"] - h["close"]) / h["atr"]
        extension_ema50 = (h["ema_mid"] - h["close"]) / h["atr"]

    rows.append({
        "signal_time": t,
        "direction": trade["direction"],
        "alignment": alignment,
        "d1_trend": d1_trend,
        "h4_trend": h4_trend,
        "dist_ema20_atr": dist_ema20,
        "dist_ema50_atr": dist_ema50,
        "dist_ema200_atr": dist_ema200,
        "extension_ema20_atr": extension_ema20,
        "extension_ema50_atr": extension_ema50,
        "stop_pips": trade["stop_pips"],
        "r_multiple": trade["r_multiple"],
    })


out = pd.DataFrame(rows)

print("SCALP TRAIN - H4 ENTRY LOCATION ANALYSIS")
print()
print("Trades classified:", len(out))
print()

print("H4 EMA20 DISTANCE")
out["ema20_bucket"] = pd.cut(
    out["dist_ema20_atr"],
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
print("H4 EMA50 DISTANCE")
out["ema50_bucket"] = pd.cut(
    out["dist_ema50_atr"],
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
print("H4 ENTRY LOCATION BY REGIME")
print(
    out.groupby(["alignment", "direction"])
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
        avg_ema20_dist=("dist_ema20_atr", "mean"),
        avg_ema50_dist=("dist_ema50_atr", "mean"),
    )
    .round(3)
    .to_string()
)

print()
print("SAVED: diagnose_scalp_h4_location.csv")

out.to_csv("diagnose_scalp_h4_location.csv", index=False)
