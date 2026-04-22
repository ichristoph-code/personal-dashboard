"""Fetch market overview data from Yahoo Finance (no API key required).

Uses the v8 chart API which is more reliable than the deprecated v7 quote API.
Fetches all symbols in parallel for speed.
Caches results to disk (10 min TTL) so a transient failure doesn't blank
the market widget — stale data is shown instead.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import atomic_write_json

import requests

_SYMBOLS = {
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones",
    "^IXIC": "Nasdaq",
    "BTC-USD": "Bitcoin",
}

_CACHE_FILE = Path(__file__).parent.parent / ".market_cache.json"
_CACHE_TTL = 10 * 60  # 10 minutes


def _load_cache():
    """Return (data, is_fresh) tuple from disk cache."""
    try:
        if _CACHE_FILE.exists():
            cached = json.loads(_CACHE_FILE.read_text())
            age = time.time() - cached.get("ts", 0)
            return cached["data"], age < _CACHE_TTL
    except Exception:
        pass
    return None, False


def _save_cache(data):
    atomic_write_json(_CACHE_FILE, {"ts": time.time(), "data": data})


def _fetch_quote(symbol, name, session):
    """Fetch a single quote using the v8 chart API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        resp = session.get(
            url,
            params={"range": "1d", "interval": "1d"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice", 0)
        prev = meta.get("chartPreviousClose") or meta.get("previousClose", price)
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0
        return {
            "symbol": symbol,
            "name": name,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:
        print(f"  Market: {name} ({symbol}) failed: {e}")
        return None


def get_market_data():
    """Fetch key market indices in parallel.  Returns a list of dicts or None.

    Uses a 10-minute disk cache.  On failure, returns stale cached data
    rather than blanking the widget.
    """
    cached_data, is_fresh = _load_cache()
    if is_fresh:
        return cached_data

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    })

    results = []
    with ThreadPoolExecutor(max_workers=len(_SYMBOLS)) as pool:
        futures = {
            pool.submit(_fetch_quote, sym, name, session): sym
            for sym, name in _SYMBOLS.items()
        }
        try:
            for future in as_completed(futures, timeout=15):
                try:
                    quote = future.result(timeout=10)
                    if quote:
                        results.append(quote)
                except Exception as e:
                    sym = futures[future]
                    print(f"  Market: {sym} result failed: {e}")
        except TimeoutError:
            print("  Market: some fetches timed out — continuing with partial data")

    if results:
        # Preserve display order (S&P, Dow, Nasdaq, BTC)
        order = list(_SYMBOLS.keys())
        results.sort(key=lambda q: order.index(q["symbol"]))
        _save_cache(results)
        return results

    # All fetches failed — fall back to stale cache if available
    if cached_data:
        print("  Market data: all fetches failed, using stale cache")
        return cached_data

    print("  Market data: all fetches failed, no cache available")
    return None
