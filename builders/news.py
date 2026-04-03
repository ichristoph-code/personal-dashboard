"""News feed HTML builder."""

import hashlib
from collections import OrderedDict
from html import escape

from .helpers import _relative_time


def build_news_html(headlines):
    """Build the News tab HTML, grouped by source."""
    if not headlines:
        return '''<div class="card">
            <h3>News</h3>
            <p class="muted">No headlines available. Check your RSS feed configuration.</p>
        </div>'''

    # Global header with saved filter + manage feeds button
    parts = []
    parts.append(
        '<div class="news-global-header">'
        '<h3>Headlines</h3>'
        '<div class="news-header-actions">'
        '<button class="news-filter-btn" id="newsFilterSaved" style="display:none" '
        'onclick="toggleNewsSavedFilter()" title="Show saved only">&#9733; Saved</button>'
        '<button class="news-manage-btn" onclick="openFeedManager()" title="Manage RSS feeds">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
        '</svg> Feeds</button>'
        '</div></div>'
    )

    # Group headlines by source, preserving order of first appearance
    grouped = OrderedDict()
    for item in headlines:
        src = item.get("source", "Other")
        grouped.setdefault(src, []).append(item)

    for source_name, items in grouped.items():
        source_esc = escape(source_name)
        source_id = source_name.replace(' ', '-').lower()
        parts.append(
            f'<div class="card news-section-card" draggable="true" data-source-id="{source_id}">'
            f'<div class="news-section-header">'
            f'<span class="news-drag-handle" title="Drag to reorder">&#x2807;</span>'
            f'<h3 class="news-section-title" onclick="toggleNewsSection(\'{source_id}\')">{source_esc}</h3>'
            f'<span class="news-section-count" onclick="toggleNewsSection(\'{source_id}\')">{len(items)}</span>'
            f'<span class="news-section-chevron" id="chevron-{source_id}" onclick="toggleNewsSection(\'{source_id}\')">&#9662;</span>'
            f'</div>'
            f'<div class="news-section-body" id="news-section-{source_id}">'
        )
        for item in items:
            title = escape(item["title"])
            link = escape(item.get("link", ""))
            parsed_dt = item.get("parsed_date")
            if parsed_dt:
                short_date = _relative_time(parsed_dt)
            else:
                date_str = escape(item.get("date", ""))
                short_date = date_str[:16] if len(date_str) > 16 else date_str
            onclick_row = f' onclick="if(!event.target.closest(\'button\'))window.open(\'{link}\',\'_blank\')" style="cursor:pointer"' if link else ''
            news_hash = hashlib.md5((item["title"] + item.get("source", "")).encode()).hexdigest()[:8]
            parts.append(
                f'<div class="news-item" data-hash="{news_hash}"{onclick_row}>'
                f'<span class="news-title">{title}</span>'
                f'<span class="news-actions">'
                f'<button class="news-read-btn" onclick="toggleNewsRead(\'{news_hash}\', this)" title="Mark as read">&#10003;</button>'
                f'<button class="news-save-btn" onclick="toggleNewsSaved(\'{news_hash}\', this)" title="Save for later">&#9734;</button>'
                f'</span>'
                f'</div>'
            )
        parts.append('</div></div>')

    # ── Feed Manager Modal ──
    parts.append(
        '<div class="feed-mgr-overlay" id="feedManagerOverlay" style="display:none">'
        '<div class="feed-mgr-modal">'
        '<div class="feed-mgr-header">'
        '<h3>Manage RSS Feeds</h3>'
        '<button class="feed-mgr-close" onclick="closeFeedManager()">&times;</button>'
        '</div>'
        '<div class="feed-mgr-body" id="feedManagerBody">'
        '<!-- rows injected by JS -->'
        '</div>'
        '<div class="feed-mgr-add-row">'
        '<input type="text" class="feed-mgr-input feed-mgr-name" id="feedNewName" placeholder="Feed name\u2026">'
        '<input type="text" class="feed-mgr-input feed-mgr-url" id="feedNewUrl" placeholder="RSS URL\u2026">'
        '<button class="feed-mgr-add-btn" onclick="addFeedRow()" title="Add feed">+</button>'
        '</div>'
        '<div class="feed-mgr-footer">'
        '<button class="feed-mgr-save" onclick="saveFeedChanges()">Save</button>'
        '<button class="feed-mgr-cancel" onclick="closeFeedManager()">Cancel</button>'
        '</div>'
        '</div></div>'
    )

    return '\n'.join(parts)
