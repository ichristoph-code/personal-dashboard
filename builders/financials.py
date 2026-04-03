"""Financial HTML builders for the Personal Dashboard.

Generates all HTML sections for the Financials tab including account cards,
savings goals, upcoming bills, recent transactions, debt tracking,
AI review, market overview, and finance quick links.
"""

from datetime import datetime
from html import escape

from .helpers import format_currency


# ── Collapsible section wrapper ──────────────────────────────────────────────

_CHEVRON_SVG = (
    '<svg class="fin-chevron" width="18" height="18" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>'
)


def fin_section(section_id, title, content, icon_svg="", default_open=True):
    """Wrap *content* in a collapsible finance section.

    Collapsed state is persisted in localStorage via JS.
    Section order is draggable and persisted via JS.
    """
    body_cls = "fin-section-body" if default_open else "fin-section-body collapsed"
    hdr_cls = "fin-section-header" if default_open else "fin-section-header collapsed"
    return (
        f'<div class="fin-section" id="{section_id}" data-section-id="{section_id}" draggable="true">'
        f'<div class="{hdr_cls}">'
        f'<span class="fin-drag-handle" title="Drag to reorder">&#x2807;</span>'
        f'<span class="fin-section-icon">{icon_svg}</span>'
        f"<h2>{title}</h2>"
        f"{_CHEVRON_SVG}"
        f"</div>"
        f'<div class="{body_cls}">'
        f"{content}"
        f"</div>"
        f"</div>"
    )


# ── SVG icon library (inline, no external deps) ─────────────────────────────

ICON_PIE = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>'
ICON_ACCOUNTS = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="18" rx="2"/><line x1="2" y1="9" x2="22" y2="9"/><line x1="10" y1="3" x2="10" y2="9"/></svg>'
ICON_BVA = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
ICON_GOALS = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>'
ICON_TREND = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>'
ICON_CATEGORY = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>'
ICON_BILLS = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>'
ICON_TXN = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'
ICON_PAYEES = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
ICON_DEBT = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>'
ICON_AI = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a5 5 0 0 1 5 5c0 2-1.5 3.5-3 4.5V14h-4v-2.5C8.5 10.5 7 9 7 7a5 5 0 0 1 5-5z"/><line x1="10" y1="17" x2="14" y2="17"/><line x1="10" y1="20" x2="14" y2="20"/><line x1="11" y1="23" x2="13" y2="23"/></svg>'
ICON_MARKET = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
ICON_NETWORTH = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 20l4-7 4 4 5-9 5 6"/><line x1="3" y1="20" x2="21" y2="20"/></svg>'
ICON_CHAT = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><line x1="9" y1="10" x2="15" y2="10"/></svg>'


# ── Account cards (enhanced with pending + health) ──────────────────────────

def build_account_card(title, accounts, empty_msg):
    """Build an account list card with pending balance and health indicators."""
    if not accounts:
        items = (
            f'<li class="account-item">'
            f'<span class="account-name">{empty_msg}</span>'
            f"</li>"
        )
    else:
        parts = []
        for acc in accounts:
            bal = format_currency(acc["balance"])
            cls = "positive" if acc["balance"] >= 0 else "negative"

            # Pending transactions indicator
            uncleared = acc.get("uncleared_balance", 0)
            pending_html = ""
            if uncleared != 0:
                pending_amt = format_currency(uncleared)
                sign = "+" if pending_amt >= 0 else ""
                pending_html = (
                    f'<span class="account-pending">'
                    f"{sign}{pending_amt:,.0f} pending</span>"
                )

            # Health dot based on last reconciliation
            health_html = ""
            last_recon = acc.get("last_reconciled_at")
            if last_recon:
                try:
                    recon_dt = datetime.fromisoformat(
                        last_recon.replace("Z", "+00:00")
                    )
                    days = (datetime.now(recon_dt.tzinfo) - recon_dt).days
                    if days > 30:
                        health_html = (
                            '<span class="acct-health health-red" '
                            f'title="Reconciled {days}d ago">●</span>'
                        )
                    elif days > 14:
                        health_html = (
                            '<span class="acct-health health-yellow" '
                            f'title="Reconciled {days}d ago">●</span>'
                        )
                    else:
                        health_html = (
                            '<span class="acct-health health-green" '
                            f'title="Reconciled {days}d ago">●</span>'
                        )
                except (ValueError, TypeError, OSError):
                    pass

            parts.append(
                f'<li class="account-item">'
                f'<div class="account-name-wrap">'
                f"{health_html}"
                f'<span class="account-name">{escape(acc["name"])}</span>'
                f"</div>"
                f'<div class="account-bal-wrap">'
                f'<span class="account-balance {cls}">${bal:,.0f}</span>'
                f"{pending_html}"
                f"</div>"
                f"</li>"
            )
        items = "\n".join(parts)

    return (
        f'<div class="card"><h3>{title}</h3>'
        f'<ul class="account-list">{items}</ul></div>'
    )


