"""
signal_engine.py
----------------
Multi-timeframe confluence signal generator for EUR/USD.

Usage:
    python signal_engine.py --mode intraday
    python signal_engine.py --mode scalp
    python signal_engine.py --mode intraday --history 500
"""

import argparse
import os
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
from datetime import datetime, timezone

import config as cfg


# ============================================================
# DATA LOADING
# ============================================================
def load_tf(tf_label):
    """
    Load a timeframe parquet file and normalize its timestamp index.
    """
    path = os.path.join(cfg.DATA_DIR, f"{cfg.SYMBOL}_{tf_label}.parquet")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_parquet(path)

    # Parquet stores MT5 timestamps in the `time` column.
    # Convert them to a UTC DatetimeIndex so all backtest
    # alignment and train/test split operations work correctly.
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df = df.set_index("time")

    df = df.sort_index()

    return df


# ============================================================
# INDICATORS
# ============================================================
def add_indicators(df):
    df = df.copy()
    df["ema_fast"] = ta.ema(df["close"], length=cfg.EMA_FAST)
    df["ema_mid"]  = ta.ema(df["close"], length=cfg.EMA_MID)
    df["ema_slow"] = ta.ema(df["close"], length=cfg.EMA_SLOW)
    df["rsi"] = ta.rsi(df["close"], length=cfg.RSI_PERIOD)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=cfg.ATR_PERIOD)

    adx = ta.adx(df["high"], df["low"], df["close"], length=cfg.ADX_PERIOD)
    if adx is not None and f"ADX_{cfg.ADX_PERIOD}" in adx.columns:
        df["adx"] = adx[f"ADX_{cfg.ADX_PERIOD}"]
    return df


# ============================================================
# LAYER 1 — REGIME (D1 + H4)
# ============================================================
def regime_layer(df_bias, df_confirm):
    b = df_bias.iloc[-1]
    c = df_confirm.iloc[-1]

    if pd.isna(b["ema_slow"]) or pd.isna(c["ema_mid"]):
        return "RANGING", ["Insufficient history for regime"]

    reasons = []
    bull = 0
    bear = 0

    if b["ema_mid"] > b["ema_slow"]:
        bull += 1; reasons.append("D1 EMA50 > EMA200 (bullish)")
    elif b["ema_mid"] < b["ema_slow"]:
        bear += 1; reasons.append("D1 EMA50 < EMA200 (bearish)")

    if "adx" in df_bias.columns and not pd.isna(b.get("adx")):
        if b["adx"] >= cfg.ADX_TREND_THRESH:
            reasons.append(f"D1 ADX {b['adx']:.1f} (trending)")
        else:
            reasons.append(f"D1 ADX {b['adx']:.1f} (weak trend)")

    if c["close"] > c["ema_mid"]:
        bull += 1; reasons.append("H4 close > EMA50")
    elif c["close"] < c["ema_mid"]:
        bear += 1; reasons.append("H4 close < EMA50")

    if bull > bear:
        return "BULLISH", reasons
    if bear > bull:
        return "BEARISH", reasons
    return "RANGING", reasons


# ============================================================
# LAYER 2 — SETUP (pullback)
# ============================================================
def setup_layer(df_setup, bias):
    if len(df_setup) < 3:
        return False, ["Not enough setup bars"]

    row  = df_setup.iloc[-1]
    reasons = []

    if pd.isna(row["ema_mid"]) or pd.isna(row["rsi"]):
        return False, ["Setup indicators NaN"]

    near_ema_fast = abs(row["close"] - row["ema_fast"]) < 1.0 * row["atr"]
    near_ema_mid  = abs(row["close"] - row["ema_mid"])  < 1.0 * row["atr"]
    in_pullback   = near_ema_fast or near_ema_mid

    if bias == "BULLISH":
        trend_ok = row["close"] > row["ema_slow"]
        rsi_ok   = 35 <= row["rsi"] <= 65
        if in_pullback and trend_ok and rsi_ok:
            reasons.append("H1 pullback to EMA zone (bullish trend intact)")
            reasons.append(f"H1 RSI {row['rsi']:.1f}")
            return True, reasons
        return False, ["No bullish pullback setup"]

    if bias == "BEARISH":
        trend_ok = row["close"] < row["ema_slow"]
        rsi_ok   = 35 <= row["rsi"] <= 65
        if in_pullback and trend_ok and rsi_ok:
            reasons.append("H1 pullback to EMA zone (bearish trend intact)")
            reasons.append(f"H1 RSI {row['rsi']:.1f}")
            return True, reasons
        return False, ["No bearish pullback setup"]

    return False, ["Regime is RANGING — no setup"]


