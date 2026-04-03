"""SF Bay Area events HTML builder (RSS-based)."""

from collections import defaultdict
from datetime import datetime, timezone
from html import escape


def _relative_date(parsed_date):
    """Return 'Today', 'Yesterday', '3 days ago', etc."""
    if not parsed_date:
        return ""
    try:
        now = datetime.now(timezone.utc)
        # Make both tz-aware for comparison
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        delta = now - parsed_date
        days = delta.days
        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days} days ago"
        else:
            return parsed_date.strftime("%b %-d")
    except Exception:
        return ""


_SOURCE_ICONS = {
    "Funcheap SF":     "💰",
    "The Bold Italic": "✨",
    "48 Hills":        "🎭",
}


def build_events_html(events):
    """Build the SF Events tab HTML from RSS event items."""
    if not events:
        return (
            '<div class="card events-empty">'
            '<div class="events-empty-icon">🗓️</div>'
            '<h3>SF Bay Area Events</h3>'
            '<p class="muted">Could not load event feeds. Check your internet connection.</p>'
            '<p class="muted">You can customize sources by adding <code>event_feeds</code> to config.json.</p>'
            '</div>'
        )

    # Group by source
    by_source = defaultdict(list)
    for item in events:
        by_source[item["source"]].append(item)

    parts = [
        '<div class="events-header">',
        '<h3>SF Bay Area — Things To Do</h3>',
        '</div>',
    ]

    for source_name, items in by_source.items():
        icon = _SOURCE_ICONS.get(source_name, "📍")
        src_esc = escape(source_name)
        parts.append(
            f'<div class="events-source-group">'
            f'<div class="events-source-label">{icon} {src_esc}</div>'
            f'<div class="events-grid">'
        )

        for item in items:
            title = escape(item["title"])
            link  = escape(item.get("link", "#"))
            desc  = escape(item.get("description", ""))
            image = escape(item.get("image", ""))
            age   = escape(_relative_date(item.get("parsed_date")))

            img_html = (
                f'<div class="event-image">'
                f'<img src="{image}" alt="" loading="lazy"'
                f' onerror="this.parentElement.style.display=\'none\'">'
                f'</div>'
                if image else ''
            )
            age_html  = f'<span class="event-age">{age}</span>' if age else ''
            desc_html = f'<p class="event-desc">{desc}</p>' if desc else ''

            parts.append(
                f'<div class="event-card">'
                f'{img_html}'
                f'<div class="event-info">'
                f'<div class="event-name">{title}</div>'
                f'{desc_html}'
                f'<div class="event-footer">'
                f'{age_html}'
                f'<a href="{link}" target="_blank" rel="noopener" class="event-link">Read more →</a>'
                f'</div>'
                f'</div>'
                f'</div>'
            )

        parts.append('</div></div>')  # events-grid + events-source-group

    return '\n'.join(parts)
