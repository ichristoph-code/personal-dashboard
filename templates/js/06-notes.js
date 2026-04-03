// ── Apple Notes ──
// ANOTES_INDEX and _currentNoteId are injected by the builder as inline <script>

var _notesEditing = false;  // true when the reader is in edit mode

function _getNoteById(id) {
    if (!window.ANOTES_INDEX) return null;
    for (var i = 0; i < ANOTES_INDEX.length; i++) {
        if (ANOTES_INDEX[i].id === id) return ANOTES_INDEX[i];
    }
    return null;
}

// Get unique folder names from the index
function _getNoteFolders() {
    var seen = {};
    var folders = [];
    if (!window.ANOTES_INDEX) return folders;
    ANOTES_INDEX.forEach(function(n) {
        if (n.folder && !seen[n.folder]) {
            seen[n.folder] = true;
            folders.push(n.folder);
        }
    });
    return folders;
}

function selectNote(id) {
    // If we're editing, cancel first
    if (_notesEditing) cancelNoteEdit();

    var note = _getNoteById(id);
    if (!note) return;
    _currentNoteId = id;

    // Highlight active item in sidebar
    document.querySelectorAll('.anotes-item').forEach(function(el) {
        el.classList.toggle('active', el.dataset.nid === id);
    });

    // Populate reader
    var titleEl   = document.getElementById('anotesReaderTitle');
    var submetaEl = document.getElementById('anotesReaderSubmeta');
    var bodyEl    = document.getElementById('anotesReaderBody');
    var contentEl = document.getElementById('anotesReaderContent');
    var emptyEl   = document.getElementById('anotesReaderEmpty');
    var toolbarEl = document.getElementById('anotesReaderToolbar');
    var editFormEl = document.getElementById('anotesEditForm');

    if (titleEl)   titleEl.textContent   = note.title || 'Untitled';
    var clipStr = (note.attachments > 0)
        ? '  \u00b7  \uD83D\uDCCE\u202F' + note.attachments  // 📎 + count
        : '';
    if (submetaEl) submetaEl.textContent = [note.folder, note.rel].filter(Boolean).join('  \u00b7  ') + clipStr;
    if (bodyEl)    bodyEl.textContent    = note.body || '';

    if (emptyEl)   emptyEl.style.display   = 'none';
    if (contentEl) contentEl.style.display = '';
    if (toolbarEl) toolbarEl.style.display = '';
    if (editFormEl) editFormEl.style.display = 'none';

    // Scroll reader to top
    if (contentEl) contentEl.scrollTop = 0;
}

// Open current note in Apple Notes app
function openNote() {
    if (!_currentNoteId) return;
    window.location.href = 'notes://';
}

// ── Delete Note (server-backed) ──
function deleteNote() {
    if (!_currentNoteId) return;
    var note = _getNoteById(_currentNoteId);
    if (!note) return;
    var deleteId = _currentNoteId;

    // Optimistic UI: animate removal from sidebar
    var item = document.getElementById('item-' + deleteId);
    if (item) {
        item.style.transition = 'opacity 0.2s ease, max-height 0.25s ease';
        item.style.overflow = 'hidden';
        item.style.opacity = '0';
        setTimeout(function() {
            item.style.maxHeight = '0';
            item.style.paddingTop = '0';
            item.style.paddingBottom = '0';
        }, 50);
        setTimeout(function() { item.remove(); }, 320);
    }

    // Remove from index
    ANOTES_INDEX = ANOTES_INDEX.filter(function(n) { return n.id !== deleteId; });
    _updateCount();

    // Clear reader
    _currentNoteId = null;
    _showReaderEmpty();

    // Server-side delete via AppleScript
    fetch('/notes-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: note.title, folder: note.folder })
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.error) {
            console.warn('Notes delete error:', data.error);
        }
    }).catch(function(err) {
        console.warn('Notes delete failed:', err);
    });
}

