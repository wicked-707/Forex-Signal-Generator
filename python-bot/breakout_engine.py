"""
breakout_engine.py
------------------
Asian range breakout strategy for EUR/USD.
Timeframes: M15 trigger, H1 confirmation, H4/D1 bias filter.

Usage:
    python breakout_engine.py                # today's potential setup
    python breakout_engine.py --date 2025-06-12
"""

import argparse
import os
import pandas as pd
import numpy as np
import pandas_ta_classic as ta

import config as cfg
from signal_engine import load_tf, add_indicators


# ============================================================
# HELPERS
# ============================================================
def pips_to_price(pips):
    return pips * cfg.PIP_SIZE


def get_asian_range(df_m15, day):
    """Return (high, low, range_pips) for the Asian session of a given date."""
    day_start = pd.Timestamp(day).tz_localize("UTC")
    asian_start = day_start + pd.Timedelta(hours=cfg.BREAKOUT["asian_start_hour"])
    asian_end   = day_start + pd.Timedelta(hours=cfg.BREAKOUT["asian_end_hour"])

    mask = (df_m15.index >= asian_start) & (df_m15.index < asian_end)
    window = df_m15.loc[mask]

    if len(window) < 8:   # need at least ~2 hours of data
        return None

    hi = window["high"].max()
    lo = window["low"].min()
    rng_pips = (hi - lo) / cfg.PIP_SIZE
    return {"high": hi, "low": lo, "range_pips": rng_pips,
            "start": asian_start, "end": asian_end}


def atr_expansion_ok(df_m15, ts):
    """True if ATR(fast) > atr_expansion_min x ATR(slow) at time ts."""
    # Compute on-the-fly if not already in df
    if "atr_fast" not in df_m15.columns:
        df_m15["atr_fast"] = ta.atr(df_m15["high"], df_m15["low"],
                                     df_m15["close"], length=cfg.BREAKOUT["atr_fast"])
        df_m15["atr_slow"] = ta.atr(df_m15["high"], df_m15["low"],
                                     df_m15["close"], length=cfg.BREAKOUT["atr_slow"])

    row = df_m15.loc[df_m15.index <= ts].iloc[-1]
    if pd.isna(row["atr_slow"]) or row["atr_slow"] == 0:
        return False
    ratio = row["atr_fast"] / row["atr_slow"]
    return ratio >= cfg.BREAKOUT["atr_expansion_min"]


def as_closed_bars(df_ht):
    """
    FIX (look-ahead bias): a higher-timeframe bar's index marks when it
    OPENED, not when it closed. A D1 bar dated 2023-06-12 00:00 isn't
    finalized until midnight on the 13th — its close/EMA values are only
    truly known at end of day. Selecting "the bar whose index <= ts" for
    a same-day ts (e.g. 07:00) was picking up that day's own future close.

    Shifting every column down by one row keeps the same index but
    attaches each row's *previous* (fully closed) bar's values to it.
    So "index <= ts" now correctly resolves to the last bar that had
    actually finished printing by ts.
    """
    return df_ht.shift(1)


def trend_agrees(df_ht, ts, direction):
    """Check H4 or D1 bias agrees with direction.

    NOTE: df_ht is expected to already be the shifted/"closed" frame
    from as_closed_bars() — see evaluate_day / simulate_day below.
    """
    sub = df_ht.loc[df_ht.index <= ts]
    if len(sub) < 5:
        return False
    row = sub.iloc[-1]

    if pd.isna(row["ema_mid"]) or pd.isna(row["ema_slow"]):
        return False

    # Optional: require a strong higher-timeframe trend, not just EMA order.
    # Toggleable (like use_h4_trend/use_d1_trend) so its effect on trade
    # count and win rate can be measured in isolation before keeping it.
    if cfg.BREAKOUT.get("use_adx_filter", False):
        if "adx" in row and not pd.isna(row["adx"]):
            if row["adx"] < cfg.BREAKOUT.get("min_adx_ht", 25):
                return False

    if direction == "BUY":
        return row["close"] > row["ema_mid"] and row["ema_mid"] > row["ema_slow"]
    else:
        return row["close"] < row["ema_mid"] and row["ema_mid"] < row["ema_slow"]


