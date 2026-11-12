"""
signal_store.py
----------------
SQLite log of every signal fired live and what actually happened to it.
This is the real track record — kept separate from backtest CSVs on
purpose, so the two are never confused with each other.

Usage:
    from signal_store import init_db, log_signal, get_open_signals, close_signal, performance_summary
    init_db()
    signal_id = log_signal(signal_dict)
    ...
    close_signal(signal_id, exit_price=..., exit_reason="TP", pips_result=..., r_multiple=...)
"""

import sqlite3
from datetime import datetime, timezone

import config_alerts as acfg

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy      TEXT NOT NULL,
    day           TEXT,
    signal_time   TEXT NOT NULL,
    direction     TEXT NOT NULL,
    entry_price   REAL NOT NULL,
    stop_loss     REAL NOT NULL,
    take_profit   REAL NOT NULL,
    stop_pips     REAL NOT NULL,
    lot_size      REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'OPEN',   -- OPEN | CLOSED
    exit_time     TEXT,
    exit_price    REAL,
    exit_reason   TEXT,
    pips_result   REAL,
    r_multiple    REAL,
    created_at    TEXT NOT NULL,
    notified      INTEGER NOT NULL DEFAULT 0
);
"""


def _connect():
    conn = sqlite3.connect(acfg.PAPER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


def already_logged(day, direction, strategy):
    """Prevent double-alerting the same day's signal if run_live.py polls more than once."""
    conn = _connect()
    row = conn.execute(
        "SELECT id FROM signals WHERE day = ? AND direction = ? AND strategy = ?",
        (day, direction, strategy),
    ).fetchone()
    conn.close()
    return row is not None


def log_signal(signal, strategy):
    """signal: dict as produced by breakout_engine.evaluate_day or signal_engine.evaluate."""
    conn = _connect()
    cur = conn.execute(
        """
        INSERT INTO signals (
            strategy, day, signal_time, direction, entry_price, stop_loss,
            take_profit, stop_pips, lot_size, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            strategy,
            signal.get("day"),
            str(signal.get("time", signal.get("entry_time"))),
            signal["signal"] if "signal" in signal else signal.get("direction"),
            signal.get("entry", signal.get("entry_price")),
            signal.get("stop_loss"),
            signal.get("tp1", signal.get("take_profit_1")),
            signal.get("stop_pips"),
            signal.get("lot_size"),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    signal_id = cur.lastrowid
    conn.close()
    return signal_id


def get_open_signals():
    conn = _connect()
    rows = conn.execute("SELECT * FROM signals WHERE status = 'OPEN'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def close_signal(signal_id, exit_price, exit_reason, pips_result, r_multiple):
    conn = _connect()
    conn.execute(
        """
        UPDATE signals
        SET status = 'CLOSED', exit_time = ?, exit_price = ?, exit_reason = ?,
            pips_result = ?, r_multiple = ?
        WHERE id = ?
        """,
        (datetime.now(timezone.utc).isoformat(), exit_price, exit_reason,
         pips_result, r_multiple, signal_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
    conn.close()
    return dict(row)


def performance_summary():
    """Real (live) performance to date — separate from any backtest number."""
    conn = _connect()
    rows = conn.execute("SELECT * FROM signals WHERE status = 'CLOSED'").fetchall()
    conn.close()
    rows = [dict(r) for r in rows]

    if not rows:
        return {"total_trades": 0, "message": "No closed live signals yet."}

    wins = [r for r in rows if r["r_multiple"] and r["r_multiple"] > 0]
    total_r = sum(r["r_multiple"] for r in rows if r["r_multiple"] is not None)

    return {
        "total_trades": len(rows),
        "wins": len(wins),
        "win_rate_pct": round(len(wins) / len(rows) * 100, 2),
        "avg_r": round(total_r / len(rows), 3),
        "total_r": round(total_r, 2),
    }


if __name__ == "__main__":
    # Quick smoke test
    init_db()
    print("DB initialized at", acfg.PAPER_DB_PATH)
    print("Open signals:", get_open_signals())
    print("Performance so far:", performance_summary())