// ── New Note (inline form in sidebar) ──
function newNote() {
    var existing = document.getElementById('anotesNewForm');
    if (existing) {
        // Toggle visibility
        if (existing.style.display === 'none') {
            existing.style.display = '';
            var inp = existing.querySelector('.anotes-new-title');
            if (inp) { inp.focus(); inp.value = ''; }
            var ta = existing.querySelector('.anotes-new-body');
            if (ta) ta.value = '';
        } else {
            existing.style.display = 'none';
        }
        return;
    }

    // Build form
    var folders = _getNoteFolders();
    var folderOptions = '';
    folders.forEach(function(f) {
        var sel = f === 'Notes' ? ' selected' : '';
        folderOptions += '<option value="' + f.replace(/"/g, '&quot;') + '"' + sel + '>' + f + '</option>';
    });
    if (!folderOptions) {
        folderOptions = '<option value="Notes" selected>Notes</option>';
    }

    var form = document.createElement('div');
    form.id = 'anotesNewForm';
    form.className = 'anotes-new-form';
    form.innerHTML =
        '<input class="anotes-new-title" type="text" placeholder="Note title\u2026" autocomplete="off" spellcheck="false">'
        + '<textarea class="anotes-new-body" placeholder="Note body\u2026" rows="3"></textarea>'
        + '<div class="anotes-new-row">'
        + '<select class="anotes-new-folder">' + folderOptions + '</select>'
        + '<div class="anotes-new-actions">'
        + '<button class="anotes-save-btn" onclick="_saveNewNote()">Save</button>'
        + '<button class="anotes-cancel-btn" onclick="_cancelNewNote()">Cancel</button>'
        + '</div>'
        + '</div>';

    var list = document.getElementById('anotesList');
    if (list) {
        list.insertBefore(form, list.firstChild);
    }

    // Focus the title input
    var titleInput = form.querySelector('.anotes-new-title');
    if (titleInput) titleInput.focus();

    // Keyboard: Enter in title → save, Escape → cancel
    form.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey && e.target.classList.contains('anotes-new-title')) {
            e.preventDefault();
            _saveNewNote();
        }
        if (e.key === 'Escape') {
            _cancelNewNote();
        }
    });
}

function _saveNewNote() {
    var form = document.getElementById('anotesNewForm');
    if (!form) return;
    var titleInput = form.querySelector('.anotes-new-title');
    var bodyInput = form.querySelector('.anotes-new-body');
    var folderSelect = form.querySelector('.anotes-new-folder');

    var title = titleInput ? titleInput.value.trim() : '';
    var body = bodyInput ? bodyInput.value.trim() : '';
    var folder = folderSelect ? folderSelect.value : 'Notes';

    if (!title) {
        if (titleInput) {
            titleInput.style.borderColor = 'var(--red)';
            titleInput.focus();
        }
        return;
    }

    // Disable form while saving
    var saveBtn = form.querySelector('.anotes-save-btn');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving\u2026'; }

    fetch('/notes-create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title, body: body, folder: folder })
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.error) {
            alert('Error creating note: ' + data.error);
            if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save'; }
            return;
        }

        // Add to ANOTES_INDEX
        var folderId = folder.replace(/[^a-zA-Z0-9-]/g, '-');
        var nid = folderId + '-new-' + Date.now();
        var newNote = {
            id: nid,
            folder: folder,
            title: title,
            modified: '',
            rel: 'just now',
            body: body
        };
        ANOTES_INDEX.unshift(newNote);

        // Add to sidebar
        _insertNoteSidebarItem(newNote);
        _updateCount();

        // Hide form and select the new note
        form.style.display = 'none';
        if (titleInput) titleInput.value = '';
        if (bodyInput) bodyInput.value = '';
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save'; }

        selectNote(nid);
    }).catch(function(err) {
        alert('Failed to create note: ' + err);
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save'; }
    });
}

function _cancelNewNote() {
    var form = document.getElementById('anotesNewForm');
    if (form) form.style.display = 'none';
}

