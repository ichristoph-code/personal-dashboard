"""Apple Mail messages via AppleScript — multi-mailbox support with cache fallback."""

import json
import subprocess
import time
from pathlib import Path

from . import atomic_write_json


# Default mailboxes to fetch. Can be overridden via config.json "mail_folders".
DEFAULT_FOLDERS = ["INBOX"]

_CACHE_FILE = Path(__file__).parent.parent / ".mail_cache.json"
_MSG_CACHE_MAX_AGE = 30 * 60    # 30 minutes — messages change frequently
_FOLDER_CACHE_MAX_AGE = 24 * 3600  # 24 hours — folder list rarely changes


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data):
    atomic_write_json(_CACHE_FILE, data)


def get_mail_messages(count=30, folders=None):
    """Get recent mail messages from multiple mailboxes via AppleScript.

    Returns a dict: { folder_name: [msg, ...], ... }
    Falls back to cached messages if Mail.app is unavailable.
    """
    if folders is None:
        folders = DEFAULT_FOLDERS

    cache = _load_cache()
    now = time.time()
    all_messages = {}
    used_cache = False

    for folder in folders:
        cache_key = f"msgs:{folder}"
        cached = cache.get(cache_key)
        msgs = _fetch_folder(folder, count)
        if msgs is not None:
            all_messages[folder] = msgs
            cache[cache_key] = {"ts": now, "data": msgs}
        elif cached and (now - cached["ts"]) < _MSG_CACHE_MAX_AGE:
            age_min = int((now - cached["ts"]) / 60)
            print(f"  Mail: using cached {folder} ({age_min} min old)")
            all_messages[folder] = cached["data"]
            used_cache = True
        else:
            # No live data and no usable cache — skip this folder
            pass

    _save_cache(cache)

    total = sum(len(v) for v in all_messages.values())
    suffix = " (cached)" if used_cache else ""
    print(f"  Found {total} mail messages across {len(all_messages)} folders{suffix}")
    return all_messages


def _fetch_folder(folder_name, count):
    """Fetch messages from a single named mailbox.

    Tries the top-level mailbox first; if that fails, searches all accounts
    for the first mailbox matching the name (handles Sent Messages, Deleted
    Messages, etc. that live under an account rather than at the top level).
    """
    if folder_name.upper() == "INBOX":
        # INBOX is always top-level
        target_script = "set targetBox to inbox"
    else:
        # Try top-level first; fall back to first account-level match
        target_script = f'''
        set targetBox to missing value
        try
            set targetBox to mailbox "{folder_name}"
        end try
        if targetBox is missing value then
            repeat with acct in accounts
                try
                    set targetBox to mailbox "{folder_name}" of acct
                    exit repeat
                end try
            end repeat
        end if
        if targetBox is missing value then return ""
        '''

    script = f'''
    tell application "Mail"
        set output to ""
        {target_script}
        set msgCount to count of messages of targetBox
        if msgCount < 1 then return ""
        if msgCount < {count} then
            set maxMsg to msgCount
        else
            set maxMsg to {count}
        end if
        repeat with i from msgCount to (msgCount - maxMsg + 1) by -1
            set msg to message i of targetBox
            if deleted status of msg is true then
            else
                set msgSubject to subject of msg
                set msgSender to sender of msg
                set msgDate to date received of msg as string
                set msgRead to read status of msg
                set msgFlagged to flagged status of msg
                set msgId to ""
                try
                    set msgId to message id of msg
                end try
                if msgId is "" then
                    try
                        set msgId to "mailid:" & (id of msg as string)
                    end try
                end if
                set msgContent to ""
                set output to output & msgSubject & "|||" & msgSender & "|||" & msgDate & "|||" & msgRead & "|||" & msgFlagged & "|||" & msgContent & "|||" & msgId & linefeed
            end if
        end repeat
        return output
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"  Mail error ({folder_name}): {result.stderr.strip()}")
            return None

        # Each message has 7 fields (subject|sender|date|read|flagged|content|id)
        # joined by 6 '|||' delimiters. Lines with fewer are continuations of a
        # subject/sender that contained a literal newline character.
        _SEPS = 6
        messages = []
        raw_lines = result.stdout.strip().split('\n')
        joined_lines = []
        for raw in raw_lines:
            if joined_lines and joined_lines[-1].count('|||') < _SEPS:
                joined_lines[-1] += ' ' + raw
            else:
                joined_lines.append(raw)
        for line in joined_lines:
            parts = line.split('|||')
            if len(parts) >= _SEPS + 1:
                messages.append({
                    "subject": parts[0].strip(),
                    "sender": parts[1].strip(),
                    "date": parts[2].strip(),
                    "read": parts[3].strip() == "true",
                    "flagged": parts[4].strip() == "true",
                    "preview": parts[5].strip(),
                    "message_id": parts[6].strip(),
                    "folder": folder_name,
                })
        return messages
    except subprocess.TimeoutExpired:
        print(f"  Mail script timed out ({folder_name})")
        return None
    except Exception as e:
        print(f"  Mail error ({folder_name}): {e}")
        return None


def get_mail_folders():
    """Return flat list of top-level mailbox names from Mail.app."""
    script = '''
    tell application "Mail"
        set output to ""
        repeat with mb in mailboxes
            set output to output & name of mb & linefeed
        end repeat
        return output
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    except Exception:
        return []


def get_all_mail_folders():
    """Return all account-level mailboxes as list of (account, folder) tuples.

    Skips system/noise folders and deduplicates by folder name.
    Returns a sorted list of unique folder names for the move menu.
    Falls back to cache if Mail.app is unavailable.
    """
    cache = _load_cache()
    now = time.time()
    cache_key = "all_folders"
    cached = cache.get(cache_key)

    _SKIP = {
        "all mail", "notes", "outbox", "spam", "junk", "junk e-mail",
        "important", "starred", "recovered messages (google)",
        "recovered messages (icloud)",
    }
    script = '''
    tell application "Mail"
        set output to ""
        repeat with acct in accounts
            set aName to name of acct
            repeat with mb in mailboxes of acct
                set output to output & aName & "|" & name of mb & linefeed
            end repeat
        end repeat
        return output
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())

        seen_names = set()
        folders = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if '|' not in line:
                continue
            account, folder = line.split('|', 1)
            account, folder = account.strip(), folder.strip()
            if folder.lower() in _SKIP:
                continue
            if folder not in seen_names:
                seen_names.add(folder)
                folders.append((account, folder))
        # Sort: put iCloud folders first (primary account), then others
        folders.sort(key=lambda t: (0 if t[0] == 'iCloud' else 1, t[1].lower()))

        cache[cache_key] = {"ts": now, "data": folders}
        _save_cache(cache)
        return folders

    except Exception as e:
        print(f"  Mail folders error: {e}")
        if cached and (now - cached["ts"]) < _FOLDER_CACHE_MAX_AGE:
            age_h = int((now - cached["ts"]) / 3600)
            print(f"  Using cached folder list ({age_h}h old)")
            return [tuple(f) for f in cached["data"]]
        return []
