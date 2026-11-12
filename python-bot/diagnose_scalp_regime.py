import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

def load_tf(tf):
    df = pd.read_parquet(f"data/EURUSD_{tf}.parquet")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()

    df["ema_mid"] = ta.ema(df["close"], length=50)
    df["ema_slow"] = ta.ema(df["close"], length=200)
    df["adx"] = ta.adx(
        df["high"],
        df["low"],
        df["close"],
        length=14
    )["ADX_14"]

    return df


d1 = load_tf("D1")
h4 = load_tf("H4")

# Match the backtest's anti-lookahead behavior:
# HTF candle values are shifted one row before alignment.
d1_shifted = d1.shift(1)
h4_shifted = h4.shift(1)

rows = []

for _, trade in trades.iterrows():

    t = pd.to_datetime(trade["signal_time"], utc=True)

    d1_available = d1_shifted.loc[:t]
    h4_available = h4_shifted.loc[:t]

    if d1_available.empty or h4_available.empty:
        continue

    d = d1_available.iloc[-1]
    h = h4_available.iloc[-1]

    required = [
        d["ema_mid"],
        d["ema_slow"],
        d["adx"],
        h["ema_mid"],
        h["close"],
    ]

    if any(pd.isna(x) for x in required):
        continue

    # D1 trend
    if d["ema_mid"] > d["ema_slow"]:
        d1_trend = "BULLISH"
    elif d["ema_mid"] < d["ema_slow"]:
        d1_trend = "BEARISH"
    else:
        d1_trend = "FLAT"

    # H4 trend relative to EMA50
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

    rows.append({
        "signal_time": t,
        "direction": trade["direction"],
        "d1_trend": d1_trend,
        "h4_trend": h4_trend,
        "alignment": alignment,
        "d1_adx": d["adx"],
        "r_multiple": trade["r_multiple"],
        "stop_pips": trade["stop_pips"],
    })


out = pd.DataFrame(rows)

print("SCALP TRAIN - EXACT D1/H4 REGIME ANALYSIS")
print()
print("Trades classified:", len(out))
print()

print("D1 + H4 ALIGNMENT")
print(
    out.groupby("alignment")
    .agg(
        trades=("r_multiple", "size"),
        win_rate=("r_multiple", lambda x: (x > 0).mean() * 100),
        avg_R=("r_multiple", "mean"),
        total_R=("r_multiple", "sum"),
        avg_stop_pips=("stop_pips", "mean"),
    )
    .round(3)
    .sort_values("avg_R", ascending=False)
    .to_string()
)

print()
print("D1/H4 ALIGNMENT BY TRADE DIRECTION")
print(
    out.groupby(["alignment", "direction"])
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
print("D1 ADX WITH D1/H4 ALIGNMENT")
print(
    out.groupby(["alignment", pd.cut(
        out["d1_adx"],
        bins=[0, 15, 20, 25, 30, 40, 100],
        right=False
    )], observed=True)
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
print("SAVED: diagnose_scalp_regime.csv")

out.to_csv("diagnose_scalp_regime.csv", index=False)
