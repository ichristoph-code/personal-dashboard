"""
Data source modules for the Personal Dashboard.
Each module handles one external data source.
"""

import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(path: Path, data):
    """Write JSON to a file atomically (write tmp then rename).

    Prevents corrupted cache files if the process crashes mid-write.
    """
    try:
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f)
            os.replace(tmp, path)  # atomic on POSIX
        except BaseException:
            os.unlink(tmp)
            raise
    except Exception as e:
        print(f"  Warning: failed to write {path}: {e}")

from .things import get_things_tasks  # noqa: F401, E402
from .calendar import get_calendar_events  # noqa: F401, E402
from .weather import get_weather  # noqa: F401, E402
from .mail import get_mail_messages  # noqa: F401, E402
from .news import get_news_headlines  # noqa: F401, E402
from .imessage import get_imessages  # noqa: F401, E402
from .notes import get_apple_notes, create_note, update_note, delete_note, clear_notes_cache  # noqa: F401, E402
from .market import get_market_data  # noqa: F401, E402
from .system import get_system_info, get_network_speed  # noqa: F401, E402
from .claude_review import generate_financial_review, query_claude_financial  # noqa: F401, E402
from .contacts import get_all_contacts, get_upcoming_birthdays  # noqa: F401, E402
from .events import get_sf_events  # noqa: F401, E402
from .journals import get_journal_articles  # noqa: F401, E402
from .briefing import generate_morning_briefing  # noqa: F401, E402
from .commute import get_commute  # noqa: F401, E402

_BASE_DIR = Path(__file__).parent.parent
_CACHE_FILES = [
    _BASE_DIR / ".things_cache.json",
    _BASE_DIR / ".calendar_cache.json",
    _BASE_DIR / ".weather_cache.json",
    _BASE_DIR / ".mail_cache.json",
    # Intentionally excluded (each manages its own TTL + fallback):
    #   .news_cache.json   — 24h cache, used as fallback on transient errors
    #   .notes_cache.json  — 30min cache, AppleScript is slow (~5-30s)
    #   .net_speed_cache.json — 30min cache, networkQuality takes ~20s
    #   .hw_cache.json     — permanent, hardware never changes
]

# Maps source names to their cache files (for selective clearing)
_SOURCE_CACHE_MAP = {
    "things":   _BASE_DIR / ".things_cache.json",
    "calendar": _BASE_DIR / ".calendar_cache.json",
    "weather":  _BASE_DIR / ".weather_cache.json",
    "mail":     _BASE_DIR / ".mail_cache.json",
    "notes":    _BASE_DIR / ".notes_cache.json",
    "events":   _BASE_DIR / ".events_cache.json",
    "journals": _BASE_DIR / ".journals_cache.json",
}


def clear_all_caches():
    """Remove all source cache files so the next fetch reads fresh data."""
    for cache in _CACHE_FILES:
        if cache.exists():
            cache.unlink()


def clear_caches_for_sources(sources: set):
    """Clear only the cache files for the specified source names.

    Sources without a cache file (e.g. 'imessages', 'market') are silently
    skipped — they always fetch fresh data anyway.
    """
    for name, path in _SOURCE_CACHE_MAP.items():
        if name in sources and path.exists():
            path.unlink()