# ── Savings goals ────────────────────────────────────────────────────────────

def build_savings_goals_html(categories):
    """Build savings goal progress bars from YNAB category goal data."""
    goals = []
    for group in categories:
        if group["name"] == "Internal Master Category":
            continue
        for cat in group.get("categories", []):
            if cat.get("hidden"):
                continue
            if not cat.get("goal_type"):
                continue

            pct = cat.get("goal_percentage_complete", 0) or 0
            target = format_currency(cat.get("goal_target", 0) or 0)
            funded = format_currency(cat.get("goal_overall_funded", 0) or 0)
            target_month = cat.get("goal_target_month")

            date_str = ""
            if target_month:
                try:
                    dt = datetime.strptime(target_month, "%Y-%m-%d")
                    date_str = f" by {dt.strftime('%b %Y')}"
                except ValueError:
                    pass

            goals.append(
                {
                    "name": cat["name"],
                    "pct": min(int(pct), 100),
                    "target": target,
                    "funded": funded,
                    "date_str": date_str,
                }
            )

    if not goals:
        return ""

    goals.sort(key=lambda g: g["pct"])

    parts = []
    for g in goals:
        if g["pct"] >= 100:
            bar_color = "var(--green)"
        elif g["pct"] >= 50:
            bar_color = "var(--accent)"
        else:
            bar_color = "var(--orange)"
        check = " ✓" if g["pct"] >= 100 else ""

        parts.append(
            f'<div class="goal-item">'
            f'<div class="goal-header">'
            f'<span class="goal-name">{escape(g["name"])}{check}</span>'
            f'<span class="goal-detail">'
            f'${g["funded"]:,.0f} of ${g["target"]:,.0f}{g["date_str"]}'
            f"</span>"
            f"</div>"
            f'<div class="goal-bar-track">'
            f'<div class="goal-bar-fill" style="width:{g["pct"]}%;'
            f'background:{bar_color}"></div>'
            f"</div>"
            f'<div class="goal-pct">{g["pct"]}%</div>'
            f"</div>"
        )

    content = '<div class="goals-list">' + "\n".join(parts) + "</div>"
    return fin_section("sec-goals", "Savings Goals", content, ICON_GOALS)


# ── Upcoming bills ───────────────────────────────────────────────────────────

_FREQ_LABELS = {
    "never": "One-time",
    "daily": "Daily",
    "weekly": "Weekly",
    "everyOtherWeek": "Bi-weekly",
    "twiceAMonth": "Twice/mo",
    "every4Weeks": "Every 4 wks",
    "monthly": "Monthly",
    "everyOtherMonth": "Bi-monthly",
    "every3Months": "Quarterly",
    "every4Months": "Every 4 mo",
    "twiceAYear": "Twice/yr",
    "yearly": "Yearly",
    "everyOtherYear": "Every 2 yrs",
}


def build_upcoming_bills_html(scheduled):
    """Build upcoming bills list from YNAB scheduled transactions."""
    if not scheduled:
        return ""

    now_str = datetime.now().strftime("%Y-%m-%d")
    upcoming = [
        s for s in scheduled
        if s.get("date_next", "") >= now_str and not s.get("deleted")
    ]
    upcoming.sort(key=lambda s: s.get("date_next", ""))
    upcoming = upcoming[:15]

    if not upcoming:
        return ""

    total = 0
    parts = []
    for bill in upcoming:
        amt = format_currency(bill.get("amount", 0))
        total += amt
        cls = "positive" if amt >= 0 else "negative"
        payee = escape(bill.get("payee_name") or "Unknown")
        cat = escape(bill.get("category_name") or "")
        freq = _FREQ_LABELS.get(bill.get("frequency", ""), bill.get("frequency", ""))

        try:
            dt = datetime.strptime(bill["date_next"], "%Y-%m-%d")
            date_str = dt.strftime("%b %d")
        except (ValueError, KeyError):
            date_str = ""

        meta_parts = [p for p in (cat, freq) if p]
        meta = " · ".join(meta_parts)

        parts.append(
            f'<div class="bill-item">'
            f'<div class="bill-info">'
            f'<span class="bill-payee">{payee}</span>'
            f'<span class="bill-meta">{meta}</span>'
            f"</div>"
            f'<div class="bill-right">'
            f'<span class="bill-amount {cls}">${abs(amt):,.0f}</span>'
            f'<span class="bill-date">{date_str}</span>'
            f"</div>"
            f"</div>"
        )

    total_cls = "positive" if total >= 0 else "negative"
    summary = (
        f'<div class="bills-summary">'
        f'Total upcoming: <strong class="{total_cls}">${abs(total):,.0f}</strong>'
        f"</div>"
    )
    content = '<div class="bills-list">' + "\n".join(parts) + "</div>" + summary
    return fin_section("sec-bills", "Upcoming Bills", content, ICON_BILLS, default_open=False)


