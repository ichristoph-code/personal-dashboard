# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A personal macOS dashboard that fetches data from APIs and local macOS sources (Calendar, Mail, Things 3, iMessage, Notes) and generates a static HTML file served as a PWA. Designed for iPhone home screen access.

## Running the Dashboard

```bash
# One-shot HTML generation
python3 dashboard.py

# Generate and serve with HTTP server (for PWA/browser access)
python3 dashboard.py --serve --port 8080

# Refresh a single tab only
python3 dashboard.py --tab today
```

The dashboard auto-refreshes every 30 minutes via a macOS LaunchAgent calling `scripts/refresh_dashboard.sh`. Individual tabs can be refreshed via AJAX at `/api/tab/{tab_name}`.

**Note:** Ian has pre-authorized killing and restarting the local dev server whenever code changes need to load. Just do it without asking.

## Architecture

Three-layer pipeline: **Sources → Builders → HTML**

- **`sources/`** — Fetches raw data from external APIs and macOS. Each source caches to `.{source_name}_cache.json` with a TTL. Returns `None`/`[]` on failure (never raises).
- **`builders/`** — Transforms source data into styled HTML strings. Each builder handles one UI component. Imports helpers from `builders/helpers.py`.
- **`templates/`** — CSS (`css/`) and JS (`js/`) files loaded with mtime-based cache busting.
- **`dashboard.py`** — Orchestrator (2000+ lines): fetches sources in parallel via `ThreadPoolExecutor`, assembles HTML panels, writes `dashboard.html` atomically, and runs the HTTP server.

### Key Patterns

**Parallel fetching with per-source timeouts** — `TAB_SOURCES` maps tab names to required source sets, enabling selective refresh. Overall timeout is 90s; individual sources get 10–30s depending on speed. Failures are logged but non-blocking.

**Caching** — `atomic_write_json()` writes to a temp file then renames. Cache freshness validated on every fetch; stale/missing cache triggers API call. Offline-resilient: returns cached data if network fails.

**Badge caching** — `_last_badge_cache` stores unread counts with 5-minute TTL to avoid full refetch on tab switches.

**Server** — `SimpleHTTPRequestHandler` subclass. Static files at `/dashboard.html`; AJAX tab refresh at `/api/tab/{tab}`. Background refresh queue deduplicates concurrent refresh requests.

**HTML generation** — CSS/JS inlined with mtime cache-busting. Chart data and calendar events embedded as JSON in `<script>` tags. No client-side API calls — all data baked in at generation time.

### Adding a New Tab or Source

1. Create `sources/my_source.py` with a function returning structured data (cache with TTL, return `None` on error).
2. Create `builders/my_builder.py` with a function accepting that data and returning an HTML string.
3. Register the source in `TAB_SOURCES` in `dashboard.py`.
4. Add a `_build_my_panel()` function in `dashboard.py` and wire it into `generate_html_dashboard()`.

## Configuration

`config.json` (copy from `config.example.json`). Key fields:
- `api_token` — YNAB API token (required)
- `latitude`, `longitude` — Location for weather (defaults: Bay Area)
- `anthropic_api_key` — Optional, used by `sources/claude_review.py` for financial summaries
- `things_auth_token` — Optional, for Things 3 task integration
- `news_feeds` — Array of `{name, url}` RSS feeds

## Dependencies

`pip install -r requirements.txt` — only `requests` is needed beyond stdlib. macOS-only features (Calendar, Mail, iMessage, Notes) use AppleScript via `subprocess`.
