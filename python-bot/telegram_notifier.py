"""
telegram_notifier.py
---------------------
Sends signal alerts to a Telegram chat/channel via the plain Bot API
(no heavy dependency — just `requests`).

Usage:
    from telegram_notifier import send_signal_alert, send_closed_alert
    send_signal_alert(signal_dict)
"""

import requests
import config_alerts as acfg


def _send_message(text):
    if acfg.TELEGRAM_BOT_TOKEN == "CHANGE_ME" or acfg.TELEGRAM_CHAT_ID == "CHANGE_ME":
        print("[telegram_notifier] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — "
              "printing instead of sending:\n" + text)
        return None

    url = f"https://api.telegram.org/bot{acfg.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": acfg.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[telegram_notifier] Failed to send message: {e}")
        return None


def format_signal_message(signal):
    """signal: dict with day/time/signal/entry/stop_loss/tp1/stop_pips/lot_size/reasons."""
    direction_emoji = "🟢" if signal["signal"] == "BUY" else "🔴"
    lines = [
        f"{direction_emoji} <b>{signal['signal']} EURUSD</b>",
        f"Time: {signal.get('time', signal.get('entry_time', ''))}",
        f"Entry: <code>{signal.get('entry', signal.get('entry_price'))}</code>",
        f"SL: <code>{signal.get('stop_loss')}</code>  ({signal.get('stop_pips')} pips)",
        f"TP1: <code>{signal.get('tp1', signal.get('take_profit_1'))}</code>",
        f"Lot: {signal.get('lot_size')}",
    ]
    reasons = signal.get("reasons")
    if reasons:
        lines.append("")
        lines.append("Reasons:")
        for r in reasons:
            lines.append(f"  • {r}")
    lines.append("")
    lines.append("⚠️ Paper/testing signal — not a validated live edge yet.")
    return "\n".join(lines)


def send_signal_alert(signal):
    text = format_signal_message(signal)
    return _send_message(text)


def send_closed_alert(signal_row):
    """signal_row: a dict/Row from signal_store with exit info populated."""
    emoji = "✅" if signal_row["r_multiple"] > 0 else "❌"
    text = (
        f"{emoji} Closed: {signal_row['direction']} EURUSD\n"
        f"Exit reason: {signal_row['exit_reason']}\n"
        f"R multiple: {signal_row['r_multiple']:.2f}\n"
        f"Signal id: {signal_row['id']}"
    )
    return _send_message(text)


def send_text(text):
    """Free-form message — startup notices, errors, daily summaries, etc."""
    return _send_message(text)
