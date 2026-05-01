"""Contacts tab + Birthdays card HTML builders."""

from html import escape


_DEFAULT_AVATAR = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E"
    "%3Ccircle cx='20' cy='20' r='20' fill='%23a0aec0'/%3E"
    "%3Ccircle cx='20' cy='15' r='7' fill='%23fff'/%3E"
    "%3Cpath d='M6 36a14 14 0 0 1 28 0' fill='%23fff'/%3E"
    "%3C/svg%3E"
)


def build_contacts_html(contacts, include_scripts=True):
    """Build a two-panel contacts UI: list sidebar + detail pane.

    Args:
        contacts: list of contact dicts from get_all_contacts()
        include_scripts: if False, omit inline <script> tags (for AJAX).
    """
    if not contacts:
        return (
            '<div class="card">'
            '<h3>Contacts</h3>'
            '<p class="muted">No contacts found. Ensure Terminal has Full Disk Access.</p>'
            '</div>'
        )

    # Build contact index for JS
    contact_index = []
    for c in contacts:
        contact_index.append({
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
            "phones": c.get("phones", []),
            "emails": c.get("emails", []),
            "addresses": c.get("addresses", []),
            "urls": c.get("urls", []),
            "ims": c.get("ims", []),
            "related": c.get("related", []),
            "thumb": c.get("thumb", ""),
            "note": c.get("note", ""),
        })

    # Group by first letter
    groups = {}
    for c in contacts:
        letter = (c["name"][0] if c["name"] else "#").upper()
        if not letter.isalpha():
            letter = "#"
        groups.setdefault(letter, []).append(c)

    parts = ['<div class="contacts-client">']

    # ── Left sidebar ──
    parts.append('<div class="contacts-sidebar">')
    parts.append(
        '<div class="contacts-sidebar-header">'
        f'<span>Contacts</span>'
        f'<span class="contacts-count">{len(contacts)}</span>'
        '</div>'
    )
    parts.append(
        '<input class="contacts-search" type="text" '
        'placeholder="Search contacts..." '
        'oninput="filterContacts(this.value)" />'
    )
    parts.append('<div class="contacts-list">')

    for letter in sorted(groups.keys()):
        parts.append(
            f'<div class="contacts-letter-group" data-letter="{escape(letter)}">'
            f'<div class="contacts-letter-header">{escape(letter)}</div>'
        )
        for c in groups[letter]:
            cid = c["id"]
            name = escape(c["name"])
            org = escape(c.get("org", ""))
            thumb = c.get("thumb") or _DEFAULT_AVATAR
            bday_dot = ""
            if c.get("birthday"):
                bday_dot = '<span class="contacts-bday-dot" title="Has birthday">🎂</span>'

            org_html = f'<span class="contacts-item-org">{org}</span>' if org and org != c["name"] else ""

            parts.append(
                f'<div class="contacts-item" data-cid="{cid}" '
                f'onclick="selectContact({cid})">'
                f'<img class="contacts-avatar" src="{thumb}" alt="" />'
                f'<div class="contacts-item-info">'
                f'<span class="contacts-item-name">{name}</span>'
                f'{org_html}'
                f'</div>'
                f'{bday_dot}'
                f'</div>'
            )
        parts.append('</div>')  # letter-group

    parts.append('</div>')  # contacts-list
    parts.append('</div>')  # contacts-sidebar

    # ── Right detail pane ──
    parts.append(
        '<div class="contacts-detail" id="contactsDetail">'
        '<div class="contacts-detail-empty">'
        '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" '
        'stroke="var(--text-faint)" stroke-width="1.5" stroke-linecap="round">'
        '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>'
        '<circle cx="12" cy="7" r="4"/>'
        '</svg>'
        '<p>Select a contact to view details</p>'
        '</div>'
        '</div>'
    )

    parts.append('</div>')  # contacts-client

    # Embed contact data as JSON for JS
    if include_scripts:
        import json
        parts.append(
            f'<script>var CONTACTS_INDEX = {json.dumps(contact_index)};</script>'
        )

    return "\n".join(parts)


def build_birthdays_card(upcoming_birthdays):
    """Build a compact card showing upcoming birthdays.

    Args:
        upcoming_birthdays: list from get_upcoming_birthdays()
    """
    if not upcoming_birthdays:
        return (
            '<div class="card birthdays-card">'
            '<h3>🎂 Upcoming Birthdays</h3>'
            '<p class="empty-state">No birthdays in the next 30 days</p>'
            '</div>'
        )

    parts = [
        '<div class="card birthdays-card">',
        '<h3>🎂 Upcoming Birthdays</h3>',
        '<div class="birthdays-list">',
    ]

    for b in upcoming_birthdays[:10]:  # cap at 10
        name = escape(b["name"])
        display = escape(b["birthday_display"])
        thumb = b.get("thumb") or _DEFAULT_AVATAR
        days = b["days_until"]

        # Days label
        if days == 0:
            days_label = '<span class="bday-days bday-today">Today!</span>'
        elif days == 1:
            days_label = '<span class="bday-days bday-soon">Tomorrow</span>'
        elif days <= 7:
            days_label = f'<span class="bday-days bday-soon">In {days} days</span>'
        else:
            days_label = f'<span class="bday-days">{display}</span>'

        # Age badge
        age_html = ""
        if b.get("age") is not None:
            age_html = f'<span class="bday-age">Turning {b["age"]}</span>'

        parts.append(
            f'<div class="bday-item">'
            f'<img class="bday-thumb" src="{thumb}" alt="" />'
            f'<div class="bday-info">'
            f'<span class="bday-name">{name}</span>'
            f'{age_html}'
            f'</div>'
            f'{days_label}'
            f'</div>'
        )

    parts.append('</div>')  # birthdays-list
    parts.append('</div>')  # birthdays-card
    return "\n".join(parts)