# ── Recent transactions ──────────────────────────────────────────────────────

def build_recent_transactions_html(transactions):
    """Build a scrollable recent transactions feed."""
    if not transactions:
        return ""

    txns = sorted(
        transactions, key=lambda t: t.get("date", ""), reverse=True
    )[:30]

    parts = []
    for txn in txns:
        amt = format_currency(txn.get("amount", 0))
        cls = "positive" if amt >= 0 else "negative"
        payee = escape(txn.get("payee_name") or txn.get("memo") or "Unknown")
        cat = escape(txn.get("category_name") or "")
        acct = escape(txn.get("account_name") or "")

        cleared = txn.get("cleared", "")
        if cleared == "uncleared":
            status_dot = '<span class="txn-status pending-dot" title="Pending">○</span>'
        elif cleared == "reconciled":
            status_dot = '<span class="txn-status recon-dot" title="Reconciled">●</span>'
        else:
            status_dot = ""

        try:
            dt = datetime.strptime(txn["date"], "%Y-%m-%d")
            date_str = dt.strftime("%b %d")
        except (ValueError, KeyError):
            date_str = ""

        meta_parts = [p for p in (cat, acct) if p]
        meta = " · ".join(meta_parts)

        parts.append(
            f'<div class="txn-item">'
            f'<div class="txn-info">'
            f"{status_dot}"
            f'<div class="txn-text">'
            f'<span class="txn-payee">{payee}</span>'
            f'<span class="txn-meta">{meta}</span>'
            f"</div>"
            f"</div>"
            f'<div class="txn-right">'
            f'<span class="txn-amount {cls}">${amt:,.2f}</span>'
            f'<span class="txn-date">{date_str}</span>'
            f"</div>"
            f"</div>"
        )

    content = '<div class="txn-list">' + "\n".join(parts) + "</div>"
    return fin_section(
        "sec-transactions", "Recent Transactions", content, ICON_TXN, default_open=False
    )


# ── Debt tracker ─────────────────────────────────────────────────────────────

def build_debt_tracker_html(accounts):
    """Build debt tracking cards for accounts with outstanding debt."""
    debt_accounts = []
    for acc in accounts:
        if acc.get("closed"):
            continue
        if acc["balance"] >= 0:
            continue
        if acc["type"] in ("creditCard", "lineOfCredit", "otherDebt"):
            debt_accounts.append(acc)

    if not debt_accounts:
        return ""

    parts = []
    for acc in debt_accounts:
        bal = format_currency(acc["balance"])
        name = escape(acc["name"])

        # Try to extract debt-specific info
        detail_parts = []
        rate_info = acc.get("debt_interest_rates") or {}
        if rate_info and isinstance(rate_info, dict):
            for date_key in sorted(rate_info.keys(), reverse=True):
                rate_raw = rate_info[date_key]
                if rate_raw:
                    # YNAB stores rate as milliunit percentage (e.g., 19500 = 19.5%)
                    rate_pct = rate_raw / 1000
                    detail_parts.append(f"{rate_pct:.1f}% APR")
                break

        min_info = acc.get("debt_minimum_payments") or {}
        if min_info and isinstance(min_info, dict):
            for date_key in sorted(min_info.keys(), reverse=True):
                min_raw = min_info[date_key]
                if min_raw:
                    min_pay = format_currency(min_raw)
                    detail_parts.append(f"Min: ${abs(min_pay):,.0f}")
                break

        orig_raw = acc.get("debt_original_balance", 0) or 0
        orig = format_currency(orig_raw) if orig_raw else 0

        pct = 0
        if orig != 0:
            pct = max(0, min(100, round((1 - abs(bal) / abs(orig)) * 100)))
            detail_parts.append(f"Original: ${abs(orig):,.0f}")

        detail_str = " · ".join(detail_parts) if detail_parts else ""

        if pct >= 75:
            bar_color = "var(--green)"
        elif pct >= 40:
            bar_color = "var(--accent)"
        else:
            bar_color = "var(--orange)"

        progress_html = ""
        if orig != 0:
            progress_html = (
                f'<div class="goal-bar-track">'
                f'<div class="goal-bar-fill" style="width:{pct}%;'
                f'background:{bar_color}"></div>'
                f"</div>"
                f'<div class="goal-pct">{pct}% paid off</div>'
            )

        parts.append(
            f'<div class="debt-card">'
            f'<div class="debt-header">'
            f'<span class="debt-name">{name}</span>'
            f'<span class="debt-balance negative">${abs(bal):,.0f} owed</span>'
            f"</div>"
            + (f'<div class="debt-detail">{detail_str}</div>' if detail_str else "")
            + progress_html
            + "</div>"
        )

    content = '<div class="debt-list">' + "\n".join(parts) + "</div>"
    return fin_section("sec-debt", "Debt Tracker", content, ICON_DEBT)


