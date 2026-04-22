#!/usr/bin/env python3
"""
Personal Dashboard Generator
Creates an interactive HTML dashboard with macOS Calendar events,
Things 3 tasks, YNAB financial data, weather, email, and news.
"""

import argparse
import json
import socket
import socketserver
import http.server
import sys
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import requests

from sources import (
    get_things_tasks, get_calendar_events,
    get_weather, get_mail_messages, get_news_headlines, get_imessages,
    get_apple_notes, create_note, update_note, delete_note, clear_all_caches, clear_caches_for_sources, atomic_write_json,
    get_market_data, generate_financial_review, query_claude_financial,
    get_system_info, get_network_speed,
    get_all_contacts, get_upcoming_birthdays,
    get_sf_events, get_journal_articles,
    generate_morning_briefing, get_commute,
)
from sources.mail import get_all_mail_folders
from sources.ynab import YNABClient
from builders import (
    PIE_COLORS, PIE_BORDER_COLORS, format_currency,
    build_account_card, fin_section, build_calendar_html,
    build_things_html, build_mail_html, build_news_html,
    build_imessage_html, build_notes_html,
    build_savings_goals_html, build_upcoming_bills_html,
    build_recent_transactions_html, build_debt_tracker_html,
    build_claude_review_html, build_market_overview_html,
    build_finance_links_html, build_networth_chart_html,
    build_claude_chat_html, build_system_html,
    build_contacts_html, build_birthdays_card, build_today_html,
    build_events_html, build_journals_html,
    ICON_PIE, ICON_ACCOUNTS, ICON_BVA, ICON_TREND, ICON_CATEGORY, ICON_PAYEES,
)

BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"
_NET_WORTH_FILE = BASE_DIR / ".net_worth_history.json"

# Shared state: last-computed financial summary for Claude chat queries
_last_financial_summary = {}

# ── Tab-to-source mapping for selective refresh ──
TAB_SOURCES = {
    "today":      {"calendar", "weather", "things", "mail", "imessages", "birthdays"},
    "calendar":   {"calendar", "weather", "birthdays"},
    "tasks":      {"things"},
    "email":      {"mail"},
    "news":       {"news"},
    "imessage":   {"imessages"},
    "financials": {"months", "transactions", "scheduled", "market", "ynab_accounts", "ynab_categories"},
    "notes":      {"notes"},
    "contacts":   {"contacts"},
    "system":     {"system", "network_speed"},
    "events":     {"events"},
    "journals":   {"journals"},
}


def _save_net_worth(value):
    """Append today's net worth to the history file for trend tracking."""
    try:
        history = json.loads(_NET_WORTH_FILE.read_text()) if _NET_WORTH_FILE.exists() else []
    except Exception:
        history = []
    today = datetime.now().strftime("%Y-%m-%d")
    if history and history[-1]["date"] == today:
        history[-1]["value"] = round(value)
    else:
        history.append({"date": today, "value": round(value)})
    history = history[-365:]  # keep one year
    atomic_write_json(_NET_WORTH_FILE, history)
    return history


def _css_link_tags():
    """Return <link> tags for each CSS module in order, with mtime cache-busting."""
    css_dir = TEMPLATE_DIR / "css"
    if css_dir.is_dir():
        files = sorted(css_dir.glob("*.css"))
        if files:
            return "\n".join(
                f'    <link rel="stylesheet" href="/templates/css/{f.name}?v={int(f.stat().st_mtime)}">'
                for f in files
            )
    return '    <link rel="stylesheet" href="/templates/styles.css">'


def _js_script_tags():
    """Return <script> tags for each JS module in order, with mtime cache-busting."""
    js_dir = TEMPLATE_DIR / "js"
    if js_dir.is_dir():
        files = sorted(js_dir.glob("*.js"))
        if files:
            return "\n".join(
                f'    <script src="/templates/js/{f.name}?v={int(f.stat().st_mtime)}"></script>'
                for f in files
            )
    return '    <script src="/templates/scripts.js"></script>'


# ── Per-source data fetching (used by both full generation and AJAX API) ──