# ============================================================
# SIGNAL LOGIC (single-day evaluation)
# ============================================================
def evaluate_day(df_m15, df_h1, df_h4, df_d1, day):
    """
    Returns a signal dict for the given day, or None if no setup.
    """
    asian = get_asian_range(df_m15, day)
    if asian is None:
        return None

    if not (cfg.BREAKOUT["min_range_pips"] <= asian["range_pips"] <= cfg.BREAKOUT["max_range_pips"]):
        return None

    # FIX: only ever check trend agreement against fully-closed H4/D1 bars.
    df_h4_closed = as_closed_bars(df_h4)
    df_d1_closed = as_closed_bars(df_d1)

    # Entry window
    day_start = pd.Timestamp(day).tz_localize("UTC")
    entry_start = day_start + pd.Timedelta(hours=cfg.BREAKOUT["entry_start_hour"])
    entry_end   = day_start + pd.Timedelta(hours=cfg.BREAKOUT["entry_end_hour"])

    window = df_m15.loc[(df_m15.index >= entry_start) & (df_m15.index < entry_end)]

    if len(window) == 0:
        return None

    for ts, row in window.iterrows():
        direction = None
        if row["close"] > asian["high"]:
            direction = "BUY"
        elif row["close"] < asian["low"]:
            direction = "SELL"

        if direction is None:
            continue

        # Volatility filter
        if not atr_expansion_ok(df_m15, ts):
            continue

        # Trend filters (now against closed bars only)
        if cfg.BREAKOUT["use_h4_trend"] and not trend_agrees(df_h4_closed, ts, direction):
            continue
        if cfg.BREAKOUT["use_d1_trend"] and not trend_agrees(df_d1_closed, ts, direction):
            continue

        # Build the trade
        entry = row["close"]

        # Stop = opposite side of range +/- buffer
        atr_now = row["atr_fast"] if "atr_fast" in row else ta.atr(
            df_m15["high"], df_m15["low"], df_m15["close"],
            length=cfg.BREAKOUT["atr_fast"]).loc[ts]
        buffer = cfg.BREAKOUT["stop_buffer_atr"] * atr_now

        if direction == "BUY":
            sl = asian["low"] - buffer
            stop_pips = (entry - sl) / cfg.PIP_SIZE
        else:
            sl = asian["high"] + buffer
            stop_pips = (sl - entry) / cfg.PIP_SIZE

        stop_pips = max(stop_pips, cfg.BREAKOUT["min_stop_pips"])

        # TP from range size
        range_price = asian["range_pips"] * cfg.PIP_SIZE
        if direction == "BUY":
            tp1 = entry + cfg.BREAKOUT["tp1_range_mult"] * range_price
            tp2 = entry + cfg.BREAKOUT["tp2_range_mult"] * range_price
        else:
            tp1 = entry - cfg.BREAKOUT["tp1_range_mult"] * range_price
            tp2 = entry - cfg.BREAKOUT["tp2_range_mult"] * range_price

        # Lot size
        risk_usd = cfg.ACCOUNT_BALANCE * cfg.RISK_PER_TRADE
        raw_lot = risk_usd / (stop_pips * 10.0)
        lot = max(cfg.MIN_LOT, min(cfg.MAX_LOT, round(raw_lot, 2)))

        return {
            "day":        str(day),
            "time":       str(ts),
            "signal":     direction,
            "asian_high": asian["high"],
            "asian_low":  asian["low"],
            "range_pips": round(asian["range_pips"], 1),
            "entry":      round(entry, 5),
            "stop_loss":  round(sl, 5),
            "tp1":        round(tp1, 5),
            "tp2":        round(tp2, 5),
            "stop_pips":  round(stop_pips, 1),
            "lot_size":   lot,
            "reasons": [
                f"Asian range {asian['range_pips']:.1f} pips",
                f"Breakout {direction} at {ts}",
                f"Stop distance {stop_pips:.1f} pips",
            ],
        }

    return None


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD (default: latest)")
    args = parser.parse_args()

    df_m15 = add_indicators(load_tf("M15"))
    df_h1  = add_indicators(load_tf("H1"))
    df_h4  = add_indicators(load_tf("H4"))
    df_d1  = add_indicators(load_tf("D1"))

    if args.date:
        day = args.date
    else:
        day = df_m15.index[-1].strftime("%Y-%m-%d")

    result = evaluate_day(df_m15, df_h1, df_h4, df_d1, day)

    print("=" * 60)
    print(f"BREAKOUT SIGNAL — {day}")
    print("=" * 60)
    if result is None:
        print("No qualifying setup.")
        return

    print(f"Signal:   {result['signal']}")
    print(f"Time:     {result['time']}")
    print(f"Entry:    {result['entry']}")
    print(f"SL:       {result['stop_loss']}  ({result['stop_pips']} pips)")
    print(f"TP1:      {result['tp1']}")
    print(f"TP2:      {result['tp2']}")
    print(f"Lot:      {result['lot_size']}")
    print(f"Range:    {result['range_pips']} pips")
    print("Reasons:")
    for r in result["reasons"]:
        print(f"  • {r}")


if __name__ == "__main__":
    main()