// Insert a new note item into the sidebar list
function _insertNoteSidebarItem(note) {
    var list = document.getElementById('anotesList');
    if (!list) return;

    var el = document.createElement('div');
    el.className = 'anotes-item';
    el.id = 'item-' + note.id;
    el.dataset.nid = note.id;
    el.style.cssText = 'display:flex;align-items:center;gap:6px';
    el.setAttribute('onclick', "selectNote('" + note.id.replace(/'/g, "\\'") + "')");
    el.innerHTML =
        '<span class="anotes-drag-handle" title="Drag to reorder"'
        + ' style="cursor:grab;font-size:14px;line-height:1;padding:4px 3px;opacity:0.5;flex-shrink:0;border-radius:4px;color:#a0aec0;display:inline-block">\u22ee</span>'
        + '<div class="anotes-item-content" style="flex:1;min-width:0">'
        + '<div class="anotes-item-title">' + _escapeHtml(note.title) + '</div>'
        + '<div class="anotes-item-meta">'
        + '<span class="anotes-item-folder">' + _escapeHtml(note.folder) + '</span>'
        + '<span class="anotes-item-date">' + _escapeHtml(note.rel) + '</span>'
        + '</div></div>';

    // Insert after the new-note form (if present) or at the top
    var newForm = document.getElementById('anotesNewForm');
    if (newForm && newForm.nextSibling) {
        list.insertBefore(el, newForm.nextSibling);
    } else if (newForm) {
        list.appendChild(el);
    } else {
        list.insertBefore(el, list.firstChild);
    }

    // Make it draggable
    el.setAttribute('draggable', 'true');
}

function _escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

// ── Edit Note (inline in reader pane) ──
function editNote() {
    if (!_currentNoteId) return;
    var note = _getNoteById(_currentNoteId);
    if (!note) return;

    _notesEditing = true;

    var contentEl = document.getElementById('anotesReaderContent');
    var toolbarEl = document.getElementById('anotesReaderToolbar');
    var editFormEl = document.getElementById('anotesEditForm');

    // Hide read-mode content, show edit form
    if (contentEl) contentEl.style.display = 'none';
    if (toolbarEl) toolbarEl.style.display = 'none';

    if (!editFormEl) {
        // Create edit form in the reader pane
        editFormEl = document.createElement('div');
        editFormEl.id = 'anotesEditForm';
        editFormEl.className = 'anotes-edit-form';
        var reader = document.getElementById('anotesReader');
        if (reader) reader.insertBefore(editFormEl, reader.firstChild);
    }

    editFormEl.style.display = '';
    editFormEl.innerHTML =
        '<div class="anotes-edit-header">'
        + '<input class="anotes-edit-title-input" id="anotesEditTitle" type="text"'
        + ' value="' + (note.title || '').replace(/"/g, '&quot;') + '"'
        + ' placeholder="Note title\u2026" autocomplete="off" spellcheck="false">'
        + '<div class="anotes-edit-submeta">' + _escapeHtml(note.folder) + '  \u00b7  Editing</div>'
        + '</div>'
        + '<textarea class="anotes-edit-body" id="anotesEditBody" placeholder="Note body\u2026">'
        + _escapeHtml(note.body || '')
        + '</textarea>'
        + '<div class="anotes-edit-actions">'
        + '<button class="anotes-save-btn" id="anotesEditSave" onclick="saveNoteEdit()">Save</button>'
        + '<button class="anotes-cancel-btn" onclick="cancelNoteEdit()">Cancel</button>'
        + '</div>';

    // Focus title
    var titleInput = document.getElementById('anotesEditTitle');
    if (titleInput) { titleInput.focus(); titleInput.select(); }

    // Keyboard shortcuts for edit form
    editFormEl.addEventListener('keydown', function(e) {
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            e.preventDefault();
            saveNoteEdit();
        }
        if (e.key === 'Escape') {
            cancelNoteEdit();
        }
    });
}

function saveNoteEdit() {
    if (!_currentNoteId) return;
    var note = _getNoteById(_currentNoteId);
    if (!note) return;

    var titleInput = document.getElementById('anotesEditTitle');
    var bodyInput = document.getElementById('anotesEditBody');
    var saveBtn = document.getElementById('anotesEditSave');

    var newTitle = titleInput ? titleInput.value.trim() : '';
    var newBody = bodyInput ? bodyInput.value : '';

    if (!newTitle) {
        if (titleInput) {
            titleInput.style.borderColor = 'var(--red)';
            titleInput.focus();
        }
        return;
    }

    // Disable save while in-flight
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving\u2026'; }

    var origTitle = note.title;
    var origFolder = note.folder;

    fetch('/notes-update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: origTitle,
            folder: origFolder,
            new_title: newTitle,
            new_body: newBody
        })
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.error) {
            alert('Error updating note: ' + data.error);
            if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save'; }
            return;
        }

        // Update ANOTES_INDEX
        note.title = newTitle;
        note.body = newBody;
        note.rel = 'just now';

        // Update sidebar item title
        var sidebarItem = document.getElementById('item-' + _currentNoteId);
        if (sidebarItem) {
            var titleEl = sidebarItem.querySelector('.anotes-item-title');
            if (titleEl) titleEl.textContent = newTitle;
            var dateEl = sidebarItem.querySelector('.anotes-item-date');
            if (dateEl) dateEl.textContent = 'just now';
        }

        // Exit edit mode and re-select to refresh reader
        _notesEditing = false;
        selectNote(_currentNoteId);
    }).catch(function(err) {
        alert('Failed to update note: ' + err);
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save'; }
    });
}

