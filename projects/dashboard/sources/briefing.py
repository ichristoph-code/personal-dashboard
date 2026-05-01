"""AI morning briefing using the Claude API.

Generates a warm 2-3 sentence summary of the day ahead.
Cached by date — regenerates each morning, not on every dashboard load.
"""

import json
import time
from datetime import datetime
from pathlib import Path

import requests

from . import atomic_write_json

_CACHE_FILE = Path(__file__).parent.parent / ".briefing_cache.json"


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            cached = json.loads(_CACHE_FILE.read_text())
            if cached.get("date") == datetime.now().strftime("%Y-%m-%d"):
                return cached.get("text")
    except Exception:
        pass
    return None


def _load_any_cache():
    """Return the most recent briefing text regardless of date (used as fallback)."""
    try:
        if _CACHE_FILE.exists():
            cached = json.loads(_CACHE_FILE.read_text())
            return cached.get("text")
    except Exception:
        pass
    return None


def generate_morning_briefing(api_key, data):
    """Generate a short morning briefing paragraph.

    Args:
        api_key: Anthropic API key.
        data: dict with keys: weather, today_events, today_tasks,
              net_worth, ready_to_assign, unread_mail, unread_imessages.

    Returns:
        Plain text string (2-3 sentences), or None on failure.
    """
    if not api_key:
        return None

    cached = _load_cache()
    if cached:
        print("  Briefing: using cached (today's)")
        return cached

    now = datetime.now()
    hour = now.hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"

    # Build a lean summary for the prompt
    summary = {
        "time_of_day": time_of_day,
        "date": now.strftime("%A, %B %-d"),
    }
    if data.get("weather"):
        w = data["weather"]
        summary["weather"] = f'{w.get("current_temp")}°F, {w.get("current_desc")}'
        fc = w.get("forecast", [])
        if fc:
            summary["today_high_low"] = f'H:{fc[0].get("high")}° L:{fc[0].get("low")}°'
    summary["calendar_events_today"] = data.get("today_events", [])[:6]
    summary["tasks_due_today"] = data.get("today_tasks", [])[:5]
    if data.get("unread_mail"):
        summary["unread_emails"] = data["unread_mail"]
    if data.get("unread_imessages"):
        summary["unread_messages"] = data["unread_imessages"]

    prompt = (
        f"You are Ian's personal assistant. Write a warm, natural {time_of_day} briefing "
        f"in exactly 2-3 sentences. Be specific — mention real events, tasks, and conditions "
        f"from the data. No bullet points, no headers, just flowing prose. "
        f"Keep it under 60 words.\n\n"
        f"Data:\n{json.dumps(summary, indent=2)}"
    )

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 150,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip()
        atomic_write_json(_CACHE_FILE, {
            "date": now.strftime("%Y-%m-%d"),
            "ts": time.time(),
            "text": text,
        })
        print("  Briefing: generated fresh")
        return text
    except Exception as e:
        print(f"  Briefing failed: {e}")
        return _load_any_cache()
