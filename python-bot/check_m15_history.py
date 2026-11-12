import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

if not mt5.initialize():
    print("MT5 initialization failed:", mt5.last_error())
    raise SystemExit(1)

tests = [
    ("2022-01-01", "2022-03-31"),
    ("2022-04-01", "2022-06-30"),
    ("2022-07-01", "2022-09-01"),
    ("2022-09-01", "2022-10-01"),
]

for start, end in tests:
    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)

    rates = mt5.copy_rates_range(
        "EURUSD",
        mt5.TIMEFRAME_M15,
        start_dt,
        end_dt,
    )

    if rates is None:
        print(f"{start} -> {end}: ERROR {mt5.last_error()}")
        continue

    if len(rates) == 0:
        print(f"{start} -> {end}: 0 bars")
        continue

    first = pd.to_datetime(
        rates[0]["time"],
        unit="s",
        utc=True,
    )

    last = pd.to_datetime(
        rates[-1]["time"],
        unit="s",
        utc=True,
    )

    print(
        f"{start} -> {end}: "
        f"{len(rates):,} bars | "
        f"{first} -> {last}"
    )

mt5.shutdown()