function cancelNoteEdit() {
    _notesEditing = false;
    var editFormEl = document.getElementById('anotesEditForm');
    if (editFormEl) editFormEl.style.display = 'none';

    // Restore reader content
    if (_currentNoteId) {
        var contentEl = document.getElementById('anotesReaderContent');
        var toolbarEl = document.getElementById('anotesReaderToolbar');
        if (contentEl) contentEl.style.display = '';
        if (toolbarEl) toolbarEl.style.display = '';
    } else {
        _showReaderEmpty();
    }
}

function _showReaderEmpty() {
    var contentEl = document.getElementById('anotesReaderContent');
    var emptyEl   = document.getElementById('anotesReaderEmpty');
    var toolbarEl = document.getElementById('anotesReaderToolbar');
    var editFormEl = document.getElementById('anotesEditForm');
    if (contentEl) contentEl.style.display = 'none';
    if (emptyEl)   emptyEl.style.display   = '';
    if (toolbarEl) toolbarEl.style.display = 'none';
    if (editFormEl) editFormEl.style.display = 'none';
}

// Live search filter — queries ANOTES_INDEX directly (body + title), not DOM attributes
function filterNotes(query) {
    var q = query.trim().toLowerCase();
    var totalVisible = 0;

    // Build a set of matching note IDs from the index (searches full body text)
    var matchIds = {};
    if (q) {
        ANOTES_INDEX.forEach(function(note) {
            var haystack = (note.title + ' ' + note.body).toLowerCase();
            if (haystack.indexOf(q) !== -1) matchIds[note.id] = true;
        });
    }

    // Also search items not in groups (after drag reorder)
    document.querySelectorAll('.anotes-item').forEach(function(item) {
        var nid = item.dataset.nid || '';
        var match = !q || matchIds[nid];
        item.classList.toggle('hidden', !match);
        if (match) totalVisible++;
    });

    // Hide empty folder groups
    document.querySelectorAll('.anotes-group').forEach(function(group) {
        var items = group.querySelectorAll('.anotes-item');
        var visibleInGroup = 0;
        items.forEach(function(item) {
            if (!item.classList.contains('hidden')) visibleInGroup++;
        });
        group.classList.toggle('hidden', visibleInGroup === 0);
    });

    var countEl   = document.getElementById('anotesCount');
    var noResults = document.getElementById('anotesNoResults');

    if (countEl) {
        countEl.textContent = q
            ? (totalVisible + ' result' + (totalVisible !== 1 ? 's' : ''))
            : (totalVisible + ' notes');
    }
    if (noResults) {
        noResults.classList.toggle('visible', q !== '' && totalVisible === 0);
    }
}

function _updateCount() {
    var visible = document.querySelectorAll('.anotes-item:not(.hidden)').length;
    var countEl = document.getElementById('anotesCount');
    if (countEl) countEl.textContent = visible + ' notes';
}

// Double-click on reader body to enter edit mode
document.addEventListener('dblclick', function(e) {
    if (e.target.closest('.anotes-reader-body') || e.target.closest('.anotes-reader-title')) {
        if (_currentNoteId && !_notesEditing) {
            editNote();
        }
    }
});

// Select first note on load if any exist
(function() {
    var first = document.querySelector('.anotes-item');
    if (first && first.dataset.nid) selectNote(first.dataset.nid);
})();

