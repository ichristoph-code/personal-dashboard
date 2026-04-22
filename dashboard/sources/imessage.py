"""iMessage conversations via Messages SQLite database (chat.db).

Requires Full Disk Access for the process running dashboard.py.
Grant it in: System Settings → Privacy & Security → Full Disk Access → add Terminal (or Python).
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .contacts import resolve_contacts_bulk

DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"

# Max conversations and messages per conversation to fetch
MAX_CONVOS = 30
MAX_MSGS_PER_CONVO = 20


def _apple_timestamp_to_dt(ts):
    """Convert Apple epoch (seconds since 2001-01-01) to datetime."""
    if ts is None:
        return None
    # Timestamps stored in nanoseconds in newer macOS versions
    if ts > 1e12:
        ts = ts / 1e9
    apple_epoch = 978307200  # 2001-01-01 UTC in Unix seconds
    return datetime.fromtimestamp(apple_epoch + ts, tz=timezone.utc)


def _format_dt(dt):
    """Format a datetime for display."""
    if dt is None:
        return ""
    now = datetime.now(tz=timezone.utc)
    delta = now - dt
    if delta.days == 0:
        return dt.astimezone().strftime("%-I:%M %p")
    elif delta.days == 1:
        return "Yesterday"
    elif delta.days < 7:
        return dt.astimezone().strftime("%A")
    else:
        return dt.astimezone().strftime("%b %-d")


def _resolve_handles_bulk(handle_ids, contact_cache):
    """Resolve a list of handles to contact names + thumbnails via AddressBook SQLite."""
    to_fetch = [h for h in handle_ids if h and h not in contact_cache]
    if not to_fetch:
        return

    resolved = resolve_contacts_bulk(to_fetch)
    for ident, info in resolved.items():
        contact_cache[ident] = info  # { "name": str, "thumb": str|None }

    # Ensure every handle has an entry (fallback to raw handle)
    for h in to_fetch:
        if h not in contact_cache:
            contact_cache[h] = {"name": h, "thumb": None}


def _resolve_handle(handle_id, contact_cache):
    """Look up a single handle from cache. Returns display name string."""
    entry = contact_cache.get(handle_id, None)
    if entry is None:
        return handle_id
    if isinstance(entry, dict):
        return entry.get("name", handle_id)
    return entry  # legacy string fallback


def _resolve_thumb(handle_id, contact_cache):
    """Look up a contact thumbnail data URI from cache."""
    entry = contact_cache.get(handle_id, None)
    if isinstance(entry, dict):
        return entry.get("thumb")
    return None


def get_imessages(max_convos=MAX_CONVOS, max_msgs=MAX_MSGS_PER_CONVO):
    """Read recent iMessage conversations from chat.db.

    Returns a list of conversation dicts, each with:
        id, display_name, participants, last_date, unread_count, messages[]

    Each message has: text, date, is_from_me, sender
    Returns None if db is inaccessible.
    """
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True,
                               check_same_thread=False)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        print(f"  iMessage DB error: {e}")
        return None

    try:
        contact_cache = {}
        conversations = []

        # Get recent chats sorted by most recent message
        chats = conn.execute("""
            SELECT
                c.ROWID        AS chat_id,
                c.guid         AS guid,
                c.display_name AS group_name,
                c.chat_identifier AS identifier,
                MAX(m.date)    AS last_msg_date,
                SUM(CASE WHEN m.is_read = 0 AND m.is_from_me = 0 THEN 1 ELSE 0 END) AS unread
            FROM chat c
            JOIN chat_message_join cmj ON cmj.chat_id = c.ROWID
            JOIN message m ON m.ROWID = cmj.message_id
            WHERE m.text IS NOT NULL AND m.text != ''
              AND m.associated_message_type = 0
            GROUP BY c.ROWID
            ORDER BY last_msg_date DESC
            LIMIT ?
        """, (max_convos,)).fetchall()

        # Pre-fetch all participants and message handles for bulk resolution
        chat_ids = [chat["chat_id"] for chat in chats]
        placeholders = ",".join("?" * len(chat_ids))
        all_handle_rows = conn.execute(f"""
            SELECT DISTINCT h.id FROM handle h
            JOIN chat_handle_join chj ON chj.handle_id = h.ROWID
            WHERE chj.chat_id IN ({placeholders})
        """, chat_ids).fetchall()
        all_msg_handle_rows = conn.execute(f"""
            SELECT DISTINCT h.id FROM handle h
            JOIN message m ON m.handle_id = h.ROWID
            JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
            WHERE cmj.chat_id IN ({placeholders})
              AND m.text IS NOT NULL AND m.text != ''
        """, chat_ids).fetchall()
        all_handles = list({row["id"] for row in all_handle_rows + all_msg_handle_rows if row["id"]})
        print(f"  Resolving {len(all_handles)} unique handles via Contacts...")
        _resolve_handles_bulk(all_handles, contact_cache)

        for chat in chats:
            chat_id = chat["chat_id"]
            last_dt = _apple_timestamp_to_dt(chat["last_msg_date"])

            # Get participants (handles)
            handles = conn.execute("""
                SELECT h.id FROM handle h
                JOIN chat_handle_join chj ON chj.handle_id = h.ROWID
                WHERE chj.chat_id = ?
            """, (chat_id,)).fetchall()

            participants = [row["id"] for row in handles]

            # Resolve display name
            group_name = chat["group_name"] or ""
            if not group_name:
                if len(participants) == 1:
                    group_name = _resolve_handle(participants[0], contact_cache)
                elif participants:
                    names = [_resolve_handle(p, contact_cache) for p in participants[:3]]
                    group_name = ", ".join(n.split()[0] if " " in n else n for n in names)
                    if len(participants) > 3:
                        group_name += f" +{len(participants) - 3}"
                else:
                    group_name = chat["identifier"] or "Unknown"

            # Get recent messages (include attachment-only; exclude tapbacks)
            rows = conn.execute("""
                SELECT
                    m.ROWID      AS msg_id,
                    m.guid       AS msg_guid,
                    m.text,
                    m.date,
                    m.is_from_me,
                    m.is_delivered,
                    m.date_read,
                    h.id AS handle_id
                FROM message m
                LEFT JOIN handle h ON h.ROWID = m.handle_id
                JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
                WHERE cmj.chat_id = ?
                  AND m.associated_message_type = 0
                  AND (
                    (m.text IS NOT NULL AND m.text != '')
                    OR m.ROWID IN (SELECT message_id FROM message_attachment_join)
                  )
                ORDER BY m.date DESC
                LIMIT ?
            """, (chat_id, max_msgs)).fetchall()

            # ── Attachment map: msg_id → list of type strings ──
            msg_rowids = [row["msg_id"] for row in rows]
            attachments_by_msg = {}
            if msg_rowids:
                ph = ",".join("?" * len(msg_rowids))
                for ar in conn.execute(f"""
                    SELECT maj.message_id, a.mime_type
                    FROM message_attachment_join maj
                    JOIN attachment a ON a.ROWID = maj.attachment_id
                    WHERE maj.message_id IN ({ph})
                """, msg_rowids).fetchall():
                    mid = ar["message_id"]
                    mime = ar["mime_type"] or ""
                    if mime.startswith("image/"):
                        atype = "image"
                    elif mime.startswith("video/"):
                        atype = "video"
                    elif mime.startswith("audio/"):
                        atype = "audio"
                    elif mime == "text/vcard":
                        atype = "contact"
                    elif mime == "text/x-vlocation":
                        atype = "location"
                    elif "pdf" in mime:
                        atype = "pdf"
                    else:
                        atype = "file"
                    attachments_by_msg.setdefault(mid, []).append(atype)

            # ── Tapback map: msg_guid → list of emoji strings ──
            _TAPBACK_EMOJI = {
                2000: "❤️", 2001: "👍", 2002: "😂",
                2003: "‼️", 2004: "👎", 2005: "❓",
            }
            reversed_rows = list(reversed(rows))
            msg_guid_set = {row["msg_guid"] for row in rows if row["msg_guid"]}
            tapbacks_by_guid = {}
            if msg_guid_set:
                oldest_date = min(row["date"] for row in rows) if rows else 0
                for tr in conn.execute("""
                    SELECT m.associated_message_guid,
                           m.associated_message_type,
                           m.associated_message_emoji
                    FROM message m
                    JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
                    WHERE cmj.chat_id = ?
                      AND m.associated_message_type BETWEEN 2000 AND 2006
                      AND m.date >= ?
                """, (chat_id, oldest_date)).fetchall():
                    assoc = tr["associated_message_guid"] or ""
                    target = assoc.split("/", 1)[1] if "/" in assoc else assoc
                    if target in msg_guid_set:
                        atype = tr["associated_message_type"]
                        emoji = _TAPBACK_EMOJI.get(atype, "")
                        if atype == 2006:
                            emoji = tr["associated_message_emoji"] or "👍"
                        if emoji:
                            tapbacks_by_guid.setdefault(target, []).append(emoji)

            # ── Build message dicts ──
            messages = []
            for row in reversed_rows:
                handle = row["handle_id"] or ""
                sender = "Me" if row["is_from_me"] else _resolve_handle(
                    handle, contact_cache
                )
                sender_thumb = None if row["is_from_me"] else _resolve_thumb(
                    handle, contact_cache
                )
                messages.append({
                    "text": row["text"] or "",
                    "date": _format_dt(_apple_timestamp_to_dt(row["date"])),
                    "is_from_me": bool(row["is_from_me"]),
                    "sender": sender,
                    "sender_thumb": sender_thumb,
                    "attachments": attachments_by_msg.get(row["msg_id"], []),
                    "tapbacks": tapbacks_by_guid.get(row["msg_guid"], []),
                    "is_delivered": bool(row["is_delivered"]) if row["is_from_me"] else None,
                    "is_read": bool(row["date_read"]) if row["is_from_me"] else None,
                })

            # Get thumbnail for the conversation (first participant)
            convo_thumb = None
            if len(participants) == 1:
                convo_thumb = _resolve_thumb(participants[0], contact_cache)

            conversations.append({
                "id": chat_id,
                "display_name": group_name,
                "participants": participants,
                "last_date": _format_dt(last_dt),
                "unread_count": chat["unread"] or 0,
                "messages": messages,
                "thumb": convo_thumb,
            })

        conn.close()
        total_unread = sum(c["unread_count"] for c in conversations)
        print(f"  Found {len(conversations)} iMessage conversations ({total_unread} unread)")
        return conversations

    except Exception as e:
        print(f"  iMessage error: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return None
