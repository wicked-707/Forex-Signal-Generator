import pandas as pd
import pandas_ta_classic as ta

# ============================================================
# SCALP CONFIRMATION DIAGNOSTIC
# TRAIN ONLY
#
# Baseline:
#   Entry = next M15 open after signal
#
# Candidate confirmations:
#   1. 15-minute delay
#   2. Trigger-candle breakout
#   3. Close beyond trigger candle
#   4. Two consecutive confirming candles
#
# Fixed risk model:
#   Stop = 1.5 ATR
#   TP   = 1.0R
#   Spread = 1.2 pips
# ============================================================

TRAIN_END = pd.Timestamp("2024-12-31 23:59:59", tz="UTC")

SPREAD_PIPS = 1.2
PIP_SIZE = 0.0001

STOP_MULT = 1.5
RR = 1.0

trades = pd.read_csv("backtest_scalp_trades.csv")

trades["signal_time"] = pd.to_datetime(
    trades["signal_time"], utc=True
)

# ------------------------------------------------------------
# Load M15 data
# ------------------------------------------------------------

m15 = pd.read_parquet("data/EURUSD_M15.parquet")

m15["time"] = pd.to_datetime(
    m15["time"], utc=True
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

# ------------------------------------------------------------
# Strict TRAIN signals only
# ------------------------------------------------------------

trades = trades[
    trades["signal_time"] <= TRAIN_END
].copy()

print()
print("SCALP CONFIRMATION DIAGNOSTIC")
print("--------------------------------")
print(f"TRAIN signals: {len(trades)}")
print(f"Train end:     {TRAIN_END}")
print()

# ------------------------------------------------------------
# Helper
# ------------------------------------------------------------

def evaluate_trade(
    direction,
    signal_idx,
    entry_idx,
    signal_atr
):

    if entry_idx >= len(m15):
        return None

    entry_row = m15.iloc[entry_idx]

    entry_time = m15.index[entry_idx]

    # Never enter after TRAIN.
    if entry_time > TRAIN_END:
        return None

    entry_price = float(entry_row["open"])

    if pd.isna(signal_atr) or signal_atr <= 0:
        return None

    stop_distance = STOP_MULT * signal_atr

    if direction == "BUY":

        stop = entry_price - stop_distance
        tp = entry_price + stop_distance * RR

    else:

        stop = entry_price + stop_distance
        tp = entry_price - stop_distance * RR

    future = m15.iloc[entry_idx:]

    outcome = None
    exit_time = None

    for timestamp, candle in future.iterrows():

        # Do not allow the hypothetical trade to cross TRAIN.
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

        # Conservative intrabar assumption:
        # SL gets priority if both occur in same candle.
        if hit_sl:

            outcome = "SL"
            exit_time = timestamp
            break

        if hit_tp:

            outcome = "TP"
            exit_time = timestamp
            break

    if outcome is None:
        return None

    stop_pips = stop_distance / PIP_SIZE

    spread_R = SPREAD_PIPS / stop_pips

    if outcome == "TP":

        gross_R = RR

    else:

        gross_R = -1.0

    result_R = gross_R - spread_R

    return {
        "entry_time": entry_time,
        "entry_price": entry_price,
        "exit_time": exit_time,
        "outcome": outcome,
        "r_result": result_R
    }


# ------------------------------------------------------------
# Confirmation methods
# ------------------------------------------------------------

methods = [
    "BASELINE",
    "DELAY_15M",
    "BREAK_TRIGGER",
    "CLOSE_CONFIRM",
    "TWO_CANDLE_CONFIRM"
]

results = []


# ============================================================
# Process each method
# ============================================================

for method in methods:

    total_R = 0.0
    wins = 0
    losses = 0
    count = 0

    buy_count = 0
    sell_count = 0

    for _, trade in trades.iterrows():

        signal_time = trade["signal_time"]
        direction = trade["direction"]

        try:

            signal_idx = m15.index.get_loc(signal_time)

        except KeyError:

            continue

        if signal_idx >= len(m15):
            continue

        signal_row = m15.iloc[signal_idx]

        signal_atr = signal_row["atr"]

        if pd.isna(signal_atr) or signal_atr <= 0:
            continue

        # ----------------------------------------------------
        # BASELINE
        # ----------------------------------------------------

        if method == "BASELINE":

            entry_idx = signal_idx + 1

            result = evaluate_trade(
                direction,
                signal_idx,
                entry_idx,
                signal_atr
            )

        # ----------------------------------------------------
        # 15 MINUTE DELAY
        # ----------------------------------------------------

        elif method == "DELAY_15M":

            entry_idx = signal_idx + 2

            result = evaluate_trade(
                direction,
                signal_idx,
                entry_idx,
                signal_atr
            )

        # ----------------------------------------------------
        # BREAK TRIGGER
        #
        # Wait until a later candle breaks the signal candle's
        # high for BUY or low for SELL.
        # Entry occurs at the breakout price.
        # ----------------------------------------------------

        elif method == "BREAK_TRIGGER":

            trigger_high = float(signal_row["high"])
            trigger_low = float(signal_row["low"])

            result = None

            for idx in range(signal_idx + 1, len(m15)):

                candle = m15.iloc[idx]
                timestamp = m15.index[idx]

                if timestamp > TRAIN_END:
                    break

                if direction == "BUY":

                    if candle["high"] >= trigger_high:

                        # Conservative executable approximation:
                        # enter at trigger level.
                        entry_price = trigger_high

                        stop_distance = STOP_MULT * signal_atr

                        stop = (
                            entry_price - stop_distance
                        )

                        tp = (
                            entry_price
                            + stop_distance * RR
                        )

                        outcome = None

                        for j in range(idx, len(m15)):

                            ts = m15.index[j]

                            if ts > TRAIN_END:
                                break

                            c = m15.iloc[j]

                            if c["low"] <= stop:

                                outcome = "SL"
                                break

                            if c["high"] >= tp:

                                outcome = "TP"
                                break

                        if outcome is not None:

                            stop_pips = (
                                stop_distance / PIP_SIZE
                            )

                            spread_R = (
                                SPREAD_PIPS / stop_pips
                            )

                            gross_R = (
                                RR
                                if outcome == "TP"
                                else -1.0
                            )

                            result = {
                                "entry_time": timestamp,
                                "entry_price": entry_price,
                                "outcome": outcome,
                                "r_result": (
                                    gross_R - spread_R
                                )
                            }

                        break

                else:

                    if candle["low"] <= trigger_low:

                        entry_price = trigger_low

                        stop_distance = STOP_MULT * signal_atr

                        stop = (
                            entry_price + stop_distance
                        )

                        tp = (
                            entry_price
                            - stop_distance * RR
                        )

                        outcome = None

                        for j in range(idx, len(m15)):

                            ts = m15.index[j]

                            if ts > TRAIN_END:
                                break

                            c = m15.iloc[j]

                            if c["high"] >= stop:

                                outcome = "SL"
                                break

                            if c["low"] <= tp:

                                outcome = "TP"
                                break

                        if outcome is not None:

                            stop_pips = (
                                stop_distance / PIP_SIZE
                            )

                            spread_R = (
                                SPREAD_PIPS / stop_pips
                            )

                            gross_R = (
                                RR
                                if outcome == "TP"
                                else -1.0
                            )

                            result = {
                                "entry_time": timestamp,
                                "entry_price": entry_price,
                                "outcome": outcome,
                                "r_result": (
                                    gross_R - spread_R
                                )
                            }

                        break

        # ----------------------------------------------------
        # CLOSE CONFIRM
        #
        # BUY:
        #   confirmation candle closes above signal close
        #
        # SELL:
        #   confirmation candle closes below signal close
        #
        # Entry = following candle open.
        # ----------------------------------------------------

        elif method == "CLOSE_CONFIRM":

            confirm_idx = signal_idx + 1

            result = None

            if confirm_idx < len(m15):

                confirm = m15.iloc[confirm_idx]

                if m15.index[confirm_idx] <= TRAIN_END:

                    if direction == "BUY":

                        confirmed = (
                            confirm["close"]
                            > signal_row["close"]
                        )

                    else:

                        confirmed = (
                            confirm["close"]
                            < signal_row["close"]
                        )

                    if confirmed:

                        entry_idx = confirm_idx + 1

                        result = evaluate_trade(
                            direction,
                            signal_idx,
                            entry_idx,
                            signal_atr
                        )

        # ----------------------------------------------------
        # TWO CANDLE CONFIRM
        #
        # Both candles after the signal must continue in the
        # predicted direction.
        #
        # BUY:
        #   both close > open
        #
        # SELL:
        #   both close < open
        #
        # Entry = third candle open.
        # ----------------------------------------------------

        elif method == "TWO_CANDLE_CONFIRM":

            first_idx = signal_idx + 1
            second_idx = signal_idx + 2

            result = None

            if second_idx < len(m15):

                first = m15.iloc[first_idx]
                second = m15.iloc[second_idx]

                if (
                    m15.index[first_idx] <= TRAIN_END
                    and
                    m15.index[second_idx] <= TRAIN_END
                ):

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

                    if confirmed:

                        entry_idx = second_idx + 1

                        result = evaluate_trade(
                            direction,
                            signal_idx,
                            entry_idx,
                            signal_atr
                        )

        # ----------------------------------------------------
        # Record
        # ----------------------------------------------------

        if result is None:
            continue

        count += 1

        total_R += result["r_result"]

        if result["outcome"] == "TP":
            wins += 1
        else:
            losses += 1

        if direction == "BUY":
            buy_count += 1
        else:
            sell_count += 1

    avg_R = total_R / count if count else 0

    win_rate = (
        wins / count * 100
        if count
        else 0
    )

    results.append({
        "method": method,
        "trades": count,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_R": avg_R,
        "total_R": total_R,
        "buy_trades": buy_count,
        "sell_trades": sell_count
    })


# ============================================================
# Output
# ============================================================

out = pd.DataFrame(results)

print()
print("RESULTS")
print("-------")
print(
    out.round(3).to_string(index=False)
)

print()
print(
    "SAVED: diagnose_scalp_confirmation.csv"
)

out.to_csv(
    "diagnose_scalp_confirmation.csv",
    index=False
)
