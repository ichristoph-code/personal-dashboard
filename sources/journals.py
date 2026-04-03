"""Cardiology journal feeds — RSS-based, no API key required."""

import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from . import atomic_write_json

_CACHE_FILE = Path(__file__).parent.parent / ".journals_cache.json"
_CACHE_MAX_AGE = 12 * 3600  # 12 hours (journals publish infrequently)

DEFAULT_JOURNAL_FEEDS = [
    {"name": "Healio Cardiology", "url": "https://www.healio.com/rss/cardiology"},
    {"name": "Medpage Cardiology", "url": "https://www.medpagetoday.com/rss/cardiology.xml"},
    {"name": "Cardiobrief",        "url": "https://cardiobrief.org/feed/"},
]

_DC_NS   = "http://purl.org/dc/elements/1.1/"
_ATOM_NS = "http://www.w3.org/2005/Atom"


def _parse_items(root, name):
    items = root.findall('.//item') or root.findall(f'.//{{{_ATOM_NS}}}entry')
    result = []
    for item in items[:15]:
        title = (item.findtext('title') or item.findtext(f'{{{_ATOM_NS}}}title') or '').strip()
        link = item.findtext('link') or ''
        if not link:
            link_el = item.find(f'{{{_ATOM_NS}}}link')
            if link_el is not None:
                link = link_el.get('href', '')
        pub = (item.findtext('pubDate')
               or item.findtext(f'{{{_DC_NS}}}date')
               or item.findtext(f'{{{_ATOM_NS}}}updated') or '').strip()
        parsed_dt = None
        if pub:
            try:
                parsed_dt = parsedate_to_datetime(pub)
            except Exception:
                try:
                    parsed_dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
                except Exception:
                    pass
        if title:
            result.append({
                "title":       title,
                "link":        link.strip(),
                "date":        pub,
                "parsed_date": parsed_dt.isoformat() if parsed_dt else None,
                "source":      name,
            })
    return result


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def get_journal_articles(feeds=None):
    """Fetch cardiology journal articles from RSS feeds."""
    feeds = feeds or DEFAULT_JOURNAL_FEEDS
    cache = _load_cache()
    cache_updated = False
    now = time.time()
    all_items = []

    for feed_cfg in feeds:
        name = feed_cfg.get("name", "Journal")
        url  = feed_cfg.get("url", "")
        if not url:
            continue

        fetched = None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PersonalDashboard/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                tree = ET.parse(resp)
            fetched = _parse_items(tree.getroot(), name)
            cache[name] = {"ts": now, "items": fetched}
            cache_updated = True
        except Exception as e:
            print(f"  Journal feed error ({name}): {e}")

        if fetched is None:
            cached = cache.get(name, {})
            if cached and (now - cached.get("ts", 0)) < _CACHE_MAX_AGE:
                fetched = cached.get("items", [])

        if fetched:
            all_items.extend(fetched)

    if cache_updated:
        atomic_write_json(_CACHE_FILE, cache)

    # Sort newest-first
    epoch = datetime(1970, 1, 1)
    def _sort_key(h):
        ds = h.get("parsed_date")
        if not ds:
            return epoch
        try:
            dt = datetime.fromisoformat(ds)
            return dt.replace(tzinfo=None)
        except Exception:
            return epoch

    all_items.sort(key=_sort_key, reverse=True)

    # Restore parsed_date as datetime
    for item in all_items:
        ds = item.get("parsed_date")
        if ds:
            try:
                item["parsed_date"] = datetime.fromisoformat(ds)
            except Exception:
                item["parsed_date"] = None
        else:
            item["parsed_date"] = None

    print(f"  Journals: {len(all_items)} articles from {len(feeds)} feeds")
    return all_items if all_items else None
