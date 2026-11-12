import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

m15 = pd.read_parquet("data/EURUSD_M15.parquet")
m15["time"] = pd.to_datetime(m15["time"], utc=True)
m15 = m15.set_index("time").sort_index()

m15["atr"] = ta.atr(
    m15["high"],
    m15["low"],
    m15["close"],
    length=14
)

HORIZONS = [1, 2, 4, 8, 16, 32]

results = []

for horizon in HORIZONS:

    total = 0
    favorable = 0
    unfavorable = 0
    one_atr = 0

    moves = []

    for _, trade in trades.iterrows():

        entry_time = pd.to_datetime(
            trade["entry_time"], utc=True
        )

        direction = trade["direction"]

        try:
            idx = m15.index.get_loc(entry_time)
        except KeyError:
            continue

        if idx + horizon >= len(m15):
            continue

        entry = float(trade["entry_price"])

        entry_atr = m15.iloc[idx]["atr"]

        if pd.isna(entry_atr) or entry_atr <= 0:
            continue

        future = m15.iloc[idx + 1:idx + horizon + 1]

        if future.empty:
            continue

        if direction == "BUY":

            best_move = (
                future["high"].max() - entry
            )

            worst_move = (
                future["low"].min() - entry
            )

        else:

            best_move = (
                entry - future["low"].min()
            )

            worst_move = (
                entry - future["high"].max()
            )

        favorable_r = best_move / entry_atr
        unfavorable_r = worst_move / entry_atr

        moves.append(favorable_r)

        total += 1

        if favorable_r > 0:
            favorable += 1

        if worst_move < 0:
            unfavorable += 1

        if favorable_r >= 1.0:
            one_atr += 1

    results.append({
        "horizon_bars": horizon,
        "minutes": horizon * 15,
        "signals": total,
        "positive_move_pct": (
            favorable / total * 100
            if total else 0
        ),
        "adverse_move_pct": (
            unfavorable / total * 100
            if total else 0
        ),
        "reach_1ATR_pct": (
            one_atr / total * 100
            if total else 0
        ),
        "avg_favorable_ATR": (
            sum(moves) / len(moves)
            if moves else 0
        ),
        "median_favorable_ATR": (
            pd.Series(moves).median()
            if moves else 0
        ),
    })

out = pd.DataFrame(results)

print("SCALP TRAIN - ENTRY DIRECTIONAL EDGE")
print()
print(out.round(3).to_string(index=False))
print()
print("SAVED: diagnose_scalp_directional_edge.csv")

out.to_csv(
    "diagnose_scalp_directional_edge.csv",
    index=False
)