def _fetch_sources(source_names, ynab, budget_id, config):
    """Fetch only the specified data sources in parallel.

    Returns a dict keyed by source name with the fetched data.
    Sources not in *source_names* are skipped entirely.
    """
    results = {}
    config = config or {}
    # Re-arm YNAB network access so accounts/data refresh after transient failures
    if ynab is not None:
        ynab.reset_online()
    lat = config.get("latitude", 37.89)
    lon = config.get("longitude", -122.54)
    mail_folders_cfg = config.get("mail_folders", None)
    news_feeds = config.get("news_feeds", [
        {"name": "NPR", "url": "https://feeds.npr.org/1001/rss.xml"},
        {"name": "BBC", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
    ])
    since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    def _fetch(name, fn, *a, **kw):
        print(f"  [API] Fetching {name}...")
        return fn(*a, **kw)

    # Map source names to their fetch calls
    source_fetchers = {
        "calendar":     ("calendar events", get_calendar_events),
        "things":       ("Things tasks", get_things_tasks),
        "weather":      ("weather", lambda: get_weather(lat, lon, force_refresh=True)),
        "mail":         ("mail", lambda: get_mail_messages(30, folders=mail_folders_cfg)),
        "mail_folders": ("mail folders", get_all_mail_folders),
        "news":         ("news", lambda: get_news_headlines(news_feeds)),
        "imessages":    ("iMessages", get_imessages),
        "notes":        ("Apple Notes", get_apple_notes),
        "months":       ("YNAB months", lambda: ynab.get_months(budget_id)),
        "transactions": ("YNAB transactions",
                         lambda: ynab.get_transactions(budget_id, since_date)),
        "scheduled":    ("YNAB scheduled",
                         lambda: ynab.get_scheduled_transactions(budget_id)),
        "market":       ("market data", get_market_data),
        "system":       ("system info", get_system_info),
        "network_speed": ("network speed", get_network_speed),
        "ynab_accounts":    ("YNAB accounts", lambda: ynab.get_accounts(budget_id)),
        "ynab_categories":  ("YNAB categories", lambda: ynab.get_categories(budget_id)),
        "contacts":     ("contacts", get_all_contacts),
        "birthdays":    ("birthdays", lambda: get_upcoming_birthdays(30)),
        "events":       ("SF events", lambda: get_sf_events(config.get("event_feeds", None))),
        "journals":     ("journals", lambda: get_journal_articles()),
    }

    # Per-source timeouts — slow sources get more time
    _slow_sources = {"network_speed", "notes", "market", "system"}
    _default_timeout = 10      # seconds (was 5 — too tight for many sources)
    _slow_timeout = 30         # seconds for known-slow sources
    _overall_timeout = 90      # seconds total (was 60)

    pool = ThreadPoolExecutor(max_workers=min(12, max(1, len(source_names))))
    futures = {}
    for name in source_names:
        if name in source_fetchers:
            label, fn = source_fetchers[name]
            futures[pool.submit(_fetch, label, fn)] = name

    try:
        for future in as_completed(futures, timeout=_overall_timeout):
            key = futures[future]
            per_source_timeout = _slow_timeout if key in _slow_sources else _default_timeout
            try:
                results[key] = future.result(timeout=per_source_timeout)
            except Exception as e:
                print(f"  Warning: {key} fetch failed: {e}")
                results[key] = [] if key == "mail_folders" else None
    except (TimeoutError, FuturesTimeoutError):
        for future, key in futures.items():
            if key not in results:
                future.cancel()
                print(f"  Warning: {key} fetch timed out")
                results[key] = [] if key == "mail_folders" else None
    pool.shutdown(wait=False, cancel_futures=True)
    return results


# ── Per-tab HTML builders (used by the /api/tab/ endpoint) ──

def _build_calendar_panel(results, config):
    """Build calendar panel HTML + data for inline globals."""
    calendar_events = results.get("calendar")
    weather = results.get("weather")
    birthdays = results.get("birthdays") or []
    cal_html = build_calendar_html(calendar_events, weather, include_scripts=False)
    bday_html = build_birthdays_card(birthdays)
    html = cal_html + "\n" + bday_html

    # Data that would normally be in inline <script> tags
    events_json_data = []
    forecast_by_date = {}
    if calendar_events:
        for evt in calendar_events:
            events_json_data.append({
                "title": evt["title"], "calendar": evt.get("calendar", ""),
                "start": evt["start"], "end": evt["end"],
                "all_day": evt["all_day"],
                "location": evt.get("location", ""),
                "event_id": evt.get("event_id", ""),
            })
    if weather and weather.get("forecast"):
        for day in weather["forecast"]:
            forecast_by_date[day["date"]] = {
                "icon": day["icon"], "high": day["high"],
                "low": day["low"], "desc": day["desc"],
            }

    cal_names_seen = []
    cal_names_set = set()
    for evt in (calendar_events or []):
        cn = evt.get("calendar", "")
        if cn and cn not in cal_names_set:
            cal_names_set.add(cn)
            cal_names_seen.append(cn)

    calendar_data = {
        "eventsJson": events_json_data,
        "weatherForecast": forecast_by_date,
        "calendarList": sorted(cal_names_seen, key=lambda s: s.lower()),
    }
    return html, calendar_data


def _build_tasks_panel(results, config):
    """Build tasks panel HTML."""
    things_data = results.get("things") or {}
    things_auth_token = config.get("things_auth_token", "")
    things_html = build_things_html(things_data, things_auth_token)
    return (
        f'<div class="draggable-card" data-card-id="things-tasks">'
        f'<span class="card-drag-handle" title="Drag to reorder">&#x2807;</span>'
        f'{things_html}'
        f'</div>'
    )


def _build_email_panel(results):
    """Build email panel HTML."""
    mail_messages = results.get("mail")
    all_mail_folders = results.get("mail_folders") or []
    return build_mail_html(mail_messages, all_mail_folders, include_scripts=False), all_mail_folders


def _build_news_panel(results):
    """Build news panel HTML."""
    return build_news_html(results.get("news"))


def _build_events_panel(results):
    """Build SF events panel HTML."""
    return build_events_html(results.get("events"))


def _build_journals_panel(results):
    """Build journals panel HTML."""
    return build_journals_html(results.get("journals"))


def _build_imessage_panel(results):
    """Build iMessage panel HTML."""
    return build_imessage_html(results.get("imessages"))


def _build_financials_panel(results, ynab, budget_id, config):
    """Build financials panel HTML and chart data.

    Returns (html_string, chart_data_dict).
    """
    accounts = results.get("ynab_accounts") or []
    categories = results.get("ynab_categories") or []
    months_data = results.get("months") or []
    transactions = results.get("transactions") or []
    scheduled_txns = results.get("scheduled") or []
    market_data = results.get("market")

    # Account bucketing
    total_budget = total_on_budget = total_off_budget = 0.0
    _type_buckets = {"checking": [], "savings": [], "creditCard": [], "_other": []}
    for acc in accounts:
        if acc["closed"]:
            continue
        bal = format_currency(acc["balance"])
        total_budget += bal
        if acc["on_budget"]:
            total_on_budget += bal
        else:
            total_off_budget += bal
        key = acc["type"] if acc["type"] in _type_buckets else "_other"
        _type_buckets[key].append(acc)

    def _sort_key(a): return a["name"].lower()
    checking_savings = sorted(
        _type_buckets["checking"] + _type_buckets["savings"], key=_sort_key)
    credit_cards = sorted(_type_buckets["creditCard"], key=_sort_key)
    other_accounts = sorted(_type_buckets["_other"], key=_sort_key)

    # Net worth history
    nw_history = _save_net_worth(total_budget)

    # Ready to Assign + Age of Money
    ready_to_assign = 0.0
    age_of_money = 0
    current_month_str = datetime.now().strftime("%Y-%m-01")
    relevant_months = [m for m in months_data if m.get("month", "") <= current_month_str]
    if relevant_months:
        latest = relevant_months[-1]
        ready_to_assign = format_currency(latest.get("to_be_budgeted", 0))
        age_of_money = latest.get("age_of_money", 0) or 0

    # Chart data
    pie_accounts = [(acc["name"], round(format_currency(acc["balance"])))
                    for acc in accounts if not acc["closed"] and acc["balance"] > 0]
    pie_accounts.sort(key=lambda x: x[1], reverse=True)
    n = len(pie_accounts)

    category_data = []
    for group in categories:
        if group["name"] != "Internal Master Category":
            for cat in group["categories"]:
                if not cat["hidden"] and cat["activity"] != 0:
                    category_data.append({
                        "name": cat["name"],
                        "activity": round(abs(format_currency(cat["activity"]))),
                    })
    category_data.sort(key=lambda c: c['activity'], reverse=True)

    bva_data = []
    for group in categories:
        if group["name"] == "Internal Master Category":
            continue
        for cat in group["categories"]:
            if not cat["hidden"] and cat.get("budgeted", 0) > 0:
                bva_data.append({
                    "name": cat["name"],
                    "budgeted": round(format_currency(cat["budgeted"])),
                    "spent": round(abs(format_currency(cat.get("activity", 0)))),
                })
    bva_data.sort(key=lambda c: c["budgeted"], reverse=True)
    bva_data = bva_data[:15]

    trend_labels, trend_income, trend_spending = [], [], []
    for m in relevant_months[-12:]:
        try:
            dt = datetime.strptime(m["month"], "%Y-%m-%d")
            trend_labels.append(dt.strftime("%b '%y"))
            trend_income.append(round(format_currency(m.get("income", 0))))
            trend_spending.append(round(abs(format_currency(m.get("activity", 0)))))
        except (ValueError, KeyError):
            continue

    payee_totals = {}
    for txn in transactions:
        payee = txn.get("payee_name") or "Unknown"
        amt = format_currency(txn.get("amount", 0))
        if amt < 0 and payee != "Starting Balance":
            payee_totals[payee] = payee_totals.get(payee, 0) + abs(amt)
    top_payees = sorted(payee_totals.items(), key=lambda x: x[1], reverse=True)[:10]

    # Chart data dict for JS
    chart_data = {
        "pieNames": [a[0] for a in pie_accounts],
        "pieBalances": [a[1] for a in pie_accounts],
        "pieBg": PIE_COLORS[:n],
        "pieBorder": PIE_BORDER_COLORS[:n],
        "catNames": [c['name'] for c in category_data[:15]],
        "catActivity": [c['activity'] for c in category_data[:15]],
        "bvaNames": [c["name"] for c in bva_data],
        "bvaBudgeted": [c["budgeted"] for c in bva_data],
        "bvaSpent": [c["spent"] for c in bva_data],
        "trendLabels": trend_labels,
        "trendIncome": trend_income,
        "trendSpending": trend_spending,
        "payeeNames": [p[0] for p in top_payees],
        "payeeAmounts": [round(p[1]) for p in top_payees],
        "nwHistory": nw_history,
    }

    # Build HTML sections
    net_worth_class = 'positive' if total_budget >= 0 else 'negative'
    rta_class = 'positive' if ready_to_assign >= 0 else 'negative'

    checking_card = build_account_card("Checking & Savings", checking_savings, "No accounts")
    credit_card = build_account_card("Credit Cards", credit_cards, "No credit cards")
    other_card = build_account_card("Other Accounts", other_accounts, "No other accounts")

    asset_alloc_content = (
        '<div class="pie-wrapper"><div class="pie-canvas-wrap">'
        '<canvas id="accountChart"></canvas></div></div>'
    )
    asset_alloc_section = fin_section("sec-alloc", "Asset Allocation",
                                      asset_alloc_content, ICON_PIE)
    acct_detail_content = (
        f'<div class="accounts-grid">{checking_card}{credit_card}{other_card}</div>'
    )
    acct_detail_section = fin_section("sec-accounts", "Account Details",
                                      acct_detail_content, ICON_ACCOUNTS)
    bva_content = '<div class="bva-chart-wrap"><canvas id="bvaChart"></canvas></div>'
    bva_section = fin_section("sec-bva", "Budget vs. Actual", bva_content, ICON_BVA)
    trend_content = '<div class="trend-chart-wrap"><canvas id="trendChart"></canvas></div>'
    trend_section = fin_section("sec-trend", "Monthly Income vs. Spending",
                                trend_content, ICON_TREND)
    cat_spending_content = '<canvas id="categoryChart"></canvas>'
    cat_spending_section = fin_section("sec-categories", "Spending by Category",
                                       cat_spending_content, ICON_CATEGORY)
    payees_content = '<div class="payees-chart-wrap"><canvas id="payeesChart"></canvas></div>'
    payees_section = fin_section("sec-payees", "Top Payees (30 Days)",
                                 payees_content, ICON_PAYEES, default_open=False)

    savings_goals_html = build_savings_goals_html(categories)
    upcoming_bills_html = build_upcoming_bills_html(scheduled_txns)
    recent_txns_html = build_recent_transactions_html(transactions)
    debt_tracker_html = build_debt_tracker_html(accounts)
    market_overview_html = build_market_overview_html(market_data)
    finance_links_html = build_finance_links_html()
    networth_chart_html = build_networth_chart_html()

    # Claude review (optional)
    anthropic_key = config.get("anthropic_api_key", "")
    over_budget = [c for c in bva_data if c["spent"] > c["budgeted"]]
    financial_summary = {
        "net_worth": round(total_budget),
        "on_budget": round(total_on_budget),
        "off_budget": round(total_off_budget),
        "ready_to_assign": round(ready_to_assign),
        "age_of_money_days": age_of_money,
        "top_spending_categories": category_data[:10],
        "over_budget_categories": over_budget,
        "monthly_income": trend_income[-1] if trend_income else 0,
        "monthly_spending": trend_spending[-1] if trend_spending else 0,
    }
    global _last_financial_summary
    _last_financial_summary = financial_summary

    review_html_text = None
    if anthropic_key:
        review_html_text = generate_financial_review(anthropic_key, financial_summary)
    claude_review_html = build_claude_review_html(review_html_text)
    claude_chat_html = build_claude_chat_html(has_api_key=bool(anthropic_key))

    html = f"""<div class="summary-cards privacy-blur" id="summaryCards">
                <button class="privacy-toggle" onclick="togglePrivacy()" title="Show/hide balances" aria-label="Toggle balance visibility">
                    <svg class="eye-open" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    <svg class="eye-closed" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                </button>
                <div class="card">
                    <h3>Net Worth</h3>
                    <div class="amount {net_worth_class}">${total_budget:,.0f}</div>
                </div>
                <div class="card">
                    <h3>Budget Accounts</h3>
                    <div class="amount neutral">${total_on_budget:,.0f}</div>
                </div>
                <div class="card">
                    <h3>Tracking Accounts</h3>
                    <div class="amount neutral">${total_off_budget:,.0f}</div>
                </div>
                <div class="card">
                    <h3>Ready to Assign</h3>
                    <div class="amount {rta_class}">${ready_to_assign:,.0f}</div>
                </div>
                <div class="card">
                    <h3>Age of Money</h3>
                    <div class="amount neutral">{age_of_money}<span class="amount-sub">days</span></div>
                </div>
            </div>

            {networth_chart_html}
            {asset_alloc_section}
            {acct_detail_section}
            {bva_section}
            {savings_goals_html}
            {trend_section}
            {cat_spending_section}
            {upcoming_bills_html}
            {recent_txns_html}
            {payees_section}
            {debt_tracker_html}
            {claude_review_html}
            {claude_chat_html}
            {market_overview_html}
            {finance_links_html}"""

    return html, chart_data


def _build_notes_panel(results):
    """Build notes panel HTML + index data."""
    import re as _re
    notes_data = results.get("notes")
    html = build_notes_html(notes_data, include_scripts=False)

    # Replicate the note_index construction from build_notes_html
    # (must match the nid scheme: "{sanitized_folder}-{index}")
    notes_index = []
    if notes_data:
        for folder_data in notes_data:
            fname_raw = folder_data.get("folder", "")
            fname_id = _re.sub(r"[^a-zA-Z0-9-]", "-", fname_raw)
            for i, note in enumerate(folder_data.get("notes", [])):
                nid = f"{fname_id}-{i}"
                notes_index.append({
                    "id": nid,
                    "folder": fname_raw,
                    "title": note.get("title", "Untitled"),
                    "modified": note.get("modified", ""),
                    "rel": "",  # JS will display from modified field
                    "body": note.get("body", ""),
                })

    return f'<div class="card notes-card">{html}</div>', notes_index


def _build_system_panel(results):
    """Build system panel HTML."""
    system_data = results.get("system")
    network_speed = results.get("network_speed")
    if system_data and network_speed:
        system_data["network_speed"] = network_speed
    return build_system_html(system_data)


def _build_contacts_panel(results):
    """Build contacts panel HTML + index data."""
    contacts_data = results.get("contacts") or []
    html = build_contacts_html(contacts_data, include_scripts=False)

    # Build contact index for JS (scalar data only; multi-value loaded lazily)
    contacts_index = []
    for c in contacts_data:
        contacts_index.append({
            "id": c["id"],
            "contact_id": c.get("contact_id", ""),
            "name": c["name"],
            "first": c.get("first", ""),
            "last": c.get("last", ""),
            "org": c.get("org", ""),
            "jobtitle": c.get("jobtitle", ""),
            "department": c.get("department", ""),
            "nickname": c.get("nickname", ""),
            "birthday": c.get("birthday", ""),
            "birthday_year": c.get("birthday_year"),
            "thumb": c.get("thumb", ""),
            "note": c.get("note", ""),
        })

    return html, contacts_index


def _build_today_panel(results, config):
    """Build the Today briefing panel HTML."""
    # Use cached financial summary if available (from last full generation)
    fin = _last_financial_summary
    net_worth = fin.get("net_worth", 0) if fin else 0
    ready_to_assign = fin.get("ready_to_assign", 0) if fin else 0

    # Include the AI briefing so it survives AJAX tab refreshes
    anthropic_key = (config or {}).get("anthropic_api_key", "")
    briefing_text = generate_morning_briefing(anthropic_key, {
        "weather": results.get("weather"),
        "today_events": [
            e["title"] for e in (results.get("calendar") or [])
            if e.get("start", "").startswith(datetime.now().strftime('%Y-%m-%d'))
            and not e.get("all_day")
        ][:6],
        "today_tasks": [t.get("title", "") for t in (results.get("things") or {}).get("today", [])][:5],
        "net_worth": round(net_worth),
        "ready_to_assign": round(ready_to_assign),
    })

    data = {
        "weather": results.get("weather"),
        "calendar_events": results.get("calendar"),
        "things_data": results.get("things") or {},
        "mail_messages": results.get("mail"),
        "imessages": results.get("imessages"),
        "upcoming_birthdays": results.get("birthdays") or [],
        "net_worth": net_worth,
        "ready_to_assign": ready_to_assign,
        "briefing": briefing_text,
    }

    return build_today_html(data)


def _build_header_badges(results):
    """Compute header info and badge counts for all tabs.

    Returns a JSON-serializable dict.
    """
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        greeting = "Good morning, Ian"
    elif hour < 17:
        greeting = "Good afternoon, Ian"
    else:
        greeting = "Good evening, Ian"

    weather = results.get("weather")
    weather_widget = ""
    if weather:
        weather_widget = (
            f'<a href="weather://" class="weather-widget" title="Open Weather app">'
            f'<span class="weather-icon">{weather["current_icon"]}</span>'
            f'<span class="weather-temp">{weather["current_temp"]}\u00b0F</span>'
            f'<span class="weather-desc">{escape(weather["current_desc"])}</span>'
            f'</a>'
        )

    # Next event pill
    calendar_events = results.get("calendar") or []
    next_event_html = ""
    now_str = now.strftime('%Y-%m-%d %H:%M')
    for evt in calendar_events:
        if evt.get("all_day"):
            continue
        if evt["start"] > now_str:
            try:
                evt_dt = datetime.strptime(evt["start"], '%Y-%m-%d %H:%M')
                evt_time = evt_dt.strftime('%-I:%M %p')
                evt_title = escape(evt["title"])
                eid_js = json.dumps(evt.get("event_id", ""))
                today_date = now.strftime('%Y-%m-%d')
                next_event_html = (
                    f'<a href="#" class="next-event-pill" data-date="{today_date}" '
                    f'onclick="goToEvent({eid_js});return false;" title="Jump to event">'
                    f'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
                    f'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
                    f'stroke-linejoin="round"><circle cx="12" cy="12" r="10"/>'
                    f'<polyline points="12 6 12 12 16 14"/></svg>'
                    f' Next up: <strong>{evt_title}</strong> at {evt_time}</a>'
                )
            except ValueError:
                pass
            break

    # Badge counts
    things_data = results.get("things") or {}
    today_task_count = len(things_data.get("today", []))

    mail_messages = results.get("mail")
    unread_count = 0
    if mail_messages:
        for _msgs in mail_messages.values():
            unread_count += sum(1 for m in _msgs if not m.get("read"))

    imessages = results.get("imessages") or []
    imsg_unread = sum(c["unread_count"] for c in imessages) if imessages else 0

    # Upcoming birthdays (7 days) for contacts badge
    birthdays = results.get("birthdays") or []
    bday_soon = sum(1 for b in birthdays if b["days_until"] <= 7)

    return {
        "greeting": greeting,
        "date": now.strftime('%A, %B %d'),
        "time": now.strftime('%-I:%M %p'),
        "weather_widget": weather_widget,
        "next_event": next_event_html,
        "badges": {
            "tasks": today_task_count,
            "email": unread_count,
            "imessage": imsg_unread,
            "contacts": bday_soon,
        },
    }


# Sources needed for header badges — only fetched when the tab's own
# sources already overlap significantly (e.g. "today") or not at all.
# For other tabs we use the last-known badge counts to avoid 2-7x slowdowns.
_BADGE_SOURCES = {"calendar", "weather", "things", "mail", "imessages", "birthdays"}

# Cached badge counts so per-tab refreshes don't need to re-fetch everything
_last_badge_cache = {"badges": {}, "header": {}}


def generate_html_dashboard(ynab, budget_id, config=None, default_tab=None):
    """Fetch all data sources and assemble the HTML dashboard."""
    gen_start = _time.monotonic()
    config = config or {}
    things_auth_token = config.get("things_auth_token", "")
    quick_links = config.get("quick_links", [])

    # ── YNAB data ──
    print("Fetching YNAB data...")
    budgets = ynab.get_budgets()
    if not budgets:
        raise ValueError("No YNAB budgets found")
    budget = next((b for b in budgets if b["id"] == budget_id), budgets[0])

    # Fetch accounts and categories in parallel (saves ~1-2s)
    _ynab_pool = ThreadPoolExecutor(max_workers=2)
    _acc_future = _ynab_pool.submit(ynab.get_accounts, budget["id"])
    _cat_future = _ynab_pool.submit(ynab.get_categories, budget["id"])
    accounts = _acc_future.result()
    categories = _cat_future.result()
    _ynab_pool.shutdown(wait=False)

    print(f"  Loaded budget: {budget['name']}")
    print(f"  Found {len(accounts)} accounts")

    # ── Single-pass account bucketing ──
    total_budget = total_on_budget = total_off_budget = 0.0
    _type_buckets = {"checking": [], "savings": [], "creditCard": [], "_other": []}
    for acc in accounts:
        if acc["closed"]:
            continue
        bal = format_currency(acc["balance"])
        total_budget += bal
        if acc["on_budget"]:
            total_on_budget += bal
        else:
            total_off_budget += bal
        key = acc["type"] if acc["type"] in _type_buckets else "_other"
        _type_buckets[key].append(acc)

    def _sort_key(a): return a["name"].lower()
    checking_savings = sorted(_type_buckets["checking"] + _type_buckets["savings"], key=_sort_key)
    credit_cards = sorted(_type_buckets["creditCard"], key=_sort_key)
    other_accounts = sorted(_type_buckets["_other"], key=_sort_key)

    # ── Parallel data fetching ──
    mail_folders_cfg = config.get("mail_folders", None)
    news_feeds = config.get("news_feeds", [
        {"name": "NPR", "url": "https://feeds.npr.org/1001/rss.xml"},
        {"name": "BBC", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
    ])
    lat = config.get("latitude", 37.89)
    lon = config.get("longitude", -122.54)
    unsplash_key = config.get("unsplash_access_key", "")
    event_feeds = config.get("event_feeds", None)
    work_address = config.get("work_address", "")

    # Each source is fetched in its own thread; failures are caught individually
    results = {}
    def _fetch(name, fn, *args, **kwargs):
        print(f"Fetching {name}...")
        return fn(*args, **kwargs)

    # Date range for recent transactions (last 30 days)
    since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    pool = ThreadPoolExecutor(max_workers=12)
    futures = {
        pool.submit(_fetch, "calendar events", get_calendar_events): "calendar",
        pool.submit(_fetch, "Things tasks", get_things_tasks): "things",
        pool.submit(_fetch, "weather", get_weather, lat, lon, force_refresh=True): "weather",  # weather actually checks this flag
        pool.submit(_fetch, "mail", get_mail_messages, 30, folders=mail_folders_cfg): "mail",
        pool.submit(_fetch, "mail folders", get_all_mail_folders): "mail_folders",
        pool.submit(_fetch, "news", get_news_headlines, news_feeds): "news",
        pool.submit(_fetch, "iMessages", get_imessages): "imessages",
        pool.submit(_fetch, "Apple Notes", get_apple_notes): "notes",
        # New financial data sources
        pool.submit(_fetch, "YNAB months", ynab.get_months, budget["id"]): "months",
        pool.submit(_fetch, "YNAB transactions", ynab.get_transactions, budget["id"], since_date): "transactions",
        pool.submit(_fetch, "YNAB scheduled", ynab.get_scheduled_transactions, budget["id"]): "scheduled",
        pool.submit(_fetch, "market data", get_market_data): "market",
        pool.submit(_fetch, "system info", get_system_info): "system",
        pool.submit(_fetch, "network speed", get_network_speed): "network_speed",
        pool.submit(_fetch, "contacts", get_all_contacts): "contacts",
        pool.submit(_fetch, "birthdays", lambda: get_upcoming_birthdays(30)): "birthdays",
        pool.submit(_fetch, "SF events", lambda: get_sf_events(event_feeds)): "events",
        pool.submit(_fetch, "journals", lambda: get_journal_articles()): "journals",
        pool.submit(_fetch, "commute", lambda: get_commute(lat, lon, work_address)): "commute",
    }
    # Process completed futures with a 60-second overall timeout.
    # Don't wait for stragglers (e.g. Apple Notes AppleScript can hang).
    try:
        for future in as_completed(futures, timeout=60):
            key = futures[future]
            try:
                results[key] = future.result(timeout=5)
            except Exception as e:
                print(f"  Warning: {key} fetch failed: {e}")
                results[key] = None if key != "mail_folders" else []
    except (TimeoutError, FuturesTimeoutError):
        for future, key in futures.items():
            if key not in results:
                future.cancel()
                print(f"  Warning: {key} fetch timed out — continuing without it")
                results[key] = None if key != "mail_folders" else []
    # Release the pool without waiting for stuck threads (they're daemon-like)
    pool.shutdown(wait=False, cancel_futures=True)

    calendar_events = results.get("calendar")
    things_data = results.get("things") or {}
    weather = results.get("weather")
    mail_messages = results.get("mail")
    all_mail_folders = results.get("mail_folders") or []
    news_headlines = results.get("news")
    imessages = results.get("imessages")
    notes_data = results.get("notes")
    notes_html = build_notes_html(notes_data)

    # New financial data
    months_data = results.get("months") or []
    transactions = results.get("transactions") or []
    scheduled_txns = results.get("scheduled") or []
    market_data = results.get("market")
    system_data = results.get("system")
    network_speed = results.get("network_speed")
    if system_data and network_speed:
        system_data["network_speed"] = network_speed
    system_html = build_system_html(system_data)

    # ── Contacts & Birthdays ──
    contacts_data = results.get("contacts") or []
    upcoming_birthdays = results.get("birthdays") or []
    contacts_html = build_contacts_html(contacts_data)
    birthdays_card_html = build_birthdays_card(upcoming_birthdays)

    # ── Net worth history (save today's snapshot) ──
    nw_history = _save_net_worth(total_budget)

    # ── Ready to Assign + Age of Money from most recent month ──
    ready_to_assign = 0.0
    age_of_money = 0
    current_month_str = datetime.now().strftime("%Y-%m-01")
    relevant_months = [m for m in months_data if m.get("month", "") <= current_month_str]
    if relevant_months:
        latest = relevant_months[-1]  # months are chronological ascending
        ready_to_assign = format_currency(latest.get("to_be_budgeted", 0))
        age_of_money = latest.get("age_of_money", 0) or 0

    # ── Prepare chart data ──
    pie_accounts = [(acc["name"], round(format_currency(acc["balance"])))
                    for acc in accounts if not acc["closed"] and acc["balance"] > 0]
    pie_accounts.sort(key=lambda x: x[1], reverse=True)
    pie_names = json.dumps([a[0] for a in pie_accounts])
    pie_balances = json.dumps([a[1] for a in pie_accounts])
    n = len(pie_accounts)
    pie_bg = json.dumps(PIE_COLORS[:n])
    pie_border = json.dumps(PIE_BORDER_COLORS[:n])

    category_data = []
    for group in categories:
        if group["name"] != "Internal Master Category":
            for cat in group["categories"]:
                if not cat["hidden"] and cat["activity"] != 0:
                    category_data.append({
                        "name": cat["name"],
                        "activity": round(abs(format_currency(cat["activity"]))),
                    })
    category_data.sort(key=lambda c: c['activity'], reverse=True)
    cat_names = json.dumps([c['name'] for c in category_data[:15]])
    cat_activity = json.dumps([c['activity'] for c in category_data[:15]])

    # ── Budget vs Actual chart data ──
    bva_data = []
    for group in categories:
        if group["name"] == "Internal Master Category":
            continue
        for cat in group["categories"]:
            if not cat["hidden"] and cat.get("budgeted", 0) > 0:
                bva_data.append({
                    "name": cat["name"],
                    "budgeted": round(format_currency(cat["budgeted"])),
                    "spent": round(abs(format_currency(cat.get("activity", 0)))),
                })
    bva_data.sort(key=lambda c: c["budgeted"], reverse=True)
    bva_data = bva_data[:15]
    bva_names = json.dumps([c["name"] for c in bva_data])
    bva_budgeted = json.dumps([c["budgeted"] for c in bva_data])
    bva_spent = json.dumps([c["spent"] for c in bva_data])

    # ── Monthly income vs spending trend (last 12 months) ──
    trend_labels, trend_income, trend_spending = [], [], []
    for m in relevant_months[-12:]:
        try:
            dt = datetime.strptime(m["month"], "%Y-%m-%d")
            trend_labels.append(dt.strftime("%b '%y"))
            trend_income.append(round(format_currency(m.get("income", 0))))
            trend_spending.append(round(abs(format_currency(m.get("activity", 0)))))
        except (ValueError, KeyError):
            continue
    trend_labels_json = json.dumps(trend_labels)
    trend_income_json = json.dumps(trend_income)
    trend_spending_json = json.dumps(trend_spending)

    # ── Top payees by spending (from last 30 days of transactions) ──
    payee_totals = {}
    for txn in transactions:
        payee = txn.get("payee_name") or "Unknown"
        amt = format_currency(txn.get("amount", 0))
        if amt < 0 and payee != "Starting Balance":
            payee_totals[payee] = payee_totals.get(payee, 0) + abs(amt)
    top_payees = sorted(payee_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    payee_names_json = json.dumps([p[0] for p in top_payees])
    payee_amounts_json = json.dumps([round(p[1]) for p in top_payees])

    # ── Net worth history for trend chart ──
    nw_history_json = json.dumps(nw_history)

    # ── Financial summary (used by Claude review + chat) ──
    anthropic_key = config.get("anthropic_api_key", "")
    over_budget = [c for c in bva_data if c["spent"] > c["budgeted"]]
    financial_summary = {
        "net_worth": round(total_budget),
        "on_budget": round(total_on_budget),
        "off_budget": round(total_off_budget),
        "ready_to_assign": round(ready_to_assign),
        "age_of_money_days": age_of_money,
        "top_spending_categories": category_data[:10],
        "over_budget_categories": over_budget,
        "monthly_income": trend_income[-1] if trend_income else 0,
        "monthly_spending": trend_spending[-1] if trend_spending else 0,
    }

    global _last_financial_summary
    _last_financial_summary = financial_summary

    # ── Claude AI financial review (optional, cached 4h) ──
    review_html_text = None
    if anthropic_key:
        print("Generating Claude financial review...")
        review_html_text = generate_financial_review(anthropic_key, financial_summary)

    # ── Build HTML sections ──
    checking_card = build_account_card("Checking & Savings", checking_savings, "No accounts")
    credit_card = build_account_card("Credit Cards", credit_cards, "No credit cards")
    other_card = build_account_card("Other Accounts", other_accounts, "No other accounts")
    calendar_html = build_calendar_html(calendar_events, weather)
    things_html = build_things_html(things_data, things_auth_token)
    mail_html = build_mail_html(mail_messages, all_mail_folders)
    news_html = build_news_html(news_headlines)
    imessage_html = build_imessage_html(imessages)

    # New financial builders
    savings_goals_html = build_savings_goals_html(categories)
    upcoming_bills_html = build_upcoming_bills_html(scheduled_txns)
    recent_txns_html = build_recent_transactions_html(transactions)
    debt_tracker_html = build_debt_tracker_html(accounts)
    claude_review_html = build_claude_review_html(review_html_text)
    market_overview_html = build_market_overview_html(market_data)
    finance_links_html = build_finance_links_html()
    networth_chart_html = build_networth_chart_html()
    claude_chat_html = build_claude_chat_html(has_api_key=bool(anthropic_key))

    # ── SF Events & Journals ──
    events_html   = build_events_html(results.get("events"))
    journals_html = build_journals_html(results.get("journals"))

    # ── AI Morning Briefing ──
    # Proactively clear stale briefing cache so we never bake yesterday's
    # text into a freshly-generated dashboard.html (fixes date mismatch).
    _briefing_cache = Path(__file__).parent / ".briefing_cache.json"
    try:
        if _briefing_cache.exists():
            _bc = json.loads(_briefing_cache.read_text())
            if _bc.get("date") != datetime.now().strftime("%Y-%m-%d"):
                _briefing_cache.unlink()
                print("  Briefing: cleared stale cache from", _bc.get("date"))
    except Exception:
        pass
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_events_titles = [
        e["title"] for e in (calendar_events or [])
        if e.get("start", "").startswith(today_str) and not e.get("all_day")
    ][:6]
    today_task_titles = [t.get("title", "") for t in things_data.get("today", [])][:5]
    unread_mail_count = sum(
        sum(1 for m in msgs if not m.get("read"))
        for msgs in (mail_messages or {}).values()
    )
    briefing_text = generate_morning_briefing(anthropic_key, {
        "weather": weather,
        "today_events": today_events_titles,
        "today_tasks": today_task_titles,
        "net_worth": round(total_budget),
        "ready_to_assign": round(ready_to_assign),
        "unread_mail": unread_mail_count or None,
        "unread_imessages": (sum(c["unread_count"] for c in imessages) if imessages else 0) or None,
    })

    # ── Today Briefing Panel ──
    today_panel_data = {
        "weather": weather,
        "calendar_events": calendar_events,
        "things_data": things_data,
        "mail_messages": mail_messages,
        "imessages": imessages,
        "upcoming_birthdays": upcoming_birthdays,
        "net_worth": round(total_budget),
        "ready_to_assign": round(ready_to_assign),
        "briefing": briefing_text,
        "commute": results.get("commute"),
    }
    today_html = build_today_html(today_panel_data)

    # Wrap existing chart sections in collapsible containers
    asset_alloc_content = (
        '<div class="pie-wrapper"><div class="pie-canvas-wrap">'
        '<canvas id="accountChart"></canvas></div></div>'
    )
    asset_alloc_section = fin_section("sec-alloc", "Asset Allocation", asset_alloc_content, ICON_PIE)

    acct_detail_content = (
        f'<div class="accounts-grid">{checking_card}{credit_card}{other_card}</div>'
    )
    acct_detail_section = fin_section("sec-accounts", "Account Details", acct_detail_content, ICON_ACCOUNTS)

    bva_content = '<div class="bva-chart-wrap"><canvas id="bvaChart"></canvas></div>'
    bva_section = fin_section("sec-bva", "Budget vs. Actual", bva_content, ICON_BVA)

    trend_content = '<div class="trend-chart-wrap"><canvas id="trendChart"></canvas></div>'
    trend_section = fin_section("sec-trend", "Monthly Income vs. Spending", trend_content, ICON_TREND)

    cat_spending_content = '<canvas id="categoryChart"></canvas>'
    cat_spending_section = fin_section("sec-categories", "Spending by Category", cat_spending_content, ICON_CATEGORY)

    payees_content = '<div class="payees-chart-wrap"><canvas id="payeesChart"></canvas></div>'
    payees_section = fin_section("sec-payees", "Top Payees (30 Days)", payees_content, ICON_PAYEES, default_open=False)

    net_worth_class = 'positive' if total_budget >= 0 else 'negative'
    rta_class = 'positive' if ready_to_assign >= 0 else 'negative'

    # ── Header data ──
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        greeting = "Good morning, Ian"
    elif hour < 17:
        greeting = "Good afternoon, Ian"
    else:
        greeting = "Good evening, Ian"

    formatted_date = now.strftime('%A, %B %d')
    timestamp = now.strftime('%-I:%M %p')

    # Weather header widget (clickable — opens Apple Weather)
    weather_html = ''
    if weather:
        weather_html = (
            f'<a href="weather://" class="weather-widget" title="Open Weather app">'
            f'<span class="weather-icon">{weather["current_icon"]}</span>'
            f'<span class="weather-temp">{weather["current_temp"]}\u00b0F</span>'
            f'<span class="weather-desc">{escape(weather["current_desc"])}</span>'
            f'</a>'
        )

    # Next upcoming event pill (clickable — scrolls to event in day view)
    next_event_html = ''
    if calendar_events:
        now_str = now.strftime('%Y-%m-%d %H:%M')
        for evt in calendar_events:
            if evt["all_day"]:
                continue
            if evt["start"] > now_str:
                try:
                    evt_dt = datetime.strptime(evt["start"], '%Y-%m-%d %H:%M')
                    evt_time = evt_dt.strftime('%-I:%M %p')
                    evt_title = escape(evt["title"])
                    eid_js = json.dumps(evt.get("event_id", ""))
                    today_date = now.strftime('%Y-%m-%d')
                    next_event_html = (
                        f'<a href="#" class="next-event-pill" data-date="{today_date}" onclick="goToEvent({eid_js});return false;" title="Jump to event">'
                        f'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
                        f' Next up: <strong>{evt_title}</strong> at {evt_time}</a>'
                    )
                except ValueError:
                    pass
                break

    # Badge counts
    today_task_count = len(things_data.get("today", []))
    task_badge = f'<span class="tab-badge">{today_task_count}</span>' if today_task_count > 0 else ''

    unread_count = 0
    if mail_messages:
        for _msgs in mail_messages.values():
            unread_count += sum(1 for m in _msgs if not m.get("read"))
    mail_badge = f'<span class="tab-badge">{unread_count}</span>' if unread_count > 0 else ''

    imsg_unread = sum(c["unread_count"] for c in imessages) if imessages else 0
    imsg_badge = f'<span class="tab-badge">{imsg_unread}</span>' if imsg_unread > 0 else ''

    bday_soon = sum(1 for b in upcoming_birthdays if b["days_until"] <= 7)
    contacts_badge = f'<span class="tab-badge">{bday_soon}</span>' if bday_soon > 0 else ''

    # Quick links seed data
    quick_links_json = json.dumps(quick_links)

    # Generation timestamp (epoch ms for JS)
    generated_at = int(now.timestamp() * 1000)

    # Build unique calendar name list for JS color picker
    cal_names_seen = []
    cal_names_set = set()
    for evt in (calendar_events or []):
        cn = evt.get("calendar", "")
        if cn and cn not in cal_names_set:
            cal_names_set.add(cn)
            cal_names_seen.append(cn)
    calendar_list_json = json.dumps(sorted(cal_names_seen, key=lambda s: s.lower()))

    # ── Generation timing ──
    gen_elapsed = round(_time.monotonic() - gen_start, 1)

    # Default tab override (from --tab CLI flag)
    default_tab_js = json.dumps(default_tab) if default_tab else 'null'

    # Auto-refresh interval (minutes, from config; 0 = disabled)
    auto_refresh_mins = config.get("auto_refresh_minutes", 0)

    # ── Build inline data block (replaces template placeholders) ──
    inline_data = f"""<script>
var __PIE_NAMES__      = {pie_names};
var __PIE_BALANCES__   = {pie_balances};
var __PIE_BG__         = {pie_bg};
var __PIE_BORDER__     = {pie_border};
var __CAT_NAMES__      = {cat_names};
var __CAT_ACTIVITY__   = {cat_activity};
var __BVA_NAMES__      = {bva_names};
var __BVA_BUDGETED__   = {bva_budgeted};
var __BVA_SPENT__      = {bva_spent};
var __TREND_LABELS__   = {trend_labels_json};
var __TREND_INCOME__   = {trend_income_json};
var __TREND_SPENDING__ = {trend_spending_json};
var __PAYEE_NAMES__    = {payee_names_json};
var __PAYEE_AMOUNTS__  = {payee_amounts_json};
var __NW_HISTORY__     = {nw_history_json};
var GENERATED_AT       = {generated_at};
var GEN_ELAPSED        = {gen_elapsed};
var THINGS_AUTH_TOKEN  = {json.dumps(things_auth_token)};
var CALENDAR_LIST      = {calendar_list_json};
var NEWS_FEEDS         = {json.dumps(news_feeds)};
var DEFAULT_TAB        = {default_tab_js};
var AUTO_REFRESH_MINS  = {auto_refresh_mins};
var UNSPLASH_ACCESS_KEY = {json.dumps(unsplash_key)};
var DASHBOARD_LAT       = {lat};
var DASHBOARD_LON       = {lon};
</script>"""

    css_tags = _css_link_tags()
    js_tags  = _js_script_tags()

    # ── Assemble the full HTML ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%23667eea'/><stop offset='100%25' stop-color='%23764ba2'/></linearGradient></defs><rect width='100' height='100' rx='22' fill='url(%23g)'/><path d='M30 28h20a20 20 0 0 1 0 40H30z' fill='none' stroke='white' stroke-width='6' stroke-linecap='round' stroke-linejoin='round'/><circle cx='68' cy='32' r='5' fill='%2348bb78'/></svg>">
    <title>Dashboard &mdash; {budget['name']}</title>
    <!-- PWA -->
    <link rel="manifest" href="/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Dashboard">
    <meta name="theme-color" content="#1a1a2e">
    <link rel="apple-touch-icon" href="/icon-192.png">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
{css_tags}
</head>
<body>
    <!-- Header -->
    <div class="top-bar">
        <div class="top-bar-inner">
            <div>
                <div class="greeting">{greeting}</div>
                <div class="header-meta">
                    <span class="header-date">{formatted_date}</span>
                    <span class="header-time" id="headerTime">Updated {timestamp}</span>
                    {weather_html}
                </div>
                {next_event_html}
            </div>
            <div class="header-actions">
                <!-- Analog Clock -->
                <div class="ive-clock-container">
                    <div class="ive-clock">
                        <div class="ive-clock-face">
                            <div class="ive-tick ive-tick-1"></div>
                            <div class="ive-tick ive-tick-2"></div>
                            <div class="ive-tick ive-tick-3"></div>
                            <div class="ive-tick ive-tick-4"></div>
                            <div class="ive-tick ive-tick-5"></div>
                            <div class="ive-tick ive-tick-6"></div>
                            <div class="ive-tick ive-tick-7"></div>
                            <div class="ive-tick ive-tick-8"></div>
                            <div class="ive-tick ive-tick-9"></div>
                            <div class="ive-tick ive-tick-10"></div>
                            <div class="ive-tick ive-tick-11"></div>
                            <div class="ive-tick ive-tick-12"></div>
                            <div class="ive-minute-tick ive-mt-1"></div>
                            <div class="ive-minute-tick ive-mt-2"></div>
                            <div class="ive-minute-tick ive-mt-3"></div>
                            <div class="ive-minute-tick ive-mt-4"></div>
                            <div class="ive-minute-tick ive-mt-5"></div>
                            <div class="ive-minute-tick ive-mt-6"></div>
                            <div class="ive-minute-tick ive-mt-7"></div>
                            <div class="ive-minute-tick ive-mt-8"></div>
                            <div class="ive-minute-tick ive-mt-9"></div>
                            <div class="ive-minute-tick ive-mt-10"></div>
                            <div class="ive-minute-tick ive-mt-11"></div>
                            <div class="ive-minute-tick ive-mt-12"></div>
                            <div class="ive-minute-tick ive-mt-13"></div>
                            <div class="ive-minute-tick ive-mt-14"></div>
                            <div class="ive-minute-tick ive-mt-15"></div>
                            <div class="ive-minute-tick ive-mt-16"></div>
                            <div class="ive-minute-tick ive-mt-17"></div>
                            <div class="ive-minute-tick ive-mt-18"></div>
                            <div class="ive-minute-tick ive-mt-19"></div>
                            <div class="ive-minute-tick ive-mt-20"></div>
                            <div class="ive-minute-tick ive-mt-21"></div>
                            <div class="ive-minute-tick ive-mt-22"></div>
                            <div class="ive-minute-tick ive-mt-23"></div>
                            <div class="ive-minute-tick ive-mt-24"></div>
                            <div class="ive-minute-tick ive-mt-25"></div>
                            <div class="ive-minute-tick ive-mt-26"></div>
                            <div class="ive-minute-tick ive-mt-27"></div>
                            <div class="ive-minute-tick ive-mt-28"></div>
                            <div class="ive-minute-tick ive-mt-29"></div>
                            <div class="ive-minute-tick ive-mt-30"></div>
                            <div class="ive-minute-tick ive-mt-31"></div>
                            <div class="ive-minute-tick ive-mt-32"></div>
                            <div class="ive-minute-tick ive-mt-33"></div>
                            <div class="ive-minute-tick ive-mt-34"></div>
                            <div class="ive-minute-tick ive-mt-35"></div>
                            <div class="ive-minute-tick ive-mt-36"></div>
                            <div class="ive-minute-tick ive-mt-37"></div>
                            <div class="ive-minute-tick ive-mt-38"></div>
                            <div class="ive-minute-tick ive-mt-39"></div>
                            <div class="ive-minute-tick ive-mt-40"></div>
                            <div class="ive-minute-tick ive-mt-41"></div>
                            <div class="ive-minute-tick ive-mt-42"></div>
                            <div class="ive-minute-tick ive-mt-43"></div>
                            <div class="ive-minute-tick ive-mt-44"></div>
                            <div class="ive-minute-tick ive-mt-45"></div>
                            <div class="ive-minute-tick ive-mt-46"></div>
                            <div class="ive-minute-tick ive-mt-47"></div>
                            <div class="ive-minute-tick ive-mt-48"></div>
                            <div class="ive-hand ive-hand-hour" id="iveHourHand"></div>
                            <div class="ive-hand ive-hand-minute" id="iveMinuteHand"></div>
                            <div class="ive-hand ive-hand-second" id="iveSecondHand"></div>
                            <div class="ive-center-dot"></div>
                        </div>
                    </div>
                    <div class="ive-clock-date" id="iveClockDate"></div>
                </div>
                <!-- Pomodoro Timer -->
                <div class="pomodoro-widget" id="pomoWidget" title="Start Pomodoro (25 min focus)">
                    <div class="pomo-ring-wrap">
                        <svg viewBox="0 0 28 28">
                            <circle class="pomo-ring-bg" cx="14" cy="14" r="12"/>
                            <circle class="pomo-ring-progress" cx="14" cy="14" r="12"
                                    stroke-dasharray="75.4" stroke-dashoffset="75.4"/>
                        </svg>
                        <span class="pomo-play-icon">
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        </span>
                    </div>
                    <div>
                        <span class="pomo-time">25:00</span>
                        <span class="pomo-phase"></span>
                    </div>
                    <div class="pomo-dots">
                        <span class="pomo-dot"></span>
                        <span class="pomo-dot"></span>
                        <span class="pomo-dot"></span>
                        <span class="pomo-dot"></span>
                    </div>
                    <div class="pomo-controls">
                        <button class="pomo-btn pomo-reset-btn" title="Reset">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
                        </button>
                        <button class="pomo-btn pomo-skip-btn" title="Skip phase">
                            <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" stroke-width="2"/></svg>
                        </button>
                    </div>
                </div>
                <!-- Websites Launcher -->
                <div class="app-launcher-wrap" id="webLauncherWrap">
                    <button class="refresh-btn app-launcher-trigger" title="Websites" onclick="toggleWebLauncher(event)">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="2" y1="12" x2="22" y2="12"/>
                            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                        </svg>
                    </button>
                    <div class="app-launcher-dropdown" id="webLauncherDropdown">
                        <div class="app-launcher-header">
                            <span class="app-launcher-title">Websites</span>
                            <button class="app-launcher-edit-btn" onclick="toggleWebEdit()" title="Edit websites">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </button>
                        </div>
                        <div id="webLauncherList"></div>
                        <div id="webLauncherEditor" style="display:none"></div>
                    </div>
                </div>
                <!-- App Launcher -->
                <div class="app-launcher-wrap" id="appLauncherWrap">
                    <button class="refresh-btn app-launcher-trigger" title="Launch apps" onclick="toggleAppLauncher(event)">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
                            <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
                        </svg>
                    </button>
                    <div class="app-launcher-dropdown" id="appLauncherDropdown">
                        <div class="app-launcher-header">
                            <span class="app-launcher-title">Apps</span>
                            <button class="app-launcher-edit-btn" onclick="toggleAppEdit()" title="Edit apps">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </button>
                        </div>
                        <div id="appLauncherList"></div>
                        <div id="appLauncherEditor" style="display:none"></div>
                    </div>
                </div>
                <button class="refresh-btn" onclick="openSearch()" title="Search (⌘K)">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                </button>
                <button class="refresh-btn" onclick="toggleBgPhoto()" title="Toggle background photos">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
                    </svg>
                </button>
                <button class="theme-toggle-btn" onclick="toggleTheme()" title="Toggle dark mode">
                    <svg class="icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                    </svg>
                    <svg class="icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                    </svg>
                </button>
                <button class="refresh-btn" onclick="refreshDashboard(this)" title="Refresh dashboard">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
                        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                    </svg>
                </button>
            </div>
        </div>
    </div>
    <script>var SEED_LINKS = {quick_links_json};</script>

    <!-- Tab bar -->
    <div class="tab-bar-wrap">
        <div class="tab-bar">
            <button class="tab-btn active" draggable="true" onclick="switchTab('today')" data-tab="today">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                Today
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('calendar')" data-tab="calendar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
                </svg>
                Calendar
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('tasks')" data-tab="tasks">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                Tasks{task_badge}
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('email')" data-tab="email">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>
                </svg>
                Email{mail_badge}
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('news')" data-tab="news">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                </svg>
                News
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('imessage')" data-tab="imessage">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                iMessage{imsg_badge}
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('financials')" data-tab="financials">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                </svg>
                Financials
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('notes')" data-tab="notes">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
                </svg>
                Notes
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('contacts')" data-tab="contacts">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                </svg>
                Contacts{contacts_badge}
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('system')" data-tab="system">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
                </svg>
                System
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('events')" data-tab="events">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
                </svg>
                SF Events
            </button>
            <button class="tab-btn" draggable="true" onclick="switchTab('journals')" data-tab="journals">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                </svg>
                Journals
            </button>
        </div>
    </div>

    <div class="container">
        <!-- Today Tab -->
        <div class="tab-panel active" id="panel-today">
            {today_html}
        </div>

        <!-- Calendar Tab -->
        <div class="tab-panel" id="panel-calendar">
            {calendar_html}
            {birthdays_card_html}
        </div>

        <!-- Tasks Tab -->
        <div class="tab-panel" id="panel-tasks">
            <div class="draggable-card" data-card-id="things-tasks">
                <span class="card-drag-handle" title="Drag to reorder">&#x2807;</span>
                {things_html}
            </div>
        </div>

        <!-- Email Tab -->
        <div class="tab-panel" id="panel-email">
            {mail_html}
        </div>

        <!-- News Tab -->
        <div class="tab-panel" id="panel-news">
            {news_html}
        </div>

        <!-- iMessage Tab -->
        <div class="tab-panel" id="panel-imessage">
            {imessage_html}
        </div>

        <!-- Financials Tab -->
        <div class="tab-panel" id="panel-financials">
            <div class="summary-cards privacy-blur" id="summaryCards">
                <button class="privacy-toggle" onclick="togglePrivacy()" title="Show/hide balances" aria-label="Toggle balance visibility">
                    <svg class="eye-open" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    <svg class="eye-closed" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                </button>
                <div class="card">
                    <h3>Net Worth</h3>
                    <div class="amount {net_worth_class}">${total_budget:,.0f}</div>
                </div>
                <div class="card">
                    <h3>Budget Accounts</h3>
                    <div class="amount neutral">${total_on_budget:,.0f}</div>
                </div>
                <div class="card">
                    <h3>Tracking Accounts</h3>
                    <div class="amount neutral">${total_off_budget:,.0f}</div>
                </div>
                <div class="card">
                    <h3>Ready to Assign</h3>
                    <div class="amount {rta_class}">${ready_to_assign:,.0f}</div>
                </div>
                <div class="card">
                    <h3>Age of Money</h3>
                    <div class="amount neutral">{age_of_money}<span class="amount-sub">days</span></div>
                </div>
            </div>

            {networth_chart_html}
            {asset_alloc_section}
            {acct_detail_section}
            {bva_section}
            {savings_goals_html}
            {trend_section}
            {cat_spending_section}
            {upcoming_bills_html}
            {recent_txns_html}
            {payees_section}
            {debt_tracker_html}
            {claude_review_html}
            {claude_chat_html}
            {market_overview_html}
            {finance_links_html}
        </div>

        <!-- Notes Tab -->
        <div class="tab-panel" id="panel-notes">
            <div class="card notes-card">
                {notes_html}
            </div>
        </div>

        <!-- Contacts Tab -->
        <div class="tab-panel" id="panel-contacts">
            {contacts_html}
        </div>

        <!-- System Tab -->
        <div class="tab-panel" id="panel-system">
            {system_html}
        </div>

        <!-- SF Events Tab -->
        <div class="tab-panel" id="panel-events">
            {events_html}
        </div>

        <!-- Journals Tab -->
        <div class="tab-panel" id="panel-journals">
            {journals_html}
        </div>
    </div>

    <footer>
        <span class="footer-gen">Generated in {gen_elapsed}s</span>
        <span class="footer-sep">&middot;</span>
        <span class="footer-time">Updated {timestamp}</span>
        <span class="footer-sep">&middot;</span>
        <span class="footer-shortcut">Press <kbd>?</kbd> for shortcuts</span>
    </footer>

    {inline_data}
{js_tags}
</body>
</html>"""

    return html


def _start_server(port, ynab=None, budget_id=None, config=None):
    """Serve the project directory over HTTP."""
    _base_dir = str(BASE_DIR)

    # Shared state for the refresh endpoint — Event is cleared when idle
    _refresh_busy = threading.Event()
    _refresh_pending = threading.Event()   # signals a queued refresh is waiting
    _refresh_pending_tab = None            # tab requested by the queued refresh

    def _do_refresh(ynab, budget_id, config, tab=None):
        """Regenerate the dashboard HTML and stamp file in a background thread.

        When *tab* is given and valid, only that tab's caches are cleared
        and the stamp is updated — the AJAX /api/tab/ endpoint handles the
        actual data fetch.  Full HTML regeneration only runs for tab-less
        requests (e.g. manual full refresh).
        """
        try:
            if tab and tab in TAB_SOURCES:
                clear_caches_for_sources(TAB_SOURCES[tab])
                print(f"\n  [Refresh] Cleared caches for '{tab}' tab "
                      f"({len(TAB_SOURCES[tab])} sources)")
            else:
                clear_all_caches()
                print("\n  [Refresh] Full refresh (all sources)...")
                html_content = generate_html_dashboard(ynab, budget_id, config)
                output_file = BASE_DIR / "dashboard.html"
                import tempfile
                import os
                fd, tmp = tempfile.mkstemp(dir=BASE_DIR, suffix=".html.tmp")
                try:
                    with os.fdopen(fd, 'w') as f:
                        f.write(html_content)
                    os.replace(tmp, output_file)
                except BaseException:
                    os.unlink(tmp)
                    raise

            stamp_file = BASE_DIR / "dashboard.stamp"
            with open(stamp_file, 'w') as f:
                f.write(str(int(datetime.now().timestamp() * 1000)))
            print("  [Refresh] Done.")
        except Exception as e:
            import traceback
            print(f"  [Refresh] Error: {e}")
            traceback.print_exc()
        finally:
            # Check if another refresh was queued while we were busy
            nonlocal _refresh_pending_tab
            if _refresh_pending.is_set():
                queued_tab = _refresh_pending_tab
                _refresh_pending.clear()
                _refresh_pending_tab = None
                print(f"  [Refresh] Running queued refresh"
                      f"{f' for tab {queued_tab!r}' if queued_tab else ''}...")
                # Stay busy and run the queued refresh
                _do_refresh(ynab, budget_id, config, tab=queued_tab)
            else:
                _refresh_busy.clear()

    # Capture ynab/budget_id/config for use in the refresh handler
    _server_context = {'ynab': ynab, 'budget_id': budget_id, 'config': config or {}}

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            # Pass directory= explicitly so os.getcwd() is never called
            super().__init__(*args, directory=_base_dir, **kwargs)

        def log_message(self, format, *args):
            pass

        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            path = parsed.path

            if path == '/':
                self.send_response(302)
                self.send_header('Location', '/dashboard.html')
                self.end_headers()

            elif path == '/dashboard.html':
                # Stale-date defense: if dashboard.html is from a prior
                # local date, the baked-in AI briefing is yesterday's
                # ("Good morning, Ian—it's a foggy Thursday..." on
                # Saturday). Kick off a background regen if not already
                # running, AND strip the stale briefing from the served
                # HTML so the user never sees yesterday's summary on the
                # today page. The client-side auto-refresh-on-stale
                # will fill in a fresh briefing via /api/tab/today.
                try:
                    p = BASE_DIR / "dashboard.html"
                    stale = False
                    if p.exists():
                        file_date = datetime.fromtimestamp(p.stat().st_mtime).date()
                        stale = file_date < datetime.now().date()
                    if stale:
                        if not _refresh_busy.is_set():
                            print(f"\n  [Serve] Stale dashboard.html ({file_date}), "
                                  "kicking off background regen")
                            _refresh_busy.set()
                            ctx = _server_context
                            threading.Thread(
                                target=_do_refresh,
                                args=(ctx['ynab'], ctx['budget_id'], ctx['config']),
                                daemon=True,
                            ).start()
                        # Serve the file with the stale briefing stripped
                        html_bytes = p.read_bytes()
                        import re as _re
                        html_bytes = _re.sub(
                            rb'<div class="today-briefing">.*?</div>\s*</div>',
                            b'',
                            html_bytes,
                            count=1,
                            flags=_re.DOTALL,
                        )
                        # Also strip the simpler one-level-deep form used
                        # by build_today_html (a single div with a nested
                        # span+p, closed by a single </div>).
                        html_bytes = _re.sub(
                            rb'<div class="today-briefing">'
                            rb'<span class="today-briefing-icon">[^<]*</span>'
                            rb'<p class="today-briefing-text">[^<]*</p>'
                            rb'</div>',
                            b'',
                            html_bytes,
                            count=1,
                        )
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.send_header('Content-Length', str(len(html_bytes)))
                        self.send_header('Cache-Control', 'no-store, must-revalidate')
                        self.end_headers()
                        self.wfile.write(html_bytes)
                        return
                except Exception as e:
                    print(f"  [Serve] Stale-check error: {e}")
                # Fresh file — fall through to default static handler
                super().do_GET()

            elif path == '/refresh':
                params = parse_qs(parsed.query)
                tab = params.get('tab', [None])[0]
                if not _refresh_busy.is_set():
                    _refresh_busy.set()
                    ctx = _server_context
                    t = threading.Thread(
                        target=_do_refresh,
                        args=(ctx['ynab'], ctx['budget_id'], ctx['config']),
                        kwargs={'tab': tab},
                        daemon=True,
                    )
                    t.start()
                    status_msg = b'ok'
                else:
                    # Queue this refresh instead of silently dropping it
                    _refresh_pending.set()
                    _refresh_pending_tab = tab
                    print("  [Refresh] Queued (busy) — will run after current refresh")
                    status_msg = b'queued'
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(status_msg)

            elif path == '/api/contact':
                params = parse_qs(parsed.query)
                contact_id = params.get('id', [''])[0]
                from sources.contacts import get_contact_detail
                detail = get_contact_detail(contact_id)
                self._json_response(200, detail)

            elif path.startswith('/api/tab/'):
                tab_name = path[len('/api/tab/'):]
                if tab_name not in TAB_SOURCES:
                    self._json_response(404, {"error": f"Unknown tab: {tab_name}"})
                    return
                gen_start = _time.monotonic()
                try:
                    ctx = _server_context
                    ynab_client = ctx['ynab']
                    bid = ctx['budget_id']
                    cfg = ctx['config']

                    # Only fetch sources this tab actually needs
                    needed = set(TAB_SOURCES[tab_name])
                    # For email, also need mail_folders
                    if tab_name == "email":
                        needed.add("mail_folders")

                    # Only fetch badge sources when the tab already
                    # overlaps significantly (today, calendar) — otherwise
                    # reuse cached badges to avoid fetching 6 extra sources.
                    tab_has_badge_data = needed & _BADGE_SOURCES
                    if len(tab_has_badge_data) >= 3:
                        # Tab already fetches most badge sources — add the rest
                        needed |= _BADGE_SOURCES
                        refresh_badges = True
                    else:
                        refresh_badges = False

                    # Clear caches for the requested tab's own sources
                    clear_caches_for_sources(TAB_SOURCES[tab_name])

                    print(f"\n  [API] /api/tab/{tab_name} — fetching {len(needed)} sources")
                    results = _fetch_sources(needed, ynab_client, bid, cfg)

                    # Build header/badges — use fresh data if we fetched
                    # badge sources, otherwise return cached badges
                    if refresh_badges:
                        header = _build_header_badges(results)
                        _last_badge_cache["badges"] = header["badges"]
                        _last_badge_cache["header"] = header
                    else:
                        header = _build_header_badges(results)
                        # Keep greeting/time fresh, but reuse cached badge counts,
                        # weather widget, and next-event pill (results lack those sources)
                        cached_h = _last_badge_cache.get("header", {})
                        if _last_badge_cache["badges"]:
                            header["badges"] = _last_badge_cache["badges"]
                        if not header.get("weather_widget") and cached_h.get("weather_widget"):
                            header["weather_widget"] = cached_h["weather_widget"]
                        if not header.get("next_event") and cached_h.get("next_event"):
                            header["next_event"] = cached_h["next_event"]

                    gen_elapsed = round(_time.monotonic() - gen_start, 1)
                    response = {
                        "header": header,
                        "badges": header["badges"],
                        "generated_at": int(datetime.now().timestamp() * 1000),
                        "gen_elapsed": gen_elapsed,
                    }

                    # Build the tab-specific HTML
                    if tab_name == "calendar":
                        html, cal_data = _build_calendar_panel(results, cfg)
                        response["html"] = html
                        response["calendarData"] = cal_data
                    elif tab_name == "tasks":
                        response["html"] = _build_tasks_panel(results, cfg)
                    elif tab_name == "email":
                        html, folders = _build_email_panel(results)
                        response["html"] = html
                        folder_names = [f for _, f in folders] if folders else []
                        response["mailFolders"] = folder_names
                    elif tab_name == "news":
                        response["html"] = _build_news_panel(results)
                    elif tab_name == "imessage":
                        response["html"] = _build_imessage_panel(results)
                    elif tab_name == "financials":
                        html, chart_data = _build_financials_panel(
                            results, ynab_client, bid, cfg)
                        response["html"] = html
                        response["chartData"] = chart_data
                    elif tab_name == "notes":
                        html, notes_index = _build_notes_panel(results)
                        response["html"] = html
                        response["notesIndex"] = notes_index
                    elif tab_name == "contacts":
                        html, contacts_index = _build_contacts_panel(results)
                        response["html"] = html
                        response["contactsIndex"] = contacts_index
                    elif tab_name == "today":
                        response["html"] = _build_today_panel(results, cfg)
                    elif tab_name == "system":
                        response["html"] = _build_system_panel(results)
                    elif tab_name == "events":
                        response["html"] = _build_events_panel(results)
                    elif tab_name == "journals":
                        response["html"] = _build_journals_panel(results)

                    print(f"  [API] /api/tab/{tab_name} done in {gen_elapsed}s")
                    self._json_response(200, response)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self._json_response(500, {"error": str(e)})

            else:
                super().do_GET()

        def do_POST(self):
            path = self.path.split('?')[0]
            if path == '/manage-feeds':
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    body = json.loads(self.rfile.read(length)) if length else {}
                    feeds = body.get('feeds', [])
                    if not isinstance(feeds, list):
                        self._json_response(400, {"error": "feeds must be a list"})
                        return
                    # Validate each feed has name and url
                    clean = []
                    for f in feeds:
                        name = str(f.get('name', '')).strip()
                        url = str(f.get('url', '')).strip()
                        if name and url:
                            clean.append({"name": name, "url": url})
                    # Update in-memory config
                    _server_context['config']['news_feeds'] = clean
                    # Persist to config.json
                    config_path = Path(_base_dir) / "config.json"
                    with open(config_path, 'w') as f:
                        json.dump(_server_context['config'], f, indent=2)
                    # Note: no regeneration here — the JS calls
                    # refreshDashboard() after a successful save, which
                    # hits /refresh and triggers the regen there.
                    self._json_response(200, {"ok": True})
                except Exception as e:
                    self._json_response(500, {"error": str(e)})
            elif path == '/notes-create':
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    body = json.loads(self.rfile.read(length)) if length else {}
                    title = str(body.get('title', '')).strip()
                    text = str(body.get('body', '')).strip()
                    folder = str(body.get('folder', 'Notes')).strip() or 'Notes'
                    if not title:
                        self._json_response(400, {"error": "Title is required"})
                        return
                    result = create_note(title, text, folder)
                    code = 200 if result.get("ok") else 500
                    self._json_response(code, result)
                except Exception as e:
                    self._json_response(500, {"error": str(e)})
            elif path == '/notes-update':
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    body = json.loads(self.rfile.read(length)) if length else {}
                    title = str(body.get('title', '')).strip()
                    folder = str(body.get('folder', '')).strip()
                    new_title = str(body.get('new_title', '')).strip()
                    new_body = str(body.get('new_body', '')).strip()
                    if not title or not folder:
                        self._json_response(400, {"error": "title and folder required"})
                        return
                    if not new_title:
                        self._json_response(400, {"error": "new_title is required"})
                        return
                    result = update_note(title, folder, new_title, new_body)
                    code = 200 if result.get("ok") else 500
                    self._json_response(code, result)
                except Exception as e:
                    self._json_response(500, {"error": str(e)})
            elif path == '/notes-delete':
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    body = json.loads(self.rfile.read(length)) if length else {}
                    title = str(body.get('title', '')).strip()
                    folder = str(body.get('folder', '')).strip()
                    if not title or not folder:
                        self._json_response(400, {"error": "title and folder required"})
                        return
                    result = delete_note(title, folder)
                    code = 200 if result.get("ok") else 500
                    self._json_response(code, result)
                except Exception as e:
                    self._json_response(500, {"error": str(e)})
            elif path == '/claude-query':
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    body = json.loads(self.rfile.read(length)) if length else {}
                    question = body.get('question', '').strip()
                    if not question:
                        self._json_response(400, {"error": "No question provided"})
                        return
                    api_key = _server_context['config'].get('anthropic_api_key', '')
                    if not api_key:
                        self._json_response(400, {"error": "No API key configured"})
                        return
                    result = query_claude_financial(
                        api_key, question, _last_financial_summary
                    )
                    if result:
                        self._json_response(200, {"html": result})
                    else:
                        self._json_response(500, {"error": "Failed to get response"})
                except Exception as e:
                    self._json_response(500, {"error": str(e)})
            else:
                self.send_error(404)

        def _json_response(self, code, data):
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

    try:
        # Connect to an external address (no data sent) to find the real LAN IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "unknown"

    # Auto-refresh is handled client-side via the JS setInterval
    # using AUTO_REFRESH_MINS (calls /api/tab/ — fast per-tab AJAX).
    # The old server-side _auto_refresh_loop was redundant: it did a
    # full generate_html_dashboard + disk write that collided with the
    # client-side timer and got silently dropped by _refresh_busy.
    auto_mins = (config or {}).get("auto_refresh_minutes", 0)

    # ── Daily regen watchdog ──
    # The briefing and other date-sensitive content is baked into
    # dashboard.html at generation time. If the server runs across a
    # local-date boundary without a regen, the baked briefing goes
    # stale (e.g. "Good morning, Ian—it's a foggy Thursday..." showing
    # on Saturday). Client-side AJAX refreshes only replace the in-DOM
    # today panel; they never rewrite dashboard.html on disk, so the
    # NEXT fresh page load keeps showing yesterday's briefing until the
    # AJAX refresh catches up (or fails silently).
    #
    # This watchdog runs in a daemon thread and triggers a full regen
    # whenever dashboard.html's mtime date != today's local date. It
    # checks once per minute so stale content can never persist longer
    # than that after a date rollover.
    def _dashboard_file_date():
        try:
            p = BASE_DIR / "dashboard.html"
            if not p.exists():
                return None
            return datetime.fromtimestamp(p.stat().st_mtime).date()
        except Exception:
            return None

    def _daily_regen_watchdog():
        while True:
            try:
                today = datetime.now().date()
                file_date = _dashboard_file_date()
                if file_date is not None and file_date < today:
                    if not _refresh_busy.is_set():
                        print(f"\n  [Watchdog] dashboard.html is from {file_date}, "
                              f"today is {today} — triggering full regen")
                        _refresh_busy.set()
                        t = threading.Thread(
                            target=_do_refresh,
                            args=(_server_context['ynab'],
                                  _server_context['budget_id'],
                                  _server_context['config']),
                            daemon=True,
                        )
                        t.start()
            except Exception as e:
                print(f"  [Watchdog] Error: {e}")
            _time.sleep(60)

    threading.Thread(target=_daily_regen_watchdog, daemon=True).start()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        print("\n  Dashboard server running:")
        print(f"    Local:    http://localhost:{port}/dashboard.html")
        print(f"    Network:  http://{local_ip}:{port}/dashboard.html")
        if auto_mins:
            print(f"    Auto-refresh: every {auto_mins} minutes (client-side)")
        print("\n  On iPhone (same WiFi): open the Network URL in Safari,")
        print("  then tap Share → Add to Home Screen")
        print("\n  Press Ctrl+C to stop.\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")


def main():
    parser = argparse.ArgumentParser(description="Personal Dashboard Generator")
    parser.add_argument("--serve", action="store_true",
                        help="Start HTTP server after generating (for iPhone PWA access)")
    parser.add_argument("--port", type=int, default=8080,
                        help="Port for --serve mode (default: 8080)")
    parser.add_argument("--tab", type=str, default=None,
                        choices=["today", "calendar", "tasks", "email", "news", "imessage", "financials", "notes", "contacts", "system"],
                        help="Open dashboard to a specific tab on first load")
    args = parser.parse_args()

    config_file = BASE_DIR / "config.json"

    if not config_file.exists():
        print("Config file not found!")
        print(f"Please create {config_file} with your API token and settings")
        print("\nExample config file content:")
        print('{\n  "api_token": "YOUR_YNAB_API_TOKEN_HERE",')
        print('  "budget_id": "last-used"\n}')
        sys.exit(1)

    with open(config_file, 'r') as f:
        config = json.load(f)

    if not config.get("api_token") or config["api_token"] == "YOUR_YNAB_API_TOKEN_HERE":
        print("Please add your YNAB API token to config.json")
        sys.exit(1)

    print("Generating Personal Dashboard...")
    ynab = YNABClient(config["api_token"])

    try:
        budget_id = config.get("budget_id", "last-used")
        if budget_id == "last-used":
            budget_id = ynab.resolve_budget_id()

        html_content = generate_html_dashboard(ynab, budget_id, config, default_tab=args.tab)

        # Atomic write: temp file + rename prevents serving half-written HTML
        output_file = BASE_DIR / "dashboard.html"
        import tempfile
        import os as _os
        fd, tmp = tempfile.mkstemp(dir=BASE_DIR, suffix=".html.tmp")
        try:
            with _os.fdopen(fd, 'w') as f:
                f.write(html_content)
            _os.replace(tmp, output_file)
        except BaseException:
            _os.unlink(tmp)
            raise

        # Write a tiny stamp file that the browser polls to detect completion.
        # This works reliably over both file:// and http://.
        # Uses epoch milliseconds to match GENERATED_AT precision in the JS.
        stamp_file = BASE_DIR / "dashboard.stamp"
        with open(stamp_file, 'w') as f:
            f.write(str(int(datetime.now().timestamp() * 1000)))

        print("\nDashboard generated successfully!")
        print(f"File saved: {output_file}")

        if args.serve:
            _start_server(args.port, ynab=ynab, budget_id=budget_id, config=config)
        else:
            print("\nOpen the HTML file in your browser to view your dashboard.")
            print("Tip: run with --serve to start a local web server for iPhone access.")

    except requests.exceptions.HTTPError as e:
        print(f"\nAPI Error: {e}")
        print("Please check your API token is valid")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