# ── Claude AI review ─────────────────────────────────────────────────────────

def build_claude_review_html(review_html):
    """Build the AI financial review section."""
    if not review_html:
        content = (
            '<div class="review-placeholder">'
            "<p>Add <code>&quot;anthropic_api_key&quot;: &quot;sk-...&quot;</code> "
            "to your <code>config.json</code> to enable AI-powered financial reviews.</p>"
            "</div>"
        )
        return fin_section("sec-review", "AI Financial Review", content, ICON_AI, default_open=False)

    content = f'<div class="review-content">{review_html}</div>'
    return fin_section("sec-review", "AI Financial Review", content, ICON_AI)


# ── Market overview ──────────────────────────────────────────────────────────

def build_market_overview_html(market_data):
    """Build market index cards from fetched market data."""
    if not market_data:
        return ""

    parts = []
    for item in market_data:
        change = item.get("change", 0)
        change_pct = item.get("change_pct", 0)
        cls = "positive" if change >= 0 else "negative"
        arrow = "▲" if change >= 0 else "▼"
        name = escape(item.get("name", item.get("symbol", "")))
        price = item.get("price", 0)

        parts.append(
            f'<div class="market-card">'
            f'<div class="market-name">{name}</div>'
            f'<div class="market-price">${price:,.2f}</div>'
            f'<div class="market-change {cls}">'
            f"{arrow} {abs(change):,.2f} ({abs(change_pct):.2f}%)"
            f"</div>"
            f"</div>"
        )

    content = '<div class="market-grid">' + "\n".join(parts) + "</div>"
    return fin_section("sec-market", "Market Overview", content, ICON_MARKET, default_open=False)


# ── Finance quick links ──────────────────────────────────────────────────────

def build_finance_links_html():
    """Build a row of finance quick-link buttons."""
    links = [
        ("YNAB", "https://app.ynab.com", "💰"),
        ("Credit Karma", "https://www.creditkarma.com", "📊"),
        ("Fidelity", "https://www.fidelity.com", "📈"),
        ("IRS", "https://www.irs.gov", "🏛️"),
    ]
    parts = []
    for name, url, emoji in links:
        parts.append(
            f'<a href="{url}" target="_blank" rel="noopener" class="fin-link">'
            f"{emoji} {name}</a>"
        )
    return '<div class="fin-links">' + "\n".join(parts) + "</div>"


# ── Net worth chart ─────────────────────────────────────────────────────────

def build_networth_chart_html():
    """Build the net worth over time line chart section."""
    content = '<div class="nw-chart-wrap"><canvas id="nwChart"></canvas></div>'
    return fin_section("sec-networth", "Net Worth Over Time", content, ICON_NETWORTH)


# ── Claude financial chat ────────────────────────────────────────────────────

def build_claude_chat_html(has_api_key=False):
    """Build the interactive Claude financial Q&A section."""
    if not has_api_key:
        content = (
            '<div class="review-placeholder">'
            "<p>Add <code>&quot;anthropic_api_key&quot;: &quot;sk-...&quot;</code> "
            "to your <code>config.json</code> to enable the AI financial assistant.</p>"
            "</div>"
        )
        return fin_section("sec-claude-chat", "Ask Claude", content, ICON_CHAT, default_open=False)

    content = (
        '<div class="claude-chat">'
        '<div class="claude-chat-messages" id="claudeChatMessages">'
        '<div class="claude-chat-welcome">'
        "Ask me anything about your finances &mdash; budgeting advice, "
        "spending analysis, savings strategies, or general financial questions."
        "</div>"
        "</div>"
        '<div class="claude-chat-input-wrap">'
        '<input type="text" id="claudeChatInput" class="claude-chat-input" '
        'placeholder="e.g. How can I reduce my grocery spending?" '
        'onkeydown="if(event.key===\'Enter\')sendClaudeQuery()" />'
        '<button class="claude-chat-send" onclick="sendClaudeQuery()" '
        'id="claudeChatSend" title="Send">'
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/>'
        '<polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>'
        "</button>"
        "</div>"
        "</div>"
    )
    return fin_section("sec-claude-chat", "Ask Claude", content, ICON_CHAT)
