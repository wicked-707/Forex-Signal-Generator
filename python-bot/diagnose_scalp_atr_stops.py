import pandas as pd
import numpy as np
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

# Spread already used by the existing backtest.
SPREAD_PIPS = 1.2
PIP_SIZE = 0.0001

multipliers = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

results = []

for multiplier in multipliers:

    total_R = 0.0
    wins = 0
    losses = 0
    trades_count = 0

    for _, trade in trades.iterrows():

        signal_time = pd.to_datetime(
            trade["signal_time"],
            utc=True
        )

        entry_time = pd.to_datetime(
            trade["entry_time"],
            utc=True
        )

        # ATR available at signal time.
        available = m15.loc[:signal_time]

        if available.empty:
            continue

        atr = available.iloc[-1]["atr"]

        if pd.isna(atr):
            continue

        entry_price = float(trade["entry_price"])
        direction = trade["direction"]

        stop_distance = multiplier * atr

        if direction == "BUY":
            stop = entry_price - stop_distance
            tp = entry_price + stop_distance * 1.5
        else:
            stop = entry_price + stop_distance
            tp = entry_price - stop_distance * 1.5

        future = m15.loc[entry_time:]

        if future.empty:
            continue

        outcome = None
        exit_price = None

        for timestamp, candle in future.iterrows():

            high = candle["high"]
            low = candle["low"]

            if direction == "BUY":

                hit_sl = low <= stop
                hit_tp = high >= tp

                # Conservative assumption:
                # if both occur in the same M15 candle,
                # SL is assumed first.
                if hit_sl:
                    outcome = "SL"
                    exit_price = stop
                    break

                if hit_tp:
                    outcome = "TP"
                    exit_price = tp
                    break

            else:

                hit_sl = high >= stop
                hit_tp = low <= tp

                if hit_sl:
                    outcome = "SL"
                    exit_price = stop
                    break

                if hit_tp:
                    outcome = "TP"
                    exit_price = tp
                    break

        if outcome is None:
            continue

        stop_pips = stop_distance / PIP_SIZE

        # Risk-normalized result.
        if outcome == "TP":
            gross_R = 1.5
            wins += 1
        else:
            gross_R = -1.0
            losses += 1

        # Spread cost expressed as fraction of stop risk.
        spread_R = SPREAD_PIPS / stop_pips

        r_result = gross_R - spread_R

        total_R += r_result
        trades_count += 1

    avg_R = total_R / trades_count if trades_count else 0
    win_rate = wins / trades_count * 100 if trades_count else 0

    results.append({
        "atr_multiplier": multiplier,
        "trades": trades_count,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_R": avg_R,
        "total_R": total_R,
    })


out = pd.DataFrame(results)

print("SCALP TRAIN - ATR STOP ROBUSTNESS")
print()
print(out.round(3).to_string(index=False))

print()
print("SAVED: diagnose_scalp_atr_stops.csv")

out.to_csv(
    "diagnose_scalp_atr_stops.csv",
    index=False
)
