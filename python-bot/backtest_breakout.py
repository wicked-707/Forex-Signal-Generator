"""
backtest_breakout.py
--------------------
Backtest the Asian-range breakout strategy across all available M15 data.
One trade per day max, exit at TP1 / SL / session close (20:00 UTC).
"""

import argparse
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional

import config as cfg
from signal_engine import load_tf, add_indicators
from breakout_engine import get_asian_range, atr_expansion_ok, trend_agrees, pips_to_price, as_closed_bars


@dataclass
class Trade:
    day: str
    direction: str
    signal_time: pd.Timestamp     # bar that generated the breakout signal
    entry_time: pd.Timestamp      # bar actually filled on
    entry_price: float
    stop_loss: float
    tp1: float
    stop_pips: float
    lot_size: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pips_result: float = 0.0
    usd_result: float = 0.0
    r_multiple: float = 0.0


PIP_VALUE_PER_LOT = 10.0


def usd_pnl(pips, lot):
    return pips * lot * PIP_VALUE_PER_LOT


def run_backtest(start=None, end=None):
    df_m15 = add_indicators(load_tf("M15"))
    df_h4  = add_indicators(load_tf("H4"))
    df_d1  = add_indicators(load_tf("D1"))

    # Precompute ATR slow/fast for whole M15 frame
    import pandas_ta_classic as ta
    df_m15["atr_fast"] = ta.atr(df_m15["high"], df_m15["low"], df_m15["close"],
                                 length=cfg.BREAKOUT["atr_fast"])
    df_m15["atr_slow"] = ta.atr(df_m15["high"], df_m15["low"], df_m15["close"],
                                 length=cfg.BREAKOUT["atr_slow"])

    # FIX (look-ahead): only ever check H4/D1 trend against bars that had
    # actually finished forming as of the M15 timestamp being evaluated.
    # See as_closed_bars() in breakout_engine.py for why this matters.
    df_h4_closed = as_closed_bars(df_h4)
    df_d1_closed = as_closed_bars(df_d1)

    # Train/test split: the full history is still loaded above so
    # indicators (ATR slow, EMAs on H4/D1) have proper warmup — only the
    # SET OF DAYS we're allowed to open trades on is restricted here.
    unique_days = sorted(set(df_m15.index.date))
    if start is not None:
        start_date = pd.Timestamp(start).date()
        unique_days = [d for d in unique_days if d >= start_date]
    if end is not None:
        end_date = pd.Timestamp(end).date()
        unique_days = [d for d in unique_days if d <= end_date]

    trades = []
    for day_obj in unique_days:
        day = str(day_obj)
        trade = simulate_day(df_m15, df_h4_closed, df_d1_closed, day)
        if trade is not None:
            trades.append(trade)

    return trades


