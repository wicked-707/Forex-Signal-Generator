"""
outcome_tracker.py
-------------------
Walks every OPEN logged signal against the current live price and
closes it out (TP/SL/time-exit) the moment that actually happens —
this is what turns signal_store.py from "a log of predictions" into
"a real, live-verified track record".

Call check_open_signals(current_price, now) on every polling loop
tick in run_live.py, right after checking for a new signal.
"""

from datetime import datetime, timezone

import config as cfg
import config_alerts as acfg
import signal_store as store
import telegram_notifier as tg

# How long to let a trade run before forcing a time-based exit, in hours.
# Mirrors BREAKOUT["session_close_hour"] for the breakout strategy.
MAX_HOLD_HOURS = 13  # e.g. entry ~07:00-11:00 UTC -> force close by 20:00 UTC


def check_open_signals(current_price, now=None):
    """
    current_price: latest EURUSD bid/mid price (float) from your live feed.
    now: a timezone-aware UTC datetime; defaults to current time.
    """
    now = now or datetime.now(timezone.utc)
    closed = []

    for row in store.get_open_signals():
        direction = row["direction"]
        sl = row["stop_loss"]
        tp = row["take_profit"]
        entry = row["entry_price"]
        stop_pips = row["stop_pips"]

        hit_sl = (current_price <= sl) if direction == "BUY" else (current_price >= sl)
        hit_tp = (current_price >= tp) if direction == "BUY" else (current_price <= tp)

        signal_dt = _parse_dt(row["signal_time"])
        hours_open = (now - signal_dt).total_seconds() / 3600.0 if signal_dt else 0
        timed_out = hours_open >= MAX_HOLD_HOURS

        if not (hit_sl or hit_tp or timed_out):
            continue

        if hit_sl:
            exit_reason = "SL"
            exit_price = sl
        elif hit_tp:
            exit_reason = "TP"
            exit_price = tp
        else:
            exit_reason = "TIME"
            exit_price = current_price

        pips = (exit_price - entry) / cfg.PIP_SIZE
        if direction == "SELL":
            pips = -pips
        pips -= cfg.SPREAD_PIPS  # same round-trip spread cost used in backtests
        r_multiple = pips / stop_pips

        updated = store.close_signal(
            row["id"], exit_price=exit_price, exit_reason=exit_reason,
            pips_result=pips, r_multiple=r_multiple,
        )
        tg.send_closed_alert(updated)
        closed.append(updated)

    return closed


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc) \
            if datetime.fromisoformat(value).tzinfo is None else datetime.fromisoformat(value)
    except ValueError:
        return None
