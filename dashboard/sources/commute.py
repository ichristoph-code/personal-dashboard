"""Commute time estimate using OSRM (free, no API key required).

Uses OpenStreetMap's Nominatim to geocode a work address and OSRM to
estimate drive time from home. Results are cached for 6 hours.
Uses curl subprocess to avoid macOS LibreSSL TLS compatibility issues.
"""

import json
import subprocess
import time
import urllib.parse
from pathlib import Path

from . import atomic_write_json

_CACHE_FILE  = Path(__file__).parent.parent / ".commute_cache.json"
_CACHE_MAX_AGE = 6 * 3600  # 6 hours

_OSRM_URL    = "https://routing.openstreetmap.de/routed-car/route/v1/driving/{},{};{},{}?overview=false"
_GEOCODE_URL = "https://nominatim.openstreetmap.org/search?q={}&format=json&limit=1"


def _curl_json(url):
    """Fetch a URL via curl (sidesteps macOS LibreSSL TLS handshake issues)."""
    result = subprocess.run(
        ["curl", "-s", "--max-time", "10", "-A", "PersonalDashboard/1.0", url],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def _geocode(address):
    """Return (lat, lon) for an address string, or None."""
    url = _GEOCODE_URL.format(urllib.parse.quote(address))
    try:
        data = _curl_json(url)
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"  Commute geocode error: {e}")
    return None


def _route_minutes(home_lat, home_lon, work_lat, work_lon):
    """Return estimated drive time in minutes via OSRM, or None."""
    url = _OSRM_URL.format(home_lon, home_lat, work_lon, work_lat)
    try:
        data = _curl_json(url)
        routes = (data or {}).get("routes", [])
        if routes:
            return round(routes[0]["duration"] / 60)
    except Exception as e:
        print(f"  Commute routing error: {e}")
    return None


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def get_commute(home_lat, home_lon, work_address):
    """Return commute info dict, or None if unconfigured."""
    if not work_address:
        return None

    cache = _load_cache()
    now = time.time()
    if cache and (now - cache.get("ts", 0)) < _CACHE_MAX_AGE:
        print(f"  Commute: using cached ({round((now - cache['ts'])/3600, 1)}h old)")
        return cache.get("data")

    work_coords = cache.get("work_coords")
    if not work_coords:
        coords = _geocode(work_address)
        if not coords:
            return None
        work_coords = {"lat": coords[0], "lon": coords[1]}

    minutes = _route_minutes(home_lat, home_lon, work_coords["lat"], work_coords["lon"])
    if minutes is None:
        return cache.get("data")

    maps_url = (
        f"https://maps.apple.com/?saddr={home_lat},{home_lon}"
        f"&daddr={urllib.parse.quote(work_address)}&dirflg=d"
    )

    result = {
        "work_address": work_address,
        "minutes":      minutes,
        "maps_url":     maps_url,
    }

    atomic_write_json(_CACHE_FILE, {
        "ts":          now,
        "work_coords": work_coords,
        "data":        result,
    })
    print(f"  Commute: ~{minutes} min to {work_address}")
    return result
