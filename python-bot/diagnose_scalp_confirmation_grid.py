import pandas as pd
import pandas_ta_classic as ta

trades = pd.read_csv("backtest_scalp_trades.csv")

m15 = pd.read_parquet("data/EURUSD_M15.parquet")

m15["time"] = pd.to_datetime(
    m15["time"],
    utc=True
)

m15 = (
    m15
    .set_index("time")
    .sort_index()
)

m15["atr"] = ta.atr(
    m15["high"],
    m15["low"],
    m15["close"],
    length=14
)

TRAIN_END = pd.Timestamp(
    "2024-12-31 23:59:59",
    tz="UTC"
)

SPREAD_PIPS = 1.2
PIP_SIZE = 0.0001

STOP_MULTS = [
    1.0,
    1.25,
    1.5,
    1.75,
    2.0
]

RR_VALUES = [
    0.75,
    1.0,
    1.25,
    1.5,
    2.0
]

results = []

for stop_mult in STOP_MULTS:

    for rr in RR_VALUES:

        total_R = 0.0
        wins = 0
        losses = 0
        count = 0

        for _, trade in trades.iterrows():

            signal_time = pd.to_datetime(
                trade["signal_time"],
                utc=True
            )

            direction = trade["direction"]

            try:
                signal_idx = m15.index.get_loc(
                    signal_time
                )
            except KeyError:
                continue

            # Need two confirming candles.
            first_idx = signal_idx + 1
            second_idx = signal_idx + 2
            entry_idx = signal_idx + 3

            if entry_idx >= len(m15):
                continue

            first = m15.iloc[first_idx]
            second = m15.iloc[second_idx]

            if (
                m15.index[first_idx] > TRAIN_END
                or
                m15.index[second_idx] > TRAIN_END
            ):
                continue

            # ------------------------------------------------
            # Two-candle directional confirmation
            # ------------------------------------------------

            if direction == "BUY":

                confirmed = (
                    first["close"] > first["open"]
                    and
                    second["close"] > second["open"]
                )

            else:

                confirmed = (
                    first["close"] < first["open"]
                    and
                    second["close"] < second["open"]
                )

            if not confirmed:
                continue

            entry_row = m15.iloc[entry_idx]

            if m15.index[entry_idx] > TRAIN_END:
                continue

            entry_price = float(
                entry_row["open"]
            )

            atr = m15.iloc[signal_idx]["atr"]

            if pd.isna(atr) or atr <= 0:
                continue

            stop_distance = (
                stop_mult * atr
            )

            if direction == "BUY":

                stop = (
                    entry_price
                    - stop_distance
                )

                tp = (
                    entry_price
                    + stop_distance * rr
                )

            else:

                stop = (
                    entry_price
                    + stop_distance
                )

                tp = (
                    entry_price
                    - stop_distance * rr
                )

            outcome = None

            future = m15.iloc[entry_idx:]

            for timestamp, candle in future.iterrows():

                if timestamp > TRAIN_END:
                    break

                high = float(candle["high"])
                low = float(candle["low"])

                if direction == "BUY":

                    hit_sl = low <= stop
                    hit_tp = high >= tp

                else:

                    hit_sl = high >= stop
                    hit_tp = low <= tp

                # Conservative SL-first assumption.
                if hit_sl:

                    outcome = "SL"
                    break

                if hit_tp:

                    outcome = "TP"
                    break

            if outcome is None:
                continue

            stop_pips = (
                stop_distance / PIP_SIZE
            )

            spread_R = (
                SPREAD_PIPS / stop_pips
            )

            if outcome == "TP":

                gross_R = rr
                wins += 1

            else:

                gross_R = -1.0
                losses += 1

            total_R += (
                gross_R - spread_R
            )

            count += 1

        avg_R = (
            total_R / count
            if count
            else 0
        )

        win_rate = (
            wins / count * 100
            if count
            else 0
        )

        results.append({
            "stop_atr": stop_mult,
            "tp_rr": rr,
            "trades": count,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "avg_R": avg_R,
            "total_R": total_R
        })

out = pd.DataFrame(results)

out = out.sort_values(
    "avg_R",
    ascending=False
)

print()
print(
    "SCALP TWO-CANDLE CONFIRMATION GRID"
)
print(
    "TRAIN ONLY"
)
print()
print(
    out.round(3).to_string(index=False)
)

print()
print(
    "SAVED: diagnose_scalp_confirmation_grid.csv"
)

out.to_csv(
    "diagnose_scalp_confirmation_grid.csv",
    index=False
)
