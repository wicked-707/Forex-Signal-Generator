"""
api_client.py
--------------
Posts a signal to the Laravel API (subscriber layer). Only used once
config_alerts.LARAVEL_API_ENABLED is True and you've deployed the
Laravel app in ../laravel-api.
"""

import requests
import config_alerts as acfg


def post_signal_to_laravel(signal, strategy):
    if not acfg.LARAVEL_API_ENABLED:
        return None

    payload = {
        "strategy": strategy,
        "day": signal.get("day"),
        "signal_time": str(signal.get("time", signal.get("entry_time"))),
        "direction": signal.get("signal", signal.get("direction")),
        "entry_price": signal.get("entry", signal.get("entry_price")),
        "stop_loss": signal.get("stop_loss"),
        "take_profit": signal.get("tp1", signal.get("take_profit_1")),
        "stop_pips": signal.get("stop_pips"),
        "lot_size": signal.get("lot_size"),
        "reasons": signal.get("reasons", []),
    }
    headers = {"X-API-Key": acfg.LARAVEL_API_KEY}

    try:
        resp = requests.post(acfg.LARAVEL_API_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[api_client] Failed to post signal to Laravel: {e}")
        return None
