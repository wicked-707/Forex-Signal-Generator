import pandas as pd
from pathlib import Path

path = Path("data/EURUSD_M15.parquet")

df = pd.read_parquet(path)

print("========================================")
print("EURUSD M15 DATA VALIDATION")
print("========================================")

print(f"Rows:       {len(df):,}")
print(f"Start:      {df['time'].iloc[0]}")
print(f"End:        {df['time'].iloc[-1]}")

# Basic ordering
is_sorted = df["time"].is_monotonic_increasing
print(f"Sorted:     {is_sorted}")

# Duplicate timestamps
duplicates = df["time"].duplicated().sum()
print(f"Duplicates: {duplicates:,}")

# Expected M15 spacing
diffs = df["time"].diff().dropna()

expected = pd.Timedelta(minutes=15)

normal = diffs == expected
gaps = diffs[diffs > expected]
backwards = diffs[diffs < expected]

print(f"Normal 15m intervals: {normal.sum():,}")
print(f"Gaps:                {len(gaps):,}")
print(f"Backward intervals:  {len(backwards):,}")

if len(gaps) > 0:
    print("\nLargest gaps:")
    largest = gaps.sort_values(ascending=False).head(20)

    for timestamp, gap in largest.items():
        previous_time = df.loc[timestamp - 1, "time"]
        current_time = df.loc[timestamp, "time"]

        print(
            f"{previous_time} -> {current_time} "
            f"= {gap}"
        )

# Date coverage by year
print("\nYearly row counts:")
year_counts = df.groupby(df["time"].dt.year).size()

for year, count in year_counts.items():
    print(f"  {year}: {count:,}")

# Training period
train = df[
    (df["time"] >= "2022-01-01") &
    (df["time"] < "2025-01-01")
]

print("\nTRAINING PERIOD")
print("----------------------------------------")
print(f"Rows:  {len(train):,}")
print(f"Start: {train['time'].iloc[0]}")
print(f"End:   {train['time'].iloc[-1]}")

# Test period
test = df[
    df["time"] >= "2025-01-01"
]

print("\nTEST PERIOD")
print("----------------------------------------")
print(f"Rows:  {len(test):,}")

if not test.empty:
    print(f"Start: {test['time'].iloc[0]}")
    print(f"End:   {test['time'].iloc[-1]}")

print("\n========================================")
print("VALIDATION COMPLETE")
print("========================================")