// ── Drag-to-Reorder Notes in Sidebar ──
var _NOTES_ORDER_KEY = 'dashboard-notes-order';
var _notesDragFromHandle = false;
var _notesDraggedItem = null;

function _initNotesDrag() {
    var list = document.getElementById('anotesList');
    if (!list) return;

    // Restore saved order first
    _applyNotesOrder();

    var items = list.querySelectorAll('.anotes-item');
    if (items.length < 2) return;

    // Track mousedown on drag handle
    list.addEventListener('mousedown', function(e) {
        if (e.target.closest('.anotes-drag-handle')) {
            _notesDragFromHandle = true;
        }
    });
    document.addEventListener('mouseup', function() {
        _notesDragFromHandle = false;
    });

    items.forEach(function(item) {
        item.setAttribute('draggable', 'true');

        item.addEventListener('dragstart', function(e) {
            if (!_notesDragFromHandle) {
                e.preventDefault();
                return;
            }
            _notesDraggedItem = item;
            item.classList.add('anotes-dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', item.dataset.nid);
        });

        item.addEventListener('dragend', function() {
            item.classList.remove('anotes-dragging');
            _notesDraggedItem = null;
            _notesDragFromHandle = false;
            list.querySelectorAll('.anotes-item').forEach(function(el) {
                el.classList.remove('anotes-drag-over');
            });
        });

        item.addEventListener('dragover', function(e) {
            if (!_notesDraggedItem || _notesDraggedItem === item) return;
            // Allow drag across folder groups — just need both to be notes
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            list.querySelectorAll('.anotes-item').forEach(function(el) {
                el.classList.remove('anotes-drag-over');
            });
            item.classList.add('anotes-drag-over');
        });

        item.addEventListener('dragleave', function(e) {
            if (!item.contains(e.relatedTarget)) {
                item.classList.remove('anotes-drag-over');
            }
        });

        item.addEventListener('drop', function(e) {
            e.preventDefault();
            item.classList.remove('anotes-drag-over');
            if (!_notesDraggedItem || _notesDraggedItem === item) return;

            // Get all visible note items as flat array
            var allItems = Array.from(list.querySelectorAll('.anotes-item'));
            var fromIdx = allItems.indexOf(_notesDraggedItem);
            var toIdx = allItems.indexOf(item);

            // Move the dragged item relative to the drop target
            var targetParent = item.parentNode;
            if (fromIdx < toIdx) {
                targetParent.insertBefore(_notesDraggedItem, item.nextSibling);
            } else {
                targetParent.insertBefore(_notesDraggedItem, item);
            }

            _saveNotesOrder();
        });
    });
}

function _saveNotesOrder() {
    var list = document.getElementById('anotesList');
    if (!list) return;
    var order = [];
    list.querySelectorAll('.anotes-item').forEach(function(item) {
        if (item.dataset.nid) order.push(item.dataset.nid);
    });
    try {
        localStorage.setItem(_NOTES_ORDER_KEY, JSON.stringify(order));
    } catch(e) {}
}

function _applyNotesOrder() {
    try {
        var order = JSON.parse(localStorage.getItem(_NOTES_ORDER_KEY) || '[]');
        if (!order.length) return;
        var list = document.getElementById('anotesList');
        if (!list) return;

        // Build map of nid -> item element
        var itemMap = {};
        list.querySelectorAll('.anotes-item').forEach(function(item) {
            if (item.dataset.nid) itemMap[item.dataset.nid] = item;
        });

        // Simple approach: collect all items, detach them, re-insert in order.
        var inserted = {};

        // Remove all note items from their groups temporarily
        Object.keys(itemMap).forEach(function(nid) {
            itemMap[nid].parentNode.removeChild(itemMap[nid]);
        });

        // Now re-insert items in saved order
        order.forEach(function(nid) {
            if (itemMap[nid]) {
                list.appendChild(itemMap[nid]);
                inserted[nid] = true;
            }
        });

        // Append any new items not in saved order
        Object.keys(itemMap).forEach(function(nid) {
            if (!inserted[nid]) {
                list.appendChild(itemMap[nid]);
            }
        });
    } catch(e) {}
}

// Init notes drag on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _initNotesDrag);
} else {
    _initNotesDrag();
}
