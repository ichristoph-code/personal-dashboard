"""Calendar events via CalHelper.app bundle with cache fallback."""

import json
import subprocess
import time
from pathlib import Path

from . import atomic_write_json

_CACHE_FILE = Path(__file__).parent.parent / ".calendar_cache.json"
_CACHE_MAX_AGE = 2 * 3600  # 2 hours — calendar changes frequently


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data):
    atomic_write_json(_CACHE_FILE, data)


def get_calendar_events(force_refresh=False):
    """Get upcoming calendar events using the CalHelper.app bundle.
    Falls back to cached events if CalHelper is unavailable.
    """
    cache = _load_cache()
    now = time.time()
    cached = cache.get("events")

    cal_helper_app = Path(__file__).parent.parent / "apps" / "CalHelper.app"
    if not cal_helper_app.exists():
        cal_helper_app = Path(__file__).parent.parent / "CalHelper.app"

    if not cal_helper_app.exists():
        print("  CalHelper.app not found.")
        if cached and (now - cached["ts"]) < _CACHE_MAX_AGE:
            age_min = int((now - cached["ts"]) / 60)
            print(f"  Using cached calendar data ({age_min} min old)")
            return cached["data"]
        return None

    output_file = Path("/tmp/cal_helper_output.txt")

    try:
        if output_file.exists():
            output_file.unlink()

        subprocess.run(
            ["open", "-W", str(cal_helper_app)],
            capture_output=True, text=True, timeout=45
        )

        if not output_file.exists():
            raise RuntimeError("CalHelper produced no output")

        output = output_file.read_text().strip()

        if output.startswith("ERROR:"):
            raise RuntimeError(output[6:])

        events = []
        for line in output.split('\n'):
            if '|||' not in line:
                continue
            parts = line.split('|||')
            if len(parts) >= 5:
                events.append({
                    "calendar": parts[0],
                    "title": parts[1],
                    "start": parts[2],
                    "end": parts[3],
                    "all_day": parts[4] == "1",
                    "location": parts[5] if len(parts) > 5 else "",
                    "event_id": parts[6] if len(parts) > 6 else "",
                })

        events.sort(key=lambda e: e["start"])
        cache["events"] = {"ts": now, "data": events}
        _save_cache(cache)
        print(f"  Found {len(events)} calendar events")
        return events

    except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError, Exception) as e:
        print(f"  Calendar error: {e}")
        if cached and (now - cached["ts"]) < _CACHE_MAX_AGE:
            age_min = int((now - cached["ts"]) / 60)
            print(f"  Using cached calendar data ({age_min} min old)")
            return cached["data"]
        return None