# ============================================================
# LAYER 3 — TRIGGER (M15 momentum)
# ============================================================
def trigger_layer(df_trigger, bias):
    if len(df_trigger) < 3:
        return False, ["Not enough trigger bars"]

    row  = df_trigger.iloc[-1]
    prev = df_trigger.iloc[-2]

    if pd.isna(row["rsi"]) or pd.isna(prev["rsi"]):
        return False, ["Trigger indicators NaN"]

    reasons = []

    if bias == "BULLISH":
        if prev["rsi"] < 50 and row["rsi"] >= 50:
            reasons.append("M15 RSI crossed above 50")
            return True, reasons
        if row["close"] > row["ema_fast"] and row["close"] > row["open"]:
            reasons.append("M15 bullish momentum candle")
            return True, reasons
        return False, ["No bullish trigger"]

    if bias == "BEARISH":
        if prev["rsi"] > 50 and row["rsi"] <= 50:
            reasons.append("M15 RSI crossed below 50")
            return True, reasons
        if row["close"] < row["ema_fast"] and row["close"] < row["open"]:
            reasons.append("M15 bearish momentum candle")
            return True, reasons
        return False, ["No bearish trigger"]

    return False, ["No trigger — neutral bias"]


# ============================================================
# LAYER 4 — SESSION
# ============================================================
def session_ok(ts_utc):
    h = ts_utc.hour
    return (cfg.LONDON_OPEN <= h < cfg.LONDON_CLOSE) or (cfg.NY_OPEN <= h < cfg.NY_CLOSE)


# ============================================================
# LAYER 5 — RISK & LOT SIZE
# ============================================================
def compute_risk(entry, direction, atr_setup, mode_cfg, spread_pips):
    stop_dist = mode_cfg["atr_stop_mult"] * atr_setup

    if direction == "BUY":
        sl = entry - stop_dist
        tp1 = entry + mode_cfg["rr_tp1"] * stop_dist
        tp2 = entry + mode_cfg["rr_tp2"] * stop_dist
    else:
        sl = entry + stop_dist
        tp1 = entry - mode_cfg["rr_tp1"] * stop_dist
        tp2 = entry - mode_cfg["rr_tp2"] * stop_dist

    stop_pips = stop_dist / cfg.PIP_SIZE
    risk_usd  = cfg.ACCOUNT_BALANCE * cfg.RISK_PER_TRADE
    pip_value_per_lot = 10.0
    raw_lot = risk_usd / (stop_pips * pip_value_per_lot) if stop_pips > 0 else 0

    clamped = max(cfg.MIN_LOT, min(cfg.MAX_LOT, round(raw_lot, 2)))
    clamp_note = None
    if clamped != round(raw_lot, 2):
        if clamped == cfg.MIN_LOT:
            clamp_note = f"Raised to minimum {cfg.MIN_LOT} lot"
        elif clamped == cfg.MAX_LOT:
            clamp_note = f"Capped at maximum {cfg.MAX_LOT} lot"

    actual_risk_usd = clamped * stop_pips * pip_value_per_lot
    actual_risk_pct = actual_risk_usd / cfg.ACCOUNT_BALANCE * 100

    return {
        "stop_pips":       round(stop_pips, 1),
        "stop_loss":       round(sl, 5),
        "take_profit_1":   round(tp1, 5),
        "take_profit_2":   round(tp2, 5),
        "rr_tp1":          mode_cfg["rr_tp1"],
        "rr_tp2":          mode_cfg["rr_tp2"],
        "lot_size":        clamped,
        "risk_usd":        round(actual_risk_usd, 2),
        "actual_risk_pct": round(actual_risk_pct, 2),
        "clamp_note":      clamp_note,
    }


