"""
config.py
---------
Central settings for the signal engine.
"""

# ---- Account ----
ACCOUNT_BALANCE   = 1000.0     # USD
RISK_PER_TRADE    = 0.01       # 1%

# ---- Lot sizing ----
MIN_LOT           = 0.05
MAX_LOT           = 1.00
LOT_STEP          = 0.01

# ---- Mode presets ----
# NOTE (FIX): min_confidence here is now the single source of truth.
# Previously BACKTEST[...]["min_confidence"] duplicated this with a
# different value (4 vs 3), so the backtest was silently testing a
# stricter system than the one that actually runs live. Only this
# value is used now — see backtest.py.
MODES = {
    "intraday": {
        "bias_tf":       "D1",
        "confirm_tf":    "H4",
        "setup_tf":      "H1",
        "trigger_tf":    "M15",
        "atr_stop_mult": 1.5,   # SL = 1.5 x ATR(setup_tf)
        "rr_tp1":        2.0,
        "rr_tp2":        3.0,
        "min_confidence": 4,     # was inconsistent between live (3) and backtest (4); using 4 everywhere
    },
    "scalp": {
        "bias_tf":       "H4",
        "confirm_tf":    "H1",
        "setup_tf":      "M15",
        "trigger_tf":    "M15",
        "atr_stop_mult": 1.0,
        "rr_tp1":        1.5,
        "rr_tp2":        2.0,
        "min_confidence": 4,
    },
}

# ---- Indicator parameters ----
EMA_FAST          = 20
EMA_MID           = 50
EMA_SLOW          = 200
RSI_PERIOD        = 14
ATR_PERIOD        = 14
ADX_PERIOD        = 14
ADX_TREND_THRESH  = 20

# ---- Session filter (UTC) ----
LONDON_OPEN       = 7
LONDON_CLOSE      = 16
NY_OPEN           = 12
NY_CLOSE          = 21

# ---- Pip / spread ----
PIP_SIZE          = 0.0001     # EUR/USD standard pip
MAX_SPREAD_PIPS   = 3.0        # skip signals if live spread is wider than this

# FIX: spread cost was checked as an entry filter but never actually
# subtracted from P&L in either backtest script. This charges it once
# per round-trip trade (buy at ask / sell at bid ~= one spread width).
SPREAD_PIPS       = 1.2        # typical EUR/USD spread, charged per trade in backtests

# FIX: backtests were entering at the same bar's close that generated
# the signal, which assumes a fill you couldn't actually get (you only
# know the bar closed above/below a level once it has already closed).
# When True, backtests fill at the *next* bar's open instead.
ENTRY_ON_NEXT_OPEN = True

# ---- Train/test split ----
# Tune and iterate using --split train only. Run --split test exactly
# once, at the end, as a holdout check — if a filter change only helps
# on train but not test, it was overfit, not improved. Don't go back and
# retune based on what test shows; that just moves the overfitting onto
# a bigger dataset.
SPLIT = {
    "train_start": "2022-01-01",
    "train_end":   "2024-12-31",
    "test_start":  "2025-01-01",
    "test_end":    None,   # None = through whatever data you have
}

# ---- Data files ----
DATA_DIR          = "data"
SYMBOL            = "EURUSD"

# ---- Backtest settings ----
BACKTEST = {
    "intraday": {
        "require_session":  True,     # hard session gate
        "time_exit_bars":   96,       # 24h on M15
        "cooldown_bars":    16,       # 4h on M15
        "max_trades":       1,        # maximum simultaneous open trades
    },
    "scalp": {
        "require_session":  False,
        "time_exit_bars":   None,     # let it run
        "cooldown_bars":    4,        # 1h on M15
        "max_trades":       1,        # maximum simultaneous open trades
    },
}

# ---- Breakout Strategy ----
BREAKOUT = {
    # Asian session range (UTC hours)
    "asian_start_hour": 0,
    "asian_end_hour":   6,

    # Entry window (UTC)
    "entry_start_hour": 7,
    "entry_end_hour":   11,

    # Force-close time
    "session_close_hour": 20,

    # Range size filter (pips)
    "min_range_pips": 15,
    "max_range_pips": 60,

    # Volatility expansion filter
    "atr_fast": 14,
    "atr_slow": 96,          # ~1 day on M15
    "atr_expansion_min": 1.0,

    # Trend filters (set False to disable and test without)
    "use_h4_trend":  True,
    "use_d1_trend":  True,

    # Optional extra trend-strength filter: require ADX(HTF) >= min_adx_ht
    # in addition to EMA order agreeing. Off by default — turn on and
    # re-run the backtest to measure its effect on trade count/win rate
    # in isolation before deciding to keep it.
    "use_adx_filter": False,
    "min_adx_ht":     25,

    # Risk
    "stop_buffer_atr": 0.5,  # extra buffer on stop = 0.5 x ATR(M15)
    "min_stop_pips":   12,
    "tp1_range_mult":  1.0,  # TP1 = range x this
    "tp2_range_mult":  1.5,

    # Reference levels for backtest (not used live)
    "trades_per_day":  1,
}
