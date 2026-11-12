"""
run_live.py
-----------
The always-on loop for the alerts product:

    1. Pull fresh M15/H1/H4/D1 data from MT5 (not the static parquet —
       that's for backtesting only).
    2. Evaluate today's signal with the strategy chosen in config_alerts.py.
    3. If it's a new signal (not already logged today), log it and send
       a Telegram alert.
    4. Check every currently-open logged signal against the live price
       and close it out (TP/SL/time-exit) the moment that happens.
    5. Sleep, repeat.

Requires: MetaTrader5 terminal open and logged in on this machine
(same requirement as fetch_eurusd.py). Run with:

    python run_live.py
"""

import time
from datetime import datetime, timezone

import pandas as pd
import MetaTrader5 as mt5

import config as cfg
import config_alerts as acfg
import signal_store as store
import telegram_notifier as tg
import outcome_tracker as tracker

from signal_engine import add_indicators, evaluate
import breakout_engine as be


TF_MAP = {
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}


def connect():
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")
    if not mt5.symbol_select(cfg.SYMBOL, True):
        raise RuntimeError(f"Could not select {cfg.SYMBOL}")
    print(f"[run_live] Connected to MT5, symbol={cfg.SYMBOL}")


def fetch_live(tf_label, bars=1500):
    """Pull the most recent `bars` candles live — enough history for
    EMA200/ATR96 warmup on the higher timeframes."""
    rates = mt5.copy_rates_from_pos(cfg.SYMBOL, TF_MAP[tf_label], 0, bars)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No live data returned for {tf_label}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    return df


def get_current_price():
    tick = mt5.symbol_info_tick(cfg.SYMBOL)
    if tick is None:
        raise RuntimeError("Could not fetch current tick")
    return (tick.bid + tick.ask) / 2.0


def evaluate_once():
    """One pass: fetch live data, evaluate today's signal, log+notify if new."""
    if acfg.STRATEGY == "breakout":
        df_m15 = add_indicators(fetch_live("M15"))
        df_h1  = add_indicators(fetch_live("H1"))
        df_h4  = add_indicators(fetch_live("H4"))
        df_d1  = add_indicators(fetch_live("D1"))

        today = df_m15.index[-1].strftime("%Y-%m-%d")
        result = be.evaluate_day(df_m15, df_h1, df_h4, df_d1, today)

        if result is None:
            return
        if store.already_logged(result["day"], result["signal"], "breakout"):
            return  # already alerted this signal today

        signal_id = store.log_signal(result, "breakout")
        print(f"[run_live] New breakout signal logged (id={signal_id}): {result['signal']}")
        tg.send_signal_alert(result)

        if acfg.LARAVEL_API_ENABLED:
            import api_client
            api_client.post_signal_to_laravel(result, strategy="breakout")

    elif acfg.STRATEGY == "confluence":
        mode_cfg = cfg.MODES[acfg.CONFLUENCE_MODE]
        needed = {mode_cfg["bias_tf"], mode_cfg["confirm_tf"],
                  mode_cfg["setup_tf"], mode_cfg["trigger_tf"]}
        dfs = {tf: add_indicators(fetch_live(tf)) for tf in needed}

        result = evaluate(dfs, mode_cfg, bar_index=-1)
        if result is None or result["signal"] == "WAIT":
            return

        day = result["time"][:10]
        if store.already_logged(day, result["signal"], "confluence"):
            return

        result["day"] = day
        signal_id = store.log_signal(result, "confluence")
        print(f"[run_live] New confluence signal logged (id={signal_id}): {result['signal']}")
        tg.send_signal_alert(result)

        if acfg.LARAVEL_API_ENABLED:
            import api_client
            api_client.post_signal_to_laravel(result, strategy="confluence")

    else:
        raise ValueError(f"Unknown STRATEGY in config_alerts.py: {acfg.STRATEGY}")


def main():
    store.init_db()
    connect()
    tg.send_text(
        f"🚀 run_live.py started | strategy={acfg.STRATEGY} | "
        f"paper-trade mode — signals are NOT a validated live edge yet."
    )

    while True:
        try:
            evaluate_once()
            price = get_current_price()
            tracker.check_open_signals(price)
        except Exception as e:
            print(f"[run_live] Error in loop: {e}")
            tg.send_text(f"⚠️ run_live.py error: {e}")

        time.sleep(acfg.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