def simulate_day(df_m15, df_h4_closed, df_d1_closed, day):
    asian = get_asian_range(df_m15, day)
    if asian is None:
        return None
    if not (cfg.BREAKOUT["min_range_pips"] <= asian["range_pips"] <= cfg.BREAKOUT["max_range_pips"]):
        return None

    day_start = pd.Timestamp(day).tz_localize("UTC")
    entry_start = day_start + pd.Timedelta(hours=cfg.BREAKOUT["entry_start_hour"])
    entry_end   = day_start + pd.Timedelta(hours=cfg.BREAKOUT["entry_end_hour"])
    session_end = day_start + pd.Timedelta(hours=cfg.BREAKOUT["session_close_hour"])

    window = df_m15.loc[(df_m15.index >= entry_start) & (df_m15.index < entry_end)]
    if len(window) == 0:
        return None

    # Find first breakout bar with all filters passing
    signal_ts = None
    signal_row = None
    direction = None

    for ts, row in window.iterrows():
        d = None
        if row["close"] > asian["high"]:
            d = "BUY"
        elif row["close"] < asian["low"]:
            d = "SELL"
        if d is None:
            continue

        # Volatility filter
        if pd.isna(row["atr_slow"]) or row["atr_slow"] == 0:
            continue
        ratio = row["atr_fast"] / row["atr_slow"]
        if ratio < cfg.BREAKOUT["atr_expansion_min"]:
            continue

        # Trend filters (against closed H4/D1 bars only — see run_backtest)
        if cfg.BREAKOUT["use_h4_trend"] and not trend_agrees(df_h4_closed, ts, d):
            continue
        if cfg.BREAKOUT["use_d1_trend"] and not trend_agrees(df_d1_closed, ts, d):
            continue

        signal_ts = ts
        signal_row = row
        direction = d
        break

    if signal_ts is None:
        return None

    # FIX (execution realism): you can't act on a bar until it has closed,
    # so the earliest real fill is the *next* bar's open — not this bar's
    # own close, which the strategy is using to detect the breakout in the
    # first place. Falls back to same-bar close if disabled or no bar left.
    if cfg.ENTRY_ON_NEXT_OPEN:
        after_signal = df_m15.loc[df_m15.index > signal_ts]
        if len(after_signal) == 0:
            return None
        entry_ts = after_signal.index[0]
        entry_row = after_signal.iloc[0]
        entry = entry_row["open"]
    else:
        entry_ts = signal_ts
        entry_row = signal_row
        entry = entry_row["close"]

    buffer = cfg.BREAKOUT["stop_buffer_atr"] * signal_row["atr_fast"]

    if direction == "BUY":
        sl = asian["low"] - buffer
        stop_pips = max((entry - sl) / cfg.PIP_SIZE, cfg.BREAKOUT["min_stop_pips"])
        sl = entry - stop_pips * cfg.PIP_SIZE
        tp1 = entry + cfg.BREAKOUT["tp1_range_mult"] * asian["range_pips"] * cfg.PIP_SIZE
    else:
        sl = asian["high"] + buffer
        stop_pips = max((sl - entry) / cfg.PIP_SIZE, cfg.BREAKOUT["min_stop_pips"])
        sl = entry + stop_pips * cfg.PIP_SIZE
        tp1 = entry - cfg.BREAKOUT["tp1_range_mult"] * asian["range_pips"] * cfg.PIP_SIZE

    risk_usd = cfg.ACCOUNT_BALANCE * cfg.RISK_PER_TRADE
    raw_lot = risk_usd / (stop_pips * PIP_VALUE_PER_LOT)
    lot = max(cfg.MIN_LOT, min(cfg.MAX_LOT, round(raw_lot, 2)))

    # Walk bars from entry_ts (the actual fill) to session_end
    walk = df_m15.loc[(df_m15.index > entry_ts) & (df_m15.index <= session_end)]

    exit_ts = None
    exit_price = None
    exit_reason = None

    for ts, bar in walk.iterrows():
        if direction == "BUY":
            if bar["low"] <= sl:
                exit_ts, exit_price, exit_reason = ts, sl, "SL"
                break
            if bar["high"] >= tp1:
                exit_ts, exit_price, exit_reason = ts, tp1, "TP"
                break
        else:
            if bar["high"] >= sl:
                exit_ts, exit_price, exit_reason = ts, sl, "SL"
                break
            if bar["low"] <= tp1:
                exit_ts, exit_price, exit_reason = ts, tp1, "TP"
                break

    if exit_ts is None:
        # session close
        last = walk.iloc[-1] if len(walk) else entry_row
        exit_ts = walk.index[-1] if len(walk) else entry_ts
        exit_price = last["close"]
        exit_reason = "SESSION"

    pips = (exit_price - entry) / cfg.PIP_SIZE
    if direction == "SELL":
        pips = -pips

    # FIX: charge the spread once per round-trip. Previously spread was
    # only used as a live entry filter and never actually cost anything
    # in the backtest P&L.
    pips -= cfg.SPREAD_PIPS

    trade = Trade(
        day=day,
        direction=direction,
        signal_time=signal_ts,
        entry_time=entry_ts,
        entry_price=entry,
        stop_loss=sl,
        tp1=tp1,
        stop_pips=stop_pips,
        lot_size=lot,
        exit_time=exit_ts,
        exit_price=exit_price,
        exit_reason=exit_reason,
        pips_result=pips,
        usd_result=usd_pnl(pips, lot),
        r_multiple=pips / stop_pips,
    )
    return trade


