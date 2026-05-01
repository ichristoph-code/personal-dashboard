"""SF Bay Area event feeds — RSS-based, no API key required."""

import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from . import atomic_write_json

_CACHE_FILE = Path(__file__).parent.parent / ".events_cache.json"
_CACHE_MAX_AGE = 6 * 3600  # 6 hours

DEFAULT_EVENT_FEEDS = [
    {"name": "Funcheap SF",    "url": "https://sf.funcheap.com/feed/"},
    {"name": "The Bold Italic", "url": "https://thebolditalic.com/feed"},
    {"name": "48 Hills",       "url": "https://48hills.org/feed/"},
]

# Title words that indicate news rather than events — filtered out
_NEWS_WORDS = {
    "arrested", "shooting", "stabbing", "homicide", "murder", "killed",
    "crash", "lawsuit", "indicted", "convicted", "charged", "pleads",
    "election", "votes", "ballot", "supervisor", "mayor", "governor",
    "budget", "legislation", "ordinance", "hearing", "police", "fire dept",
    "earthquake", "protests", "rally", "strike",
}

_MEDIA_NS  = "http://search.yahoo.com/mrss/"
_DC_NS     = "http://purl.org/dc/elements/1.1/"
_ATOM_NS   = "http://www.w3.org/2005/Atom"
_IMG_RE    = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_TAG_RE    = re.compile(r'<[^>]+>')


def _extract_image(item):
    """Try several RSS image conventions, return URL or ''."""
    # <media:content url="...">
    mc = item.find(f"{{{_MEDIA_NS}}}content")
    if mc is not None and mc.get("url"):
        return mc.get("url")
    # <media:thumbnail url="...">
    mt = item.find(f"{{{_MEDIA_NS}}}thumbnail")
    if mt is not None and mt.get("url"):
        return mt.get("url")
    # <enclosure url="..." type="image/...">
    enc = item.find("enclosure")
    if enc is not None and (enc.get("type", "").startswith("image") or enc.get("url", "").endswith((".jpg", ".png", ".webp"))):
        return enc.get("url", "")
    # img tag inside <description>
    desc = item.findtext("description") or ""
    m = _IMG_RE.search(desc)
    if m:
        return m.group(1)
    return ""


def _extract_description(item):
    """Return a short plain-text snippet from <description>."""
    raw = item.findtext("description") or item.findtext(f"{{{_ATOM_NS}}}summary") or ""
    plain = _TAG_RE.sub(" ", raw).strip()
    plain = re.sub(r'\s+', ' ', plain)
    return plain[:200].rsplit(' ', 1)[0] + '…' if len(plain) > 200 else plain


def _parse_items(root, name):
    items = root.findall('.//item')
    if not items:
        items = root.findall(f'.//{{{_ATOM_NS}}}entry')
    result = []
    for item in items[:12]:
        title = (item.findtext('title')
                 or item.findtext(f'{{{_ATOM_NS}}}title') or '').strip()
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
                "description": _extract_description(item),
                "image":       _extract_image(item),
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


def get_sf_events(feeds=None):
    """Fetch SF event posts from RSS feeds, with per-feed cache fallback."""
    feeds = feeds or DEFAULT_EVENT_FEEDS
    cache = _load_cache()
    cache_updated = False
    now = time.time()

    all_items = []

    for feed_cfg in feeds:
        name = feed_cfg.get("name", "Events")
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
            print(f"  Events feed error ({name}): {e}")

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

    # Drop items whose titles look like news rather than events
    def _is_news(item):
        title_lower = item["title"].lower()
        return any(word in title_lower for word in _NEWS_WORDS)

    all_items = [i for i in all_items if not _is_news(i)]

    # Restore parsed_date as datetime for the builder
    for item in all_items:
        ds = item.get("parsed_date")
        if ds:
            try:
                item["parsed_date"] = datetime.fromisoformat(ds)
            except Exception:
                item["parsed_date"] = None
        else:
            item["parsed_date"] = None

    print(f"  Events: {len(all_items)} items from {len(feeds)} feeds")
    return all_items if all_items else None
