"""Email HTML builder — INBOX view with searchable move popover."""

import json
from html import escape
from urllib.parse import quote


def build_mail_html(messages_by_folder, all_folders=None, include_scripts=True):
    """Build the Email tab HTML showing INBOX only.

    all_folders: list of (account, folder_name) tuples from get_all_mail_folders()
    include_scripts: if False, omit the inline <script> tags (for AJAX updates).
    """
    if messages_by_folder is None:
        return '''<div class="card">
            <h3>Email</h3>
            <p class="muted">Could not connect to Mail.app. Make sure Mail is running and grant automation access when prompted.</p>
        </div>'''

    if not messages_by_folder:
        return '''<div class="card">
            <h3>Email</h3>
            <p class="muted">No messages found.</p>
        </div>'''

    # Just use INBOX (or first available folder)
    messages = messages_by_folder.get("INBOX") or next(iter(messages_by_folder.values()), [])

    unread_count = sum(1 for m in messages if not m.get("read"))
    total_count = len(messages)

    # Embed folder list as JS for the searchable move popover
    # all_folders is [(account, name), ...] — we pass just the names to JS
    folder_names = [f for _, f in all_folders] if all_folders else []
    folders_js = json.dumps(folder_names)

    parts = []
    # Inject folder data at the top so the JS popover can use it
    if include_scripts:
        parts.append(f'<script>window.MAIL_MOVE_FOLDERS = {folders_js};</script>')
    parts.append('<div class="mail-client">')

    # Toolbar: compose + search
    parts.append(
        '<div class="mail-toolbar">'
        '<button class="mail-compose-btn" onclick="window.location.href=\'mailto:\'" title="Compose new email">'
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        ' Compose</button>'
        '<input class="mail-search" type="text" placeholder="Search inbox..." oninput="filterMailMessages(this.value)" />'
        '</div>'
    )

    # Summary line
    summary = f'{unread_count} unread &middot; {total_count} total'
    parts.append(f'<div class="mail-summary">{summary}</div>')

    # Message list — most recent first within each group
    def _sort_key(m):
        from datetime import datetime
        for fmt in ('%A, %B %d, %Y at %I:%M:%S\u202f%p',
                    '%A, %B %d, %Y at %I:%M:%S %p',
                    '%A, %B %d, %Y, %I:%M:%S\u202f%p',
                    '%A, %B %d, %Y, %I:%M:%S %p'):
            try:
                return datetime.strptime(m.get('date','').strip(), fmt)
            except ValueError:
                pass
        return datetime.min

    unread = sorted([m for m in messages if not m.get("read")],  key=_sort_key, reverse=True)
    read   = sorted([m for m in messages if m.get("read")],      key=_sort_key, reverse=True)

    if unread:
        parts.append('<div class="mail-group-label">Unread</div>')
        for msg in unread:
            parts.append(_mail_item(msg))

    if read:
        parts.append('<div class="mail-group-label">Recent</div>')
        for msg in read:
            parts.append(_mail_item(msg))

    if not messages:
        parts.append('<p class="mail-empty">No messages in inbox.</p>')

    parts.append('</div>')  # end mail-client

    return '\n'.join(parts)


def _mail_item(msg):
    """Render a single mail item row."""
    subj = escape(msg["subject"]) or "(No Subject)"
    sender_raw = msg["sender"]
    sender_display = escape(sender_raw)
    if '<' in sender_raw:
        sender_display = escape(sender_raw.split('<')[0].strip().strip('"\''))

    sender_email = ''
    if '<' in sender_raw and '>' in sender_raw:
        sender_email = sender_raw.split('<')[1].split('>')[0].strip()
    elif '@' in sender_raw:
        sender_email = sender_raw.strip()

    date_str = escape(msg["date"])
    flagged   = ' mail-flagged' if msg.get("flagged") else ''
    unread_cls = ' mail-unread' if not msg.get("read") else ''
    flag_icon  = '<span class="mail-flag-icon">&#9873;</span>' if msg.get("flagged") else ''

    message_id  = msg.get("message_id", "")
    mid_encoded = quote(message_id, safe='') if message_id else ''

    # Open in Mail.app
    open_btn = ''
    if message_id:
        open_btn = (
            f'<a class="mail-action-btn" href="mailhelper://open?id={mid_encoded}" title="Open in Mail">'
            f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>'
            f'</a>'
        )

    # Reply
    reply_btn = ''
    if sender_email:
        reply_subject = quote(f'Re: {msg["subject"]}', safe='')
        reply_btn = (
            f'<a class="mail-action-btn" href="mailto:{escape(sender_email)}?subject={reply_subject}" title="Reply">'
            f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/></svg>'
            f'</a>'
        )

    # Move to folder (searchable popover)
    move_btn = ''
    if message_id:
        move_btn = (
            f'<button class="mail-action-btn mail-move-btn" '
            f'onclick="openMovePopover(this, \'{mid_encoded}\')" title="Move to folder">'
            f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
            f'</button>'
        )

    # Delete — use data-id to avoid quote-escaping issues in onclick
    delete_btn = ''
    if message_id:
        delete_btn = (
            f'<button class="mail-action-btn mail-delete-btn" '
            f'data-mail-id="{escape(message_id)}" title="Delete">'
            f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
            f'</button>'
        )

    actions_inner = open_btn + reply_btn + move_btn + delete_btn
    actions = f'<div class="mail-actions">{actions_inner}</div>' if actions_inner else ''
    open_url_attr = f' data-open-url="mailhelper://open?id={mid_encoded}"' if message_id else ''

    return (
        f'<div class="mail-item{unread_cls}{flagged}"{open_url_attr} '
        f'data-subject="{subj.lower()}" data-sender="{sender_display.lower()}">'
        f'<div class="mail-item-header">'
        f'<span class="mail-sender">{sender_display}{flag_icon}</span>'
        f'<span class="mail-date">{date_str}</span>'
        f'</div>'
        f'<div class="mail-subject">{subj}</div>'
        f'{actions}'
        f'</div>'
    )
