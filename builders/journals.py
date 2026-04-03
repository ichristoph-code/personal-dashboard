"""Cardiology journal articles HTML builder."""

from collections import defaultdict
from datetime import datetime, timezone
from html import escape


def _relative_date(parsed_date):
    if not parsed_date:
        return ""
    try:
        now = datetime.now(timezone.utc)
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        delta = now - parsed_date
        days = delta.days
        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days}d ago"
        else:
            return parsed_date.strftime("%b %-d")
    except Exception:
        return ""


_SOURCE_ICONS = {
    "Healio Cardiology": "🩺",
    "Medpage Cardiology": "📋",
    "Cardiobrief":        "💬",
}


def build_journals_html(articles):
    """Build the Journals tab HTML."""
    if not articles:
        return (
            '<div class="card journals-empty">'
            '<div class="journals-empty-icon">📚</div>'
            '<h3>Cardiology Journals</h3>'
            '<p class="muted">Could not load journal feeds. Check your internet connection.</p>'
            '</div>'
        )

    by_source = defaultdict(list)
    for item in articles:
        by_source[item["source"]].append(item)

    parts = [
        '<div class="journals-header"><h3>Cardiology — Latest</h3></div>',
    ]

    for source_name, items in by_source.items():
        icon = _SOURCE_ICONS.get(source_name, "📰")
        parts.append(
            f'<div class="journals-source-group">'
            f'<div class="journals-source-label">{icon} {escape(source_name)}</div>'
            f'<ul class="journals-list">'
        )
        for item in items:
            title = escape(item["title"])
            link  = escape(item.get("link", "#"))
            parts.append(
                f'<li class="journal-item">'
                f'<a href="{link}" target="_blank" rel="noopener" class="journal-title">{title}</a>'
                f'</li>'
            )
        parts.append('</ul></div>')

    return '\n'.join(parts)
