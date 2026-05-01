"""Weather data from Open-Meteo API with offline cache fallback."""

import json
import socket
import time
from pathlib import Path

import requests

from . import atomic_write_json

try:
    import subprocess as _sp
    _tz = _sp.check_output(
        ["readlink", "/etc/localtime"], text=True
    ).strip().split("zoneinfo/")[-1]
except Exception:
    _tz = "America/Los_Angeles"
_SYSTEM_TIMEZONE = _tz or "America/Los_Angeles"

_CACHE_FILE = Path(__file__).parent.parent / ".weather_cache.json"
_CACHE_MAX_AGE = 3 * 3600  # 3 hours — weather changes fast enough

WMO_CODES = {
    0: ("Clear", "\u2600\ufe0f"), 1: ("Mostly Clear", "\U0001f324\ufe0f"),
    2: ("Partly Cloudy", "\u26c5"), 3: ("Overcast", "\u2601\ufe0f"),
    45: ("Foggy", "\U0001f32b\ufe0f"), 48: ("Icy Fog", "\U0001f32b\ufe0f"),
    51: ("Light Drizzle", "\U0001f326\ufe0f"), 53: ("Drizzle", "\U0001f326\ufe0f"),
    55: ("Heavy Drizzle", "\U0001f326\ufe0f"),
    56: ("Light Freezing Drizzle", "\U0001f326\ufe0f"), 57: ("Freezing Drizzle", "\U0001f326\ufe0f"),
    61: ("Light Rain", "\U0001f327\ufe0f"), 63: ("Rain", "\U0001f327\ufe0f"),
    65: ("Heavy Rain", "\U0001f327\ufe0f"),
    66: ("Light Freezing Rain", "\U0001f327\ufe0f"), 67: ("Freezing Rain", "\U0001f327\ufe0f"),
    71: ("Light Snow", "\U0001f328\ufe0f"), 73: ("Snow", "\U0001f328\ufe0f"),
    75: ("Heavy Snow", "\U0001f328\ufe0f"),
    77: ("Snow Grains", "\U0001f328\ufe0f"),
    80: ("Light Showers", "\U0001f326\ufe0f"), 81: ("Showers", "\U0001f327\ufe0f"),
    82: ("Heavy Showers", "\U0001f327\ufe0f"),
    85: ("Light Snow Showers", "\U0001f328\ufe0f"), 86: ("Heavy Snow Showers", "\U0001f328\ufe0f"),
    95: ("Thunderstorm", "\u26c8\ufe0f"), 96: ("Thunderstorm + Hail", "\u26c8\ufe0f"),
    99: ("Thunderstorm + Heavy Hail", "\u26c8\ufe0f"),
}


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data):
    atomic_write_json(_CACHE_FILE, data)


def _dns_ok(host="api.open-meteo.com", timeout=2):
    try:
        with socket.create_connection((host, 443), timeout=timeout):
            return True
    except Exception:
        return False


def get_weather(latitude, longitude, force_refresh=False):
    """Get current weather and 5-day forecast from Open-Meteo (free, no API key).
    Falls back to cached data when offline."""
    cache = _load_cache()
    now = time.time()
    cache_key = f"{latitude},{longitude}"
    cached = cache.get(cache_key)

    # Return cache immediately if it's still fresh — no DNS check needed
    if not force_refresh and cached and (now - cached["ts"]) < _CACHE_MAX_AGE:
        age_min = int((now - cached["ts"]) / 60)
        print(f"  Weather: {cached['data']['current_temp']}\u00b0F, {cached['data']['current_desc']} (cached {age_min} min ago)")
        return cached["data"]

    # Cache is stale or missing — check network before trying
    if not _dns_ok():
        if cached:
            age_min = int((now - cached["ts"]) / 60)
            print(f"  Weather: offline, using stale cache ({age_min} min old)")
            return cached["data"]
        print("  Weather: offline and no usable cache")
        return None

    try:
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "forecast_days": 5,
            "temperature_unit": "fahrenheit",
            "timezone": _SYSTEM_TIMEZONE,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current", {})
        code = current.get("weather_code", 0)
        desc, icon = WMO_CODES.get(code, ("Unknown", "\u2753"))
        weather = {
            "current_temp": round(current.get("temperature_2m", 0)),
            "current_desc": desc,
            "current_icon": icon,
            "forecast": [],
        }

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        codes = daily.get("weather_code", [])
        for i in range(len(dates)):
            fc_desc, fc_icon = WMO_CODES.get(codes[i] if i < len(codes) else 0, ("Unknown", "\u2753"))
            weather["forecast"].append({
                "date": dates[i],
                "high": round(highs[i]) if i < len(highs) else 0,
                "low": round(lows[i]) if i < len(lows) else 0,
                "desc": fc_desc,
                "icon": fc_icon,
            })

        cache[cache_key] = {"ts": now, "data": weather}
        _save_cache(cache)
        print(f"  Weather: {weather['current_temp']}\u00b0F, {weather['current_desc']}")
        return weather

    except Exception as e:
        print(f"  Weather error: {e}")
        if cached and (now - cached["ts"]) < _CACHE_MAX_AGE:
            age_min = int((now - cached["ts"]) / 60)
            print(f"  Weather: using cached data ({age_min} min old)")
            return cached["data"]
        return None
