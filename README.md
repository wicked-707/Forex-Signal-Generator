# Forex Alerts Product

Three pieces, built to be adopted in order:

## 1. python-bot/
Your existing Xfx project files (already fixed for look-ahead bias,
spread cost, next-bar-open entry, train/test split) plus new alerts
infrastructure:
  - config_alerts.py   - settings for Telegram/DB/Laravel (fill in the CHANGE_ME values)
  - telegram_notifier.py - posts signals to a Telegram chat (tested, works standalone)
  - signal_store.py    - SQLite log of every live signal + real outcome (tested, works)
  - outcome_tracker.py - closes open signals out against live price (TP/SL/time-exit)
  - run_live.py        - the scheduler loop tying it all together (needs MT5 + real credentials to run)
  - api_client.py       - posts signals to the Laravel API once you enable it

Copy these into your existing Xfx project folder (they assume config.py,
signal_engine.py, breakout_engine.py already exist there — copies of the
already-fixed versions are included here too, for a clean drop-in).

Run with: `python run_live.py` (after filling in config_alerts.py).

## 2. laravel-api/
Migrations, models, controller, queued job, notification channels, and
M-Pesa/Paystack service skeletons for the subscriber layer. See
laravel-api/SETUP.md for exact steps — these are written to be dropped
into an existing or new Laravel app; they were not run through
`composer install` in this sandbox (no packagist access here), so test
in your own environment first.

## 3. react-dashboard/
A Vite + React dashboard reading from the Laravel API. Already
`npm install`'d and `npm run build`'d successfully in this sandbox — it
compiles cleanly. Set VITE_API_BASE_URL to your Laravel API's URL.

## Order of operations
1. Get python-bot/run_live.py posting to Telegram, to yourself only.
2. Let it run and log real outcomes via signal_store.py for a genuine
   stretch of time.
3. Only once signal_store.performance_summary() shows something worth
   sharing, stand up laravel-api/ and open LARAVEL_API_ENABLED.
4. Add payments (M-Pesa/Paystack) once you have people who actually want
   to pay.
5. react-dashboard/ last — it's the least urgent piece.
