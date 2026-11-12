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

HORIZONS = [4, 8, 16, 32]

TESTS = [
    (0.5, -0.5),
    (1.0, -0.5),
    (1.0, -1.0),
    (1.5, -1.0),
]

results = []

for horizon in HORIZONS:

    for favorable_level, adverse_level in TESTS:

        total = 0
        favorable_first = 0
        adverse_first = 0
        neither = 0

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
            atr = m15.iloc[idx]["atr"]

            if pd.isna(atr) or atr <= 0:
                continue

            future = m15.iloc[
                idx + 1:idx + horizon + 1
            ]

            if future.empty:
                continue

            total += 1

            outcome = None

            for _, candle in future.iterrows():

                if direction == "BUY":

                    favorable_hit = (
                        candle["high"]
                        >= entry + favorable_level * atr
                    )

                    adverse_hit = (
                        candle["low"]
                        <= entry + adverse_level * atr
                    )

                else:

                    favorable_hit = (
                        candle["low"]
                        <= entry - favorable_level * atr
                    )

                    adverse_hit = (
                        candle["high"]
                        >= entry - adverse_level * atr
                    )

                # Conservative assumption:
                # if both levels occur in the same candle,
                # adverse is counted first.
                if adverse_hit:
                    outcome = "ADVERSE_FIRST"
                    break

                if favorable_hit:
                    outcome = "FAVORABLE_FIRST"
                    break

            if outcome == "FAVORABLE_FIRST":
                favorable_first += 1

            elif outcome == "ADVERSE_FIRST":
                adverse_first += 1

            else:
                neither += 1

        results.append({
            "horizon_bars": horizon,
            "minutes": horizon * 15,
            "favorable_level_ATR": favorable_level,
            "adverse_level_ATR": adverse_level,
            "signals": total,
            "favorable_first_pct": (
                favorable_first / total * 100
                if total else 0
            ),
            "adverse_first_pct": (
                adverse_first / total * 100
                if total else 0
            ),
            "neither_pct": (
                neither / total * 100
                if total else 0
            ),
        })

out = pd.DataFrame(results)

print("SCALP TRAIN - FAVORABLE VS ADVERSE SEQUENCE")
print()
print(out.round(3).to_string(index=False))
print()
print("SAVED: diagnose_scalp_sequence.csv")

out.to_csv(
    "diagnose_scalp_sequence.csv",
    index=False
)
