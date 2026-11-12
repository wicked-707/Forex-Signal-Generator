import MetaTrader5 as mt5
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta

SYMBOL = "EURUSD"

START = datetime(2022, 1, 1, tzinfo=timezone.utc)
END = datetime.now(timezone.utc)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

TIMEFRAMES = {
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

M15_TIMEFRAME = mt5.TIMEFRAME_M15


def prepare_dataframe(rates):
    df = pd.DataFrame(rates)

    if df.empty:
        return df

    df["time"] = pd.to_datetime(
        df["time"],
        unit="s",
        utc=True,
    )

    columns = [
        "time",
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "spread",
        "real_volume",
    ]

    available = [c for c in columns if c in df.columns]
    df = df[available]

    df = df.drop_duplicates(subset="time")
    df = df.sort_values("time").reset_index(drop=True)

    return df


def download_normal_timeframe(label, timeframe):
    print(f"\nDownloading {SYMBOL} {label}...")

    rates = mt5.copy_rates_range(
        SYMBOL,
        timeframe,
        START,
        END,
    )

    if rates is None:
        print(f"ERROR: {mt5.last_error()}")
        return False

    if len(rates) == 0:
        print("ERROR: MT5 returned zero candles.")
        return False

    df = prepare_dataframe(rates)

    output = DATA_DIR / f"{SYMBOL}_{label}.parquet"
    df.to_parquet(output, index=False)

    print(f"Saved: {output}")
    print(f"Rows:  {len(df):,}")
    print(f"Start: {df['time'].iloc[0]}")
    print(f"End:   {df['time'].iloc[-1]}")

    return True


def month_end(dt):
    next_month = (dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(seconds=1)


def download_m15():
    print(f"\nDownloading {SYMBOL} M15 in monthly chunks...")

    chunks = []

    current_start = START
    chunk_number = 0

    while current_start < END:
        current_end = min(
            month_end(current_start),
            END,
        )

        chunk_number += 1

        print(
            f"  Chunk {chunk_number}: "
            f"{current_start:%Y-%m-%d} -> {current_end:%Y-%m-%d}"
        )

        rates = mt5.copy_rates_range(
            SYMBOL,
            M15_TIMEFRAME,
            current_start,
            current_end,
        )

        if rates is None:
            print(f"  ERROR: {mt5.last_error()}")
            return False

        if len(rates) == 0:
            print("  ERROR: zero candles returned")
            return False

        df_chunk = prepare_dataframe(rates)

        if df_chunk.empty:
            print("  ERROR: returned data became empty")
            return False

        chunks.append(df_chunk)

        print(
            f"  Received {len(df_chunk):,} candles | "
            f"{df_chunk['time'].iloc[0]} -> "
            f"{df_chunk['time'].iloc[-1]}"
        )

        current_start = current_end + timedelta(seconds=1)

    if not chunks:
        print("ERROR: No M15 data was downloaded.")
        return False

    df = pd.concat(
        chunks,
        ignore_index=True,
    )

    df = df.drop_duplicates(
        subset="time"
    )

    df = df.sort_values(
        "time"
    ).reset_index(drop=True)

    output = DATA_DIR / f"{SYMBOL}_M15.parquet"

    df.to_parquet(
        output,
        index=False,
    )

    print("\nM15 complete.")
    print(f"Saved: {output}")
    print(f"Rows:  {len(df):,}")
    print(f"Start: {df['time'].iloc[0]}")
    print(f"End:   {df['time'].iloc[-1]}")

    return True


def main():
    print("Initializing MetaTrader 5...")

    if not mt5.initialize():
        print(
            f"MT5 initialization failed: "
            f"{mt5.last_error()}"
        )
        raise SystemExit(1)

    terminal = mt5.terminal_info()

    print(f"MT5 connected: {terminal.name}")
    print(f"MT5 build: {terminal.build}")
    print(f"Max bars: {terminal.maxbars}")
    print(f"Symbol: {SYMBOL}")
    print(f"Requested history: {START} -> {END}")

    symbol_info = mt5.symbol_info(SYMBOL)

    if symbol_info is None:
        print(f"ERROR: Symbol {SYMBOL} not found.")
        mt5.shutdown()
        raise SystemExit(1)

    if not symbol_info.visible:
        print(
            f"{SYMBOL} is not visible. "
            f"Enabling it..."
        )

        if not mt5.symbol_select(SYMBOL, True):
            print(
                f"ERROR: Could not select {SYMBOL}."
            )
            mt5.shutdown()
            raise SystemExit(1)

    success = True

    for label, timeframe in TIMEFRAMES.items():
        if not download_normal_timeframe(
            label,
            timeframe,
        ):
            success = False

    if not download_m15():
        success = False

    mt5.shutdown()

    print("\n----------------------------------------")

    if success:
        print(
            "Historical data download completed successfully."
        )
    else:
        print(
            "Historical data download completed with errors."
        )

    print("----------------------------------------")


if __name__ == "__main__":
    main()
