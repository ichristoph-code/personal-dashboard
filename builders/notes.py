"""Build Apple Notes HTML for the dashboard notes tab."""

import json
import re
import time
from datetime import datetime
from html import escape


def _parse_dt(mod_str: str):
    """Parse AppleScript date string to datetime, or None."""
    try:
        s = re.sub(r"^[A-Za-z]+,\s*", "", mod_str)
        s = s.replace(" at ", " ")
        return datetime.strptime(s, "%B %d, %Y %I:%M:%S %p")
    except Exception:
        return None


def _relative_date(mod_str: str) -> str:
    """Convert to relative string like '2h ago' or 'Feb 4, 2025'."""
    dt = _parse_dt(mod_str)
    if not dt:
        return ""
    diff = time.time() - dt.timestamp()
    if diff < 3600:
        mins = int(diff / 60)
        return f"{mins}m ago" if mins > 1 else "just now"
    elif diff < 86400:
        return f"{int(diff / 3600)}h ago"
    elif diff < 7 * 86400:
        return f"{int(diff / 86400)}d ago"
    else:
        return dt.strftime("%b %-d, %Y")


def build_notes_html(folders: list, include_scripts=True) -> str:
    """Generate a two-panel Apple Notes UI: folder+list sidebar, reader pane.

    Args:
        folders: [ {"folder": str, "notes": [{"title", "modified", "body"}, ...]}, ... ]
        include_scripts: if False, omit the inline <script> tags (for AJAX updates).
    """
    if not folders:
        return '<div class="notes-empty">No notes found in Apple Notes.</div>'

    total_notes = sum(len(f.get("notes", [])) for f in folders)
    if total_notes == 0:
        return '<div class="notes-empty">No notes found in Apple Notes.</div>'

    # ── Build flat note list with folder membership for JS ──
    # We'll embed all note data as JSON so the reader pane can render without
    # a server round-trip.
    note_index = []   # [{id, folder, title, modified, rel, body}, ...]
    list_html_parts = []
    first_note_id = None

    for folder_data in folders:
        fname_raw = folder_data.get("folder", "")
        notes = folder_data.get("notes", [])
        if not notes:
            continue

        fname = escape(fname_raw)
        fname_id = re.sub(r"[^a-zA-Z0-9-]", "-", fname_raw)

        list_html_parts.append(
            f'<div class="anotes-group" data-folder-id="{escape(fname_id)}">'
            f'<div class="anotes-group-label">{fname}'
            f'<span class="anotes-group-count">{len(notes)}</span></div>'
        )

        for i, note in enumerate(notes):
            nid = f"{fname_id}-{i}"
            if first_note_id is None:
                first_note_id = nid
            title_raw = note.get("title", "Untitled")
            mod_str = note.get("modified", "")
            body_raw = note.get("body", "")
            rel = _relative_date(mod_str)

            atts = note.get("attachments", 0)
            note_index.append({
                "id": nid,
                "folder": fname_raw,
                "title": title_raw,
                "modified": mod_str,
                "rel": rel,
                "body": body_raw,
                "attachments": atts,
            })

            clip_html = (
                f'<span class="anotes-clip" title="{atts} attachment{"s" if atts != 1 else ""}">📎</span>'
                if atts else ''
            )
            list_html_parts.append(
                f'<div class="anotes-item" id="item-{escape(nid)}"'
                f' data-nid="{escape(nid)}"'
                f' style="display:flex;align-items:center;gap:6px"'
                f' onclick="selectNote(\'{escape(nid)}\')">'
                f'<span class="anotes-drag-handle" title="Drag to reorder"'
                f' style="cursor:grab;font-size:14px;line-height:1;padding:4px 3px;'
                f'opacity:0.5;flex-shrink:0;border-radius:4px;color:#a0aec0;'
                f'display:inline-block">⋮</span>'
                f'<div class="anotes-item-content" style="flex:1;min-width:0">'
                f'<div class="anotes-item-title">{escape(title_raw)}{clip_html}</div>'
                f'<div class="anotes-item-meta">'
                f'<span class="anotes-item-folder">{fname}</span>'
                f'<span class="anotes-item-date">{rel}</span>'
                f'</div>'
                f'</div>'
                f'</div>'
            )

        list_html_parts.append('</div>')  # close anotes-group

    # Serialize note data for JS (body is plain text, safe to JSON-encode)
    note_index_json = json.dumps(note_index, ensure_ascii=False)

    sidebar_html = "\n".join(list_html_parts)

    html = f"""<div class="anotes-shell">

  <!-- Sidebar -->
  <div class="anotes-sidebar">
    <div class="anotes-sidebar-top">
      <div class="anotes-search-wrap">
        <svg class="anotes-search-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input class="anotes-search" id="anotesSearch" type="search"
          placeholder="Search\u2026" oninput="filterNotes(this.value)"
          autocomplete="off" spellcheck="false">
      </div>
      <div class="anotes-sidebar-meta">
        <span class="anotes-count" id="anotesCount">{total_notes} notes</span>
        <button class="anotes-new-btn" onclick="newNote()" title="New note in Apple Notes">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="anotes-list" id="anotesList">
{sidebar_html}
      <div class="anotes-no-results" id="anotesNoResults">No notes match.</div>
    </div>
  </div>

  <!-- Reader pane -->
  <div class="anotes-reader" id="anotesReader">
    <div class="anotes-reader-empty" id="anotesReaderEmpty">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--text-faintest);margin-bottom:10px">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
      <span>Select a note</span>
    </div>
    <div class="anotes-reader-content" id="anotesReaderContent" style="display:none">
      <div class="anotes-reader-header">
        <div class="anotes-reader-title" id="anotesReaderTitle"></div>
        <div class="anotes-reader-submeta" id="anotesReaderSubmeta"></div>
      </div>
      <div class="anotes-reader-body" id="anotesReaderBody"></div>
    </div>
    <div class="anotes-reader-toolbar" id="anotesReaderToolbar" style="display:none">
      <button class="anotes-edit-btn" onclick="editNote()" title="Edit note">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
        Edit
      </button>
      <button class="anotes-open-btn" onclick="openNote()" title="Open in Notes">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
          <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
        Open in Notes
      </button>
      <button class="anotes-delete-btn" onclick="deleteNote()" title="Delete note">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
          <path d="M10 11v6"/><path d="M14 11v6"/>
          <path d="M9 6V4h6v2"/>
        </svg>
        Delete
      </button>
    </div>
  </div>

</div>"""
    if include_scripts:
        html += f"""
<script>
var ANOTES_INDEX = {note_index_json};
var _currentNoteId = null;
</script>"""
    return html