# ============================================================
# MAIN EVALUATOR
# ============================================================
def evaluate(dfs, mode_cfg, bar_index=-1):
    df_bias    = dfs[mode_cfg["bias_tf"]]
    df_confirm = dfs[mode_cfg["confirm_tf"]]
    df_setup   = dfs[mode_cfg["setup_tf"]]
    df_trigger = dfs[mode_cfg["trigger_tf"]]

    # FIX (look-ahead bias): in historical/backtest mode (bar_index != -1),
    # slicing each higher-timeframe frame to "index <= cutoff" and taking
    # the last row picks up that bar's FINAL close/EMA — information that
    # wasn't actually available yet at that point in time, because a bar's
    # timestamp marks when it opened, not when it closed. Shifting by one
    # row makes each timestamp carry the previous (fully closed) bar's
    # values instead.
    #
    # Live mode (bar_index == -1) is exempt: there, "the last row" is
    # whatever the broker feed currently reports, which is genuinely
    # up-to-the-moment data, not a look-ahead leak.
    if bar_index != -1:
        df_bias    = df_bias.shift(1)
        df_confirm = df_confirm.shift(1)
        df_setup   = df_setup.shift(1)

    # Slice to "as of" the trigger bar time in history mode
    if bar_index != -1:
        cutoff = df_trigger.index[bar_index]
        df_bias    = df_bias[df_bias.index <= cutoff]
        df_confirm = df_confirm[df_confirm.index <= cutoff]
        df_setup   = df_setup[df_setup.index <= cutoff]
        df_trigger = df_trigger[df_trigger.index <= cutoff]

    if len(df_setup) < 5 or len(df_trigger) < 5:
        return None

    ts = df_trigger.index[-1]
    reasons = []
    confidence = 0

    # Layer 1 — regime
    bias, bias_reasons = regime_layer(df_bias, df_confirm)
    reasons.extend(bias_reasons)
    if bias != "RANGING":
        confidence += 1

    # Layer 2 — setup
    setup_ok, setup_reasons = setup_layer(df_setup, bias)
    if setup_ok:
        confidence += 1
        reasons.extend(setup_reasons)

    # Layer 3 — trigger
    trigger_ok, trigger_reasons = trigger_layer(df_trigger, bias)
    if trigger_ok:
        confidence += 1
        reasons.extend(trigger_reasons)

    # Layer 4 — session
    if session_ok(ts):
        confidence += 1
        reasons.append("Active London/NY session")
    else:
        reasons.append("Outside major session")

    # Spread check
    spread_pips = df_trigger.iloc[-1]["spread"] / 10.0
    if spread_pips <= cfg.MAX_SPREAD_PIPS:
        confidence += 1
    else:
        reasons.append(f"Spread too wide ({spread_pips:.1f} pips)")

    # ---- DECISION ----
    # FIX: min_confidence now comes from mode_cfg only (single source of
    # truth — see config.py). Previously a separate, higher threshold in
    # BACKTEST[...] meant the backtest was quietly testing a stricter
    # system than the one that runs live.
    if not setup_ok or not trigger_ok or bias == "RANGING":
        signal = "WAIT"
        confidence = 0
    elif confidence < mode_cfg["min_confidence"]:
        signal = "WAIT"
        confidence = 0
    else:
        signal = "BUY" if bias == "BULLISH" else "SELL"

    result = {
        "time":       str(ts),
        "symbol":     cfg.SYMBOL,
        "mode":       None,
        "signal":     signal,
        "confidence": confidence,
        "reasons":    reasons,
    }

    if signal in ("BUY", "SELL"):
        entry = df_trigger.iloc[-1]["close"]
        atr_setup = df_setup.iloc[-1]["atr"]
        risk = compute_risk(entry, signal, atr_setup, mode_cfg, spread_pips)
        result["entry"] = entry
        result.update(risk)

    return result


# ============================================================
# PRINT
# ============================================================
def print_signal(r, compact=False):
    if compact and r["signal"] == "WAIT":
        return

    print("=" * 60)
    print(f"[{r['mode'].upper()}] {r['time']}")
    print(f"Signal: {r['signal']}  |  Confidence: {r['confidence']}/5")
    for reason in r["reasons"]:
        print(f"  • {reason}")
    if r["signal"] in ("BUY", "SELL"):
        print(f"  Entry:      {r['entry']}")
        print(f"  Stop Loss:  {r['stop_loss']}  ({r['stop_pips']} pips)")
        print(f"  TP1:        {r['take_profit_1']}  (1:{r['rr_tp1']})")
        print(f"  TP2:        {r['take_profit_2']}  (1:{r['rr_tp2']})")
        print(f"  Lot size:   {r['lot_size']}  | Actual risk: {r['actual_risk_pct']}% (${r['risk_usd']})")
        if r.get("clamp_note"):
            print(f"  ⚠️  {r['clamp_note']}")


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["intraday", "scalp"], default="intraday")
    parser.add_argument("--history", type=int, default=0)
    args = parser.parse_args()

    mode_cfg = cfg.MODES[args.mode]

    needed = {mode_cfg["bias_tf"], mode_cfg["confirm_tf"],
              mode_cfg["setup_tf"], mode_cfg["trigger_tf"]}
    dfs = {}
    for tf in needed:
        dfs[tf] = add_indicators(load_tf(tf))

    if args.history == 0:
        result = evaluate(dfs, mode_cfg, bar_index=-1)
        if result:
            result["mode"] = args.mode
            print_signal(result)
        else:
            print("Not enough data to evaluate.")
    else:
        df_trig = dfs[mode_cfg["trigger_tf"]]
        n = min(args.history, len(df_trig) - 5)
        for i in range(n, 0, -1):
            result = evaluate(dfs, mode_cfg, bar_index=-i)
            if result:
                result["mode"] = args.mode
                print_signal(result, compact=True)


if __name__ == "__main__":
    main()