def summarize(trades):
    print("\n" + "=" * 60)
    print("BACKTEST REPORT — BREAKOUT")
    print("=" * 60)

    if not trades:
        print("No trades.")
        return

    df = pd.DataFrame([t.__dict__ for t in trades])
    total = len(df)
    wins = df[df["r_multiple"] > 0]
    losses = df[df["r_multiple"] < 0]
    wr = len(wins) / total * 100
    avg_r = df["r_multiple"].mean()
    total_r = df["r_multiple"].sum()
    total_usd = df["usd_result"].sum()

    eq = df.sort_values("exit_time")["usd_result"].cumsum()
    max_dd = (eq - eq.cummax()).min()

    print(f"Total trades:    {total}")
    print(f"Wins / Losses:   {len(wins)} / {len(losses)}")
    print(f"Win rate:        {wr:.2f}%")
    print(f"Avg R / trade:   {avg_r:.3f}")
    print(f"Total R:         {total_r:.2f}")
    print(f"Total USD:       ${total_usd:.2f}")
    print(f"Max drawdown:    ${max_dd:.2f}")
    print(f"Start balance:   ${cfg.ACCOUNT_BALANCE:.2f}")
    print(f"End balance:     ${cfg.ACCOUNT_BALANCE + total_usd:.2f}")
    print(f"(spread cost of {cfg.SPREAD_PIPS} pips/trade already included above)")

    print(f"\nExit reasons:")
    for reason, count in df["exit_reason"].value_counts().items():
        print(f"  {reason}: {count}")

    print(f"\nDirection:")
    for d in ("BUY", "SELL"):
        sub = df[df["direction"] == d]
        if len(sub):
            w = (sub["r_multiple"] > 0).mean() * 100
            print(f"  {d}: {len(sub)} trades | WR {w:.1f}% | total R {sub['r_multiple'].sum():.2f}")

    print(f"\nBy year:")
    df["year"] = df["entry_time"].dt.year
    for y in sorted(df["year"].unique()):
        sub = df[df["year"] == y]
        w = (sub["r_multiple"] > 0).mean() * 100
        print(f"  {y}: {len(sub)} trades | WR {w:.1f}% | total R {sub['r_multiple'].sum():.2f}")

    out = "backtest_breakout_trades.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["train", "test", "all"], default="train",
                         help="train = tune here; test = run ONCE at the end as a holdout; "
                              "all = full history (old behavior, no split)")
    parser.add_argument("--start", help="override start date YYYY-MM-DD (takes precedence over --split)")
    parser.add_argument("--end", help="override end date YYYY-MM-DD (takes precedence over --split)")
    args = parser.parse_args()

    if args.start or args.end:
        start, end = args.start, args.end
        label = f"{start or 'earliest'} -> {end or 'latest'}"
    elif args.split == "train":
        start, end = cfg.SPLIT["train_start"], cfg.SPLIT["train_end"]
        label = f"TRAIN {start} -> {end}"
    elif args.split == "test":
        start, end = cfg.SPLIT["test_start"], cfg.SPLIT["test_end"]
        label = f"TEST (HOLDOUT) {start} -> {end or 'latest'}"
    else:
        start, end = None, None
        label = "ALL DATA (no split)"

    print(f"Split: {label}")
    if args.split == "test" and not (args.start or args.end):
        print("!! This is your holdout set — only meant to be run once you're")
        print("!! done tuning on --split train. If you're about to go tweak a")
        print("!! filter after seeing this result, that defeats the point.\n")

    trades = run_backtest(start=start, end=end)
    summarize(trades)


if __name__ == "__main__":
    main()
