"""RSS news feed headlines with offline cache fallback."""

import json
import time
import xml.etree.ElementTree as ET
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from . import atomic_write_json

_CACHE_FILE = Path(__file__).parent.parent / ".news_cache.json"
_CACHE_MAX_AGE = 24 * 3600  # show cached news up to 24 hours old


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data: dict):
    atomic_write_json(_CACHE_FILE, data)


def _parse_items(root, name):
    """Extract headline dicts from a parsed RSS/Atom XML root."""
    items = root.findall('.//item')  # RSS 2.0
    if not items:
        # RDF/RSS 1.0 — items use the http://purl.org/rss/1.0/ namespace
        rss1_ns = {'rss1': 'http://purl.org/rss/1.0/'}
        items = root.findall('.//rss1:item', rss1_ns)
    if not items:
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//atom:entry', ns)
    result = []
    dc_ns = 'http://purl.org/dc/elements/1.1/'
    rss1_ns_uri = 'http://purl.org/rss/1.0/'
    for item in items[:10]:
        title = (item.findtext('title')
                 or item.findtext(f'{{{rss1_ns_uri}}}title')
                 or item.findtext('{http://www.w3.org/2005/Atom}title') or '')
        link = item.findtext('link') or item.findtext(f'{{{rss1_ns_uri}}}link') or ''
        if not link:
            link_el = item.find('{http://www.w3.org/2005/Atom}link')
            if link_el is not None:
                link = link_el.get('href', '')
        pub_date = (item.findtext('pubDate')
                    or item.findtext(f'{{{dc_ns}}}date')
                    or item.findtext('{http://www.w3.org/2005/Atom}updated') or '')
        if title.strip():
            parsed_dt = None
            if pub_date.strip():
                try:
                    parsed_dt = parsedate_to_datetime(pub_date.strip())
                except Exception:
                    try:
                        parsed_dt = datetime.fromisoformat(pub_date.strip().replace('Z', '+00:00'))
                    except Exception:
                        pass
            result.append({
                "title": title.strip(),
                "link": link.strip(),
                "date": pub_date.strip(),
                # Store as ISO string for JSON serialisation; restore on load
                "parsed_date": parsed_dt.isoformat() if parsed_dt else None,
                "source": name,
            })
    return result


def _dns_ok(timeout=2):
    """Quick connectivity probe — returns False if network is unreachable."""
    import socket
    try:
        with socket.create_connection(("feeds.npr.org", 443), timeout=timeout):
            return True
    except Exception:
        return False


def get_news_headlines(feeds):
    """Get news headlines from RSS feeds, with per-feed cache fallback."""
    cache = _load_cache()
    cache_updated = False
    now = time.time()

    # Quick DNS check — if broken, skip all network attempts and use cache
    online = _dns_ok()
    if not online:
        print("  News: DNS unavailable, using cached headlines")

    all_items = []  # list of dicts (parsed_date is ISO string or None)

    for feed_config in feeds:
        name = feed_config.get("name", "News")
        url = feed_config.get("url", "")
        if not url:
            continue

        fetched = None
        if online:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Dashboard/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    tree = ET.parse(resp)
                fetched = _parse_items(tree.getroot(), name)
                cache[name] = {"ts": now, "items": fetched}
                cache_updated = True
            except Exception as e:
                print(f"  RSS feed error ({name}): {e}")

        # Fall back to cache if we didn't get fresh data
        if fetched is None:
            cached = cache.get(name)
            if cached and (now - cached["ts"]) < _CACHE_MAX_AGE:
                age_min = int((now - cached["ts"]) / 60)
                if online:  # only log if we actually tried and failed
                    print(f"  Using cached news for {name} ({age_min} min old)")
                fetched = cached["items"]

        if fetched:
            all_items.extend(fetched)

    if cache_updated:
        _save_cache(cache)

    # Restore parsed_date from ISO string for sorting
    epoch = datetime(1970, 1, 1)
    def sort_key(h):
        ds = h.get("parsed_date")
        if not ds:
            return epoch
        try:
            dt = datetime.fromisoformat(ds)
            return dt.replace(tzinfo=None)
        except Exception:
            return epoch

    all_items.sort(key=sort_key, reverse=True)

    # Guarantee at least 3 headlines per feed, then fill the rest by date
    MIN_PER_FEED = 3
    MAX_TOTAL = 50
    seen_sources = {}   # source -> count of items already picked
    result = []
    remaining = []
    for item in all_items:
        src = item.get("source", "")
        cnt = seen_sources.get(src, 0)
        if cnt < MIN_PER_FEED:
            result.append(item)
            seen_sources[src] = cnt + 1
        else:
            remaining.append(item)
    # Fill up to MAX_TOTAL with the newest remaining items (already sorted)
    result.extend(remaining[:MAX_TOTAL - len(result)])
    # Re-sort so the final list is newest-first
    result.sort(key=sort_key, reverse=True)

    # Convert parsed_date back to a datetime object for builders/news.py compatibility
    for h in result:
        ds = h.get("parsed_date")
        if ds:
            try:
                h["parsed_date"] = datetime.fromisoformat(ds)
            except Exception:
                h["parsed_date"] = None
        else:
            h["parsed_date"] = None

    print(f"  Found {len(result)} news headlines")
    return result
