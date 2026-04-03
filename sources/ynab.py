"""YNAB (You Need A Budget) API client with offline cache fallback."""

import json
import time
from pathlib import Path

import requests

from . import atomic_write_json

# Cache lives next to this file's parent package
_CACHE_FILE = Path(__file__).parent.parent / ".ynab_cache.json"
_CACHE_MAX_AGE = 7 * 24 * 3600  # 7 days — stale but still useful offline


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data: dict):
    atomic_write_json(_CACHE_FILE, data)


class YNABClient:
    """Client for the YNAB REST API with local cache fallback."""

    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://api.ynab.com/v1"
        self.headers = {"Authorization": f"Bearer {api_token}"}
        self._cache = _load_cache()
        self._online = True  # flipped False on first network failure

    @staticmethod
    def _dns_ok(host="api.ynab.com", timeout=3):
        """Quick check: can we resolve the YNAB hostname within `timeout` seconds?"""
        import socket
        try:
            socket.setdefaulttimeout(timeout)
            socket.getaddrinfo(host, 443)
            return True
        except Exception:
            return False
        finally:
            socket.setdefaulttimeout(None)

    def reset_online(self):
        """Re-arm network access so the next request retries the API."""
        self._online = True

    def _get(self, url, cache_key):
        """GET with cache-on-success and instant cache-fallback when offline."""
        cached = self._cache.get(cache_key)

        # If we already know we're offline this run, skip straight to cache
        if not self._online:
            if cached:
                return cached["data"]
            raise ConnectionError("YNAB offline and no cache available")

        # Quick DNS probe — skip the slow requests.get if DNS is broken
        if not self._dns_ok():
            self._online = False
            if cached:
                age_h = (time.time() - cached["ts"]) / 3600
                print(f"  YNAB offline — using cached data ({age_h:.0f}h old) for {cache_key}")
                return cached["data"]
            raise ConnectionError("YNAB DNS failed and no cache available")

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            self._cache[cache_key] = {"ts": time.time(), "data": data}
            _save_cache(self._cache)
            return data
        except Exception:
            if cached:
                age_h = (time.time() - cached["ts"]) / 3600
                print(f"  YNAB error — using cached data ({age_h:.0f}h old) for {cache_key}")
                self._online = False
                return cached["data"]
            raise

    def resolve_budget_id(self):
        """Resolve 'last-used' to a real budget ID, using cache to work offline.

        Returns the first budget's ID and persists it so future offline runs work.
        """
        cached_bid = self._cache.get("resolved_budget_id")
        if cached_bid:
            print(f"  Using cached budget_id: {cached_bid}")
            return cached_bid
        budgets = self.get_budgets()
        budget_id = budgets[0]["id"]
        self._cache["resolved_budget_id"] = budget_id
        _save_cache(self._cache)
        return budget_id

    @staticmethod
    def _extract(data, *keys):
        """Safely navigate nested dict keys; raises KeyError with context."""
        node = data
        for k in keys:
            try:
                node = node[k]
            except (KeyError, TypeError, IndexError) as e:
                raise KeyError(f"YNAB response missing key path {'.'.join(str(x) for x in keys)}: {e}")
        return node

    def get_budgets(self):
        data = self._get(f"{self.base_url}/budgets", "budgets")
        return self._extract(data, "data", "budgets")

    def get_accounts(self, budget_id):
        data = self._get(
            f"{self.base_url}/budgets/{budget_id}/accounts",
            f"accounts_{budget_id}",
        )
        return self._extract(data, "data", "accounts")

    def get_categories(self, budget_id):
        data = self._get(
            f"{self.base_url}/budgets/{budget_id}/categories",
            f"categories_{budget_id}",
        )
        return self._extract(data, "data", "category_groups")

    def get_months(self, budget_id):
        """Fetch monthly budget summaries (income, activity, age of money)."""
        data = self._get(
            f"{self.base_url}/budgets/{budget_id}/months",
            f"months_{budget_id}",
        )
        return self._extract(data, "data", "months")

    def get_transactions(self, budget_id, since_date=None):
        """Fetch transactions, optionally filtered by start date (YYYY-MM-DD)."""
        url = f"{self.base_url}/budgets/{budget_id}/transactions"
        cache_key = f"transactions_{budget_id}"
        if since_date:
            url += f"?since_date={since_date}"
            cache_key += f"_{since_date}"
        data = self._get(url, cache_key)
        return self._extract(data, "data", "transactions")

    def get_scheduled_transactions(self, budget_id):
        """Fetch scheduled/recurring transactions (upcoming bills)."""
        data = self._get(
            f"{self.base_url}/budgets/{budget_id}/scheduled_transactions",
            f"scheduled_{budget_id}",
        )
        return self._extract(data, "data", "scheduled_transactions")
