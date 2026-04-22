"""Apple Notes via AppleScript — folders and notes with body text."""

import json
import subprocess
import time
from pathlib import Path

from . import atomic_write_json

_CACHE_FILE = Path(__file__).parent.parent / ".notes_cache.json"
_CACHE_MAX_AGE = 30 * 60  # 30 minutes


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data):
    atomic_write_json(_CACHE_FILE, data)


def _json_escape(s: str) -> str:
    """Escape a string for safe embedding inside a JSON string literal."""
    return (s
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t"))


def get_apple_notes(force_refresh=False):
    """Return list of folders, each with all notes sorted newest-modified first.

    Returns:
        [ { "folder": str, "notes": [ {"title", "modified", "body"}, ... ] } ]
    Falls back to cache if Notes.app is unavailable.
    """
    cache = _load_cache()
    now = time.time()
    cached = cache.get("notes")
    if not force_refresh and cached and (now - cache.get("ts", 0)) < _CACHE_MAX_AGE:
        return cached

    # Output valid JSON directly from AppleScript to avoid all delimiter issues.
    # Each note is one JSON object; records are separated by a unique sentinel
    # line so Python can split them without any ambiguity.
    script = r"""
tell application "Notes"
    set output to "["
    set isFirst to true
    set folderList to every folder
    repeat with f in folderList
        set fName to name of f
        set noteList to every note of f
        set total to count of noteList
        if total > 0 then
            repeat with i from 1 to total
                set n to item i of noteList
                set nTitle to name of n
                set nMod to modification date of n as string
                set nBody to plaintext of n
                if length of nBody > 20000 then
                    set nBody to text 1 thru 20000 of nBody
                end if
                set attCount to count of attachments of n

                -- JSON-escape backslash and double-quote in each field
                -- (AppleScript has no built-in JSON encoder so we do minimal escaping)
                set nTitle to my jsEscape(nTitle)
                set nBody to my jsEscape(nBody)
                set fNameEsc to my jsEscape(fName)
                set nModEsc to my jsEscape(nMod)

                if isFirst then
                    set isFirst to false
                else
                    set output to output & ","
                end if
                set output to output & "{\"folder\":\"" & fNameEsc & "\",\"title\":\"" & nTitle & "\",\"modified\":\"" & nModEsc & "\",\"body\":\"" & nBody & "\",\"attachments\":" & attCount & "}"
            end repeat
        end if
    end repeat
    set output to output & "]"
    return output
end tell

on jsEscape(s)
    set s to my replaceText(s, "\\", "\\\\")
    set s to my replaceText(s, "\"", "\\\"")
    set s to my replaceText(s, return, "\\n")
    set s to my replaceText(s, linefeed, "\\n")
    set s to my replaceText(s, tab, "\\t")
    return s
end jsEscape

on replaceText(theText, searchStr, replaceStr)
    set AppleScript's text item delimiters to searchStr
    set theItems to text items of theText
    set AppleScript's text item delimiters to replaceStr
    set theText to theItems as string
    set AppleScript's text item delimiters to ""
    return theText
end replaceText
"""

    raw = ""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=45
        )
        raw = result.stdout.strip()
    except subprocess.TimeoutExpired:
        print("  Apple Notes: timed out after 45s — using cache")
    except Exception as e:
        print(f"  Apple Notes: error — {e}")

    if not raw and cached:
        return cached  # fall back to stale cache rather than empty

    # Parse the JSON array AppleScript returned
    notes_flat = []
    try:
        notes_flat = json.loads(raw)
    except Exception:
        if cached:
            return cached
        return []

    # Group by folder, preserving Apple Notes folder order
    folders: dict[str, list] = {}
    for note in notes_flat:
        fname = note.get("folder", "")
        if fname not in folders:
            folders[fname] = []
        folders[fname].append({
            "title": note.get("title", ""),
            "modified": note.get("modified", ""),
            "body": note.get("body", ""),
            "attachments": int(note.get("attachments", 0)),
        })

    def _parse_mod(mod_str: str) -> float:
        """Parse AppleScript date string to a Unix timestamp for sorting."""
        import re
        try:
            s = re.sub(r"^[A-Za-z]+,\s*", "", mod_str)
            s = s.replace(" at ", " ")
            from datetime import datetime
            return datetime.strptime(s, "%B %d, %Y %I:%M:%S %p").timestamp()
        except Exception:
            return 0.0

    result_list = []
    for fname, notes in folders.items():
        # Sort by modification date, newest first
        notes_sorted = sorted(notes, key=lambda n: _parse_mod(n["modified"]), reverse=True)
        result_list.append({"folder": fname, "notes": notes_sorted})

    if result_list:
        _save_cache({"notes": result_list, "ts": now})
    return result_list


def clear_notes_cache():
    """Delete the notes cache file so the next fetch is fresh."""
    try:
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
    except Exception:
        pass



def create_note(title: str, body: str = "", folder: str = "Notes") -> dict:
    """Create a new note in Apple Notes via AppleScript.

    Args:
        title: Note title
        body: Note body (plain text)
        folder: Target folder name (default: "Notes")

    Returns:
        {"ok": True} on success, {"error": "..."} on failure
    """
    # Pass text via argv to avoid escaping issues with newlines/quotes
    script = '''
on run argv
    set noteTitle to item 1 of argv
    set noteBody to item 2 of argv
    set noteFolder to item 3 of argv
    tell application "Notes"
        set targetFolder to folder noteFolder
        make new note at targetFolder with properties {name:noteTitle, body:noteBody}
    end tell
end run
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script, title, body, folder],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "AppleScript failed"}
        clear_notes_cache()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def update_note(title: str, folder: str, new_title: str, new_body: str) -> dict:
    """Update an existing note's title and body in Apple Notes.

    Finds the note by matching title within the specified folder.

    Returns:
        {"ok": True} on success, {"error": "..."} on failure
    """
    # Pass text via argv to avoid escaping issues with newlines/quotes
    script = '''
on run argv
    set noteTitle to item 1 of argv
    set noteFolder to item 2 of argv
    set newTitle to item 3 of argv
    set newBody to item 4 of argv
    tell application "Notes"
        set targetFolder to folder noteFolder
        set matchingNotes to (every note of targetFolder whose name is noteTitle)
        if (count of matchingNotes) > 0 then
            set targetNote to item 1 of matchingNotes
            set name of targetNote to newTitle
            set body of targetNote to newBody
            return "ok"
        else
            return "not found"
        end if
    end tell
end run
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script, title, folder, new_title, new_body],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "AppleScript failed"}
        output = result.stdout.strip()
        if output == "not found":
            return {"error": f"Note '{title}' not found in folder '{folder}'"}
        clear_notes_cache()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def delete_note(title: str, folder: str) -> dict:
    """Delete a note from Apple Notes by title and folder.

    Returns:
        {"ok": True} on success, {"error": "..."} on failure
    """
    # Pass text via argv to avoid escaping issues with newlines/quotes
    script = '''
on run argv
    set noteTitle to item 1 of argv
    set noteFolder to item 2 of argv
    tell application "Notes"
        set targetFolder to folder noteFolder
        set matchingNotes to (every note of targetFolder whose name is noteTitle)
        if (count of matchingNotes) > 0 then
            delete item 1 of matchingNotes
            return "ok"
        else
            return "not found"
        end if
    end tell
end run
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script, title, folder],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "AppleScript failed"}
        output = result.stdout.strip()
        if output == "not found":
            return {"error": f"Note '{title}' not found in folder '{folder}'"}
        clear_notes_cache()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}
