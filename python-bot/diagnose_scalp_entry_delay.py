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

SPREAD_PIPS = 1.2
PIP_SIZE = 0.0001

STOP_MULT = 1.5
RR = 1.0

DELAY_BARS = [0, 1, 2, 3, 4]

results = []

for delay in DELAY_BARS:

    total_R = 0.0
    wins = 0
    losses = 0
    count = 0

    for _, trade in trades.iterrows():

        signal_time = pd.to_datetime(
            trade["signal_time"], utc=True
        )

        direction = trade["direction"]

        try:
            signal_idx = m15.index.get_loc(signal_time)
        except KeyError:
            continue

        entry_idx = signal_idx + 1 + delay

        if entry_idx >= len(m15):
            continue

        entry_row = m15.iloc[entry_idx]

        entry_time = m15.index[entry_idx]
        entry_price = float(entry_row["open"])

        # ATR from the signal candle.
        signal_atr = m15.iloc[signal_idx]["atr"]

        if pd.isna(signal_atr) or signal_atr <= 0:
            continue

        stop_distance = STOP_MULT * signal_atr

        if direction == "BUY":
            stop = entry_price - stop_distance
            tp = entry_price + stop_distance * RR
        else:
            stop = entry_price + stop_distance
            tp = entry_price - stop_distance * RR

        future = m15.iloc[entry_idx:]

        outcome = None

        for _, candle in future.iterrows():

            high = candle["high"]
            low = candle["low"]

            if direction == "BUY":

                hit_sl = low <= stop
                hit_tp = high >= tp

                if hit_sl:
                    outcome = "SL"
                    break

                if hit_tp:
                    outcome = "TP"
                    break

            else:

                hit_sl = high >= stop
                hit_tp = low <= tp

                if hit_sl:
                    outcome = "SL"
                    break

                if hit_tp:
                    outcome = "TP"
                    break

        if outcome is None:
            continue

        stop_pips = stop_distance / PIP_SIZE

        spread_R = SPREAD_PIPS / stop_pips

        if outcome == "TP":
            gross_R = RR
            wins += 1
        else:
            gross_R = -1.0
            losses += 1

        total_R += gross_R - spread_R
        count += 1

    avg_R = total_R / count if count else 0
    win_rate = wins / count * 100 if count else 0

    results.append({
        "delay_bars": delay,
        "delay_minutes": delay * 15,
        "trades": count,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_R": avg_R,
        "total_R": total_R
    })

out = pd.DataFrame(results)

print("SCALP TRAIN - ENTRY DELAY SENSITIVITY")
print()
print(out.round(3).to_string(index=False))
print()
print("SAVED: diagnose_scalp_entry_delay.csv")

out.to_csv(
    "diagnose_scalp_entry_delay.csv",
    index=False
)
