"""iMessage HTML builder — conversation list + message thread view."""

from collections import Counter
from html import escape


def build_imessage_html(conversations):
    """Build the iMessage tab HTML.

    conversations: list of dicts from sources/imessage.py, or None if inaccessible.
    """
    if conversations is None:
        return '''
        <div class="card imsg-permission-card">
            <div class="imsg-permission-icon">💬</div>
            <h3>iMessage Access Required</h3>
            <p class="muted">To display iMessages, grant <strong>Full Disk Access</strong> to Terminal:</p>
            <ol class="imsg-permission-steps">
                <li>Open <strong>System Settings → Privacy &amp; Security → Full Disk Access</strong></li>
                <li>Click <strong>+</strong> and add <strong>Terminal</strong></li>
                <li>Re-run the dashboard from Terminal</li>
            </ol>
        </div>'''

    if not conversations:
        return '''
        <div class="card">
            <h3>iMessage</h3>
            <p class="muted">No recent conversations found.</p>
        </div>'''

    total_unread = sum(c["unread_count"] for c in conversations)

    parts = []
    parts.append('<div class="imsg-client">')

    # ── Conversation list (left pane) ──
    parts.append('<div class="imsg-sidebar">')
    total_badge = f'<span class="imsg-total-badge">{total_unread}</span>' if total_unread else ''
    parts.append(
        '<div class="imsg-sidebar-header">'
        f'<span>Messages</span>{total_badge}'
        '</div>'
    )
    parts.append('<input class="imsg-search" type="text" placeholder="Search conversations..." oninput="filterImessages(this.value)" />')
    parts.append('<div class="imsg-convo-list">')

    for i, convo in enumerate(conversations):
        cid = convo["id"]
        name = escape(convo["display_name"])
        last_date = escape(convo["last_date"])
        unread = convo["unread_count"]
        if convo["messages"]:
            _last = convo["messages"][-1]
            last_msg = _last["text"]
            if not last_msg and _last.get("attachments"):
                _aicons = {"image": "📷 Photo", "video": "🎬 Video", "audio": "🎵 Audio",
                           "contact": "👤 Contact", "location": "📍 Location",
                           "pdf": "📄 PDF", "file": "📎 File"}
                last_msg = _aicons.get(_last["attachments"][0], "📎 Attachment")
        else:
            last_msg = ""
        preview = escape(last_msg[:60] + ("…" if len(last_msg) > 60 else ""))
        unread_cls = " imsg-convo-unread" if unread > 0 else ""
        active_cls = " active" if i == 0 else ""
        badge = f'<span class="imsg-unread-badge">{unread}</span>' if unread > 0 else ''

        # Use contact photo if available, otherwise initials
        thumb = convo.get("thumb")
        if thumb:
            avatar_html = f'<img class="imsg-avatar imsg-avatar-img" src="{thumb}" alt="">'
        else:
            initials = _initials(convo["display_name"])
            avatar_html = f'<div class="imsg-avatar">{initials}</div>'

        parts.append(
            f'<div class="imsg-convo-item{unread_cls}{active_cls}" '
            f'data-cid="{cid}" data-name="{name.lower()}" '
            f'onclick="switchImsgConvo({cid}, this)">'
            f'{avatar_html}'
            f'<div class="imsg-convo-info">'
            f'<div class="imsg-convo-row">'
            f'<span class="imsg-convo-name">{name}</span>'
            f'<span class="imsg-convo-date">{last_date}</span>'
            f'</div>'
            f'<div class="imsg-convo-preview">{preview}{badge}</div>'
            f'</div>'
            f'</div>'
        )

    parts.append('</div>')  # end convo-list
    parts.append('</div>')  # end sidebar

    # ── Message thread pane (right) ──
    parts.append('<div class="imsg-thread-pane">')

    for i, convo in enumerate(conversations):
        cid = convo["id"]
        name = escape(convo["display_name"])
        active_cls = " active" if i == 0 else ""
        _first_p = convo["participants"][0] if convo["participants"] else ""
        imsg_url = f"imessage://{_first_p}" if _first_p.startswith("+") else f"imessage://+{_first_p}" if _first_p else "imessage://"

        parts.append(f'<div class="imsg-thread{active_cls}" data-thread="{cid}">')

        # Thread header with search
        parts.append(
            f'<div class="imsg-thread-header">'
            f'<span class="imsg-thread-name">{name}</span>'
            f'<div class="imsg-thread-actions">'
            f'<input class="imsg-thread-search" type="text" placeholder="Search messages\u2026" '
            f'oninput="searchImsgThread(this)" />'
            f'<a class="imsg-open-btn" href="{escape(imsg_url)}" title="Open in Messages">'
            f'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
            f'<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
            f' Open</a>'
            f'</div>'
            f'</div>'
        )

        # Messages
        parts.append('<div class="imsg-messages">')
        if not convo["messages"]:
            parts.append('<p class="imsg-empty">No messages</p>')
        else:
            # Find last outgoing message for receipt display
            last_out_idx = None
            for _ri in range(len(convo["messages"]) - 1, -1, -1):
                if convo["messages"][_ri]["is_from_me"]:
                    last_out_idx = _ri
                    break

            prev_sender = None
            for idx, msg in enumerate(convo["messages"]):
                bubble_cls = "imsg-bubble-me" if msg["is_from_me"] else "imsg-bubble-them"
                row_cls = "imsg-row-me" if msg["is_from_me"] else "imsg-row-them"
                text = escape(msg["text"]) if msg["text"] else ""
                date = escape(msg["date"])
                search_text = escape(msg["text"].lower()) if msg["text"] else ""

                # Sender label for group chats
                sender_label = ""
                if not msg["is_from_me"] and msg["sender"] != prev_sender and len(convo["participants"]) > 1:
                    sender_label = f'<div class="imsg-sender-label">{escape(msg["sender"])}</div>'

                # Attachment indicator
                attach_html = ""
                if msg.get("attachments"):
                    _icons = {"image": "📷", "video": "🎬", "audio": "🎵",
                              "contact": "👤", "location": "📍", "pdf": "📄", "file": "📎"}
                    acounts = Counter(msg["attachments"])
                    aparts = []
                    for atype, cnt in acounts.items():
                        icon = _icons.get(atype, "📎")
                        label = atype.capitalize()
                        aparts.append(f'{icon} {cnt} {label}s' if cnt > 1 else f'{icon} {label}')
                    attach_html = f'<div class="imsg-attach-label">{" · ".join(aparts)}</div>'

                # Tapback badges
                tapback_html = ""
                if msg.get("tapbacks"):
                    tcounts = Counter(msg["tapbacks"])
                    tbadges = []
                    for emoji, cnt in tcounts.items():
                        tbadges.append(f'{emoji}{cnt}' if cnt > 1 else emoji)
                    tapback_html = f'<div class="imsg-tapbacks">{" ".join(tbadges)}</div>'

                # Text (may be empty for attachment-only messages)
                text_html = f'<span class="imsg-text">{text}</span>' if text else ""

                parts.append(
                    f'{sender_label}'
                    f'<div class="imsg-row {row_cls}" data-search="{search_text}">'
                    f'<div class="imsg-bubble {bubble_cls}">'
                    f'{attach_html}'
                    f'{text_html}'
                    f'<span class="imsg-time">{date}</span>'
                    f'{tapback_html}'
                    f'</div>'
                    f'</div>'
                )

                # Delivery receipt (last outgoing message only)
                if idx == last_out_idx and msg["is_from_me"]:
                    if msg.get("is_read"):
                        parts.append('<div class="imsg-receipt imsg-receipt-read">Read</div>')
                    elif msg.get("is_delivered"):
                        parts.append('<div class="imsg-receipt">Delivered</div>')

                prev_sender = msg["sender"]

        parts.append('</div>')  # end messages

        # Compose bar — opens Messages app
        parts.append(
            f'<a class="imsg-compose" href="{escape(imsg_url)}" title="Reply in Messages">'
            f'<span class="imsg-compose-text">Reply in Messages\u2026</span>'
            f'<svg class="imsg-compose-icon" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">'
            f'<path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>'
            f'</a>'
        )

        parts.append('</div>')  # end thread

    parts.append('</div>')  # end thread-pane
    parts.append('</div>')  # end imsg-client

    return '\n'.join(parts)


def _initials(name):
    """Generate 1-2 letter avatar initials from a name."""
    words = name.strip().split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()
