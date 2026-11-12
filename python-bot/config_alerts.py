"""
config_alerts.py
-----------------
Settings for the alerts product (Telegram, paper-trade DB, Laravel API).
Drop this alongside your existing config.py in the Xfx project — it
imports from it rather than duplicating anything.

Fill in the values marked CHANGE_ME before running run_live.py.
"""

import config as cfg  # your existing config.py

# ---- Which strategy feeds the alerts ----
# "breakout" -> breakout_engine.evaluate_day
# "confluence" -> signal_engine.evaluate (mode below)
STRATEGY = "breakout"
CONFLUENCE_MODE = "intraday"   # only used if STRATEGY == "confluence"

# ---- Telegram ----
# Create a bot: message @BotFather on Telegram -> /newbot -> copy the token.
# Get your chat_id: message your new bot once, then visit
#   https://api.telegram.org/bot<TOKEN>/getUpdates
# and read "chat":{"id": ...} from the response. For a channel, add the
# bot as admin and use the channel's @username as the chat_id instead.
TELEGRAM_BOT_TOKEN = "CHANGE_ME"
TELEGRAM_CHAT_ID   = "CHANGE_ME"

# ---- Live polling ----
POLL_INTERVAL_SECONDS = 60      # how often run_live.py checks for a new bar/signal
TIMEZONE_NOTE = "All times UTC, matching your parquet data and MT5 server-adjusted feed."

# ---- Paper-trade log ----
PAPER_DB_PATH = "paper_signals.db"

# ---- Laravel API (subscriber layer — leave DISABLED until you have real subscribers) ----
LARAVEL_API_ENABLED = False
LARAVEL_API_URL     = "https://your-domain.example.com/api/signals"
LARAVEL_API_KEY      = "CHANGE_ME"   # must match VerifyApiKey middleware on the Laravel side
