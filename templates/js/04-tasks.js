// ── Task completion persistence ──
var COMPLETED_TASKS_KEY = 'dashboard-completed-tasks';
var DELETED_TASKS_KEY = 'dashboard-deleted-tasks';
// THINGS_AUTH_TOKEN is injected by dashboard.py as a global variable
var PENDING_TASKS_KEY = 'dashboard-pending-tasks';
var DEADLINE_CHANGES_KEY = 'dashboard-deadline-changes';

// Fire a Things URL scheme action via hidden iframe.
// Keeps the dashboard page intact instead of navigating away.
function _fireThingsUrl(url) {
    var iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    setTimeout(function() { iframe.remove(); }, 3000);
}

function getPendingTasks() {
    try {
        var stored = localStorage.getItem(PENDING_TASKS_KEY);
        if (stored) return JSON.parse(stored);
    } catch(e) {}
    return [];
}

function savePendingTask(task) {
    var pending = getPendingTasks();
    pending.push(task);
    try { localStorage.setItem(PENDING_TASKS_KEY, JSON.stringify(pending)); } catch(e) {}
}

function removePendingTask(tempUuid) {
    var pending = getPendingTasks().filter(function(t) { return t.uuid !== tempUuid; });
    try { localStorage.setItem(PENDING_TASKS_KEY, JSON.stringify(pending)); } catch(e) {}
}

function injectPendingTasks() {
    var pending = getPendingTasks();
    if (!pending.length) return;

    // Filter out tasks older than 24 hours
    var cutoff = Date.now() - 86400000;
    var fresh = pending.filter(function(t) { return t.added > cutoff; });
    if (fresh.length !== pending.length) {
        try { localStorage.setItem(PENDING_TASKS_KEY, JSON.stringify(fresh)); } catch(e) {}
    }

    fresh.forEach(function(task) {
        // Don't re-inject if Things has already picked it up (same title in the DOM)
        var exists = Array.from(document.querySelectorAll('.task-title')).some(function(el) {
            return el.textContent.trim() === task.title;
        });
        if (exists) {
            removePendingTask(task.uuid);
            return;
        }

        var areaId = task.list.replace(/\s+/g, '-').replace(/[^a-z0-9-]/gi, '').toLowerCase();
        var taskList = document.getElementById('area-body-' + areaId)
                    || document.querySelector('#panel-tasks .task-list');
        if (!taskList) return;

        var safeTitle = task.title.replace(/</g,'&lt;').replace(/>/g,'&gt;');
        var safeLabel = task.listLabel.replace(/</g,'&lt;').replace(/>/g,'&gt;');
        var li = document.createElement('li');
        li.className = 'task-item';
        li.dataset.uuid = task.uuid;
        li.draggable = true;
        li.innerHTML = '<span class="task-drag-handle">&#x2807;</span>'
            + '<a class="task-circle" href="things:///show" onclick="completeTask(event,this)"></a>'
            + '<div class="task-content"><span class="task-title">' + safeTitle + '</span>'
            + '<span class="task-project" style="color:var(--green);">' + safeLabel + ' ·  syncing…</span></div>';
        taskList.insertBefore(li, taskList.firstChild);
        taskList.style.maxHeight = taskList.scrollHeight + 'px';
    });
}

// ── Deadline change persistence ──
function getDeadlineChanges() {
    try {
        var stored = localStorage.getItem(DEADLINE_CHANGES_KEY);
        if (stored) return JSON.parse(stored);
    } catch(e) {}
    return {};
}

function saveDeadlineChange(uuid, dateStr) {
    var changes = getDeadlineChanges();
    changes[uuid] = { date: dateStr, ts: Date.now() };
    // Auto-expire after 7 days (only as a safety net; normal cleanup
    // happens in applyDeadlineChanges when the server confirms the change)
    var cutoff = Date.now() - 604800000;
    Object.keys(changes).forEach(function(k) {
        if (changes[k].ts < cutoff) delete changes[k];
    });
    try { localStorage.setItem(DEADLINE_CHANGES_KEY, JSON.stringify(changes)); } catch(e) {}
}

function removeDeadlineChange(uuid) {
    var changes = getDeadlineChanges();
    delete changes[uuid];
    try { localStorage.setItem(DEADLINE_CHANGES_KEY, JSON.stringify(changes)); } catch(e) {}
}

function _deadlineLabelAndClass(dateStr) {
    var dl = new Date(dateStr + 'T00:00:00');
    var today = new Date(); today.setHours(0,0,0,0);
    var delta = Math.round((dl - today) / 86400000);
    var label, cls, bucket, bucketCss;
    if (delta < -1) {
        label = 'Overdue \u00b7 ' + dl.toLocaleDateString('en-US', {month:'short',day:'numeric'});
        cls = 'deadline-overdue'; bucket = 'Overdue'; bucketCss = 'overdue';
    } else if (delta === -1) {
        label = 'Yesterday'; cls = 'deadline-overdue'; bucket = 'Overdue'; bucketCss = 'overdue';
    } else if (delta === 0) {
        label = 'Today'; cls = 'deadline-today'; bucket = 'Today'; bucketCss = 'today';
    } else if (delta === 1) {
        label = 'Tomorrow'; cls = 'deadline-tomorrow'; bucket = 'Tomorrow'; bucketCss = 'tomorrow';
    } else if (delta <= 6) {
        label = dl.toLocaleDateString('en-US', {weekday:'long'}); cls = 'deadline-week';
        bucket = 'This Week'; bucketCss = 'this-week';
    } else if (delta <= 13) {
        label = 'Next ' + dl.toLocaleDateString('en-US', {weekday:'short'}); cls = 'deadline-later';
        bucket = 'Next Week'; bucketCss = 'next-week';
    } else {
        label = dl.toLocaleDateString('en-US', {month:'short',day:'numeric'});
        if (dl.getFullYear() !== today.getFullYear()) {
            label = dl.toLocaleDateString('en-US', {month:'short',day:'numeric',year:'numeric'});
        }
        cls = 'deadline-later'; bucket = 'Later'; bucketCss = 'later';
    }
    return { label: label, cls: cls, bucket: bucket, bucketCss: bucketCss };
}

// ── Due Soon card live updates ──
function _removeDueSoonTask(uuid) {
    var card = document.querySelector('.due-soon-card');
    if (!card) return;
    var item = card.querySelector('.due-item[data-uuid="' + uuid + '"]');
    if (item) item.remove();
    _refreshDueSoonCounts(card);
}

function _updateDueSoonForTask(uuid, dateStr, taskTitle, taskProject) {
    var card = document.querySelector('.due-soon-card');
    if (!card) return;

    // Remove any existing entry for this task
    var existing = card.querySelector('.due-item[data-uuid="' + uuid + '"]');
    if (existing) existing.remove();

    if (!dateStr) {
        _refreshDueSoonCounts(card);
        return;
    }

    var info = _deadlineLabelAndClass(dateStr);

    // Find or create the correct bucket
    var bucket = card.querySelector('.due-bucket-' + info.bucketCss);
    if (!bucket) {
        bucket = document.createElement('div');
        bucket.className = 'due-bucket due-bucket-' + info.bucketCss;
        bucket.innerHTML = '<div class="due-bucket-label">' + info.bucket
            + '<span class="due-bucket-count">0</span></div>'
            + '<ul class="due-list"></ul>';

        // Insert in chronological order
        var order = ['overdue','today','tomorrow','this-week','next-week','later'];
        var insertBefore = null;
        var myIdx = order.indexOf(info.bucketCss);
        for (var i = myIdx + 1; i < order.length; i++) {
            var next = card.querySelector('.due-bucket-' + order[i]);
            if (next) { insertBefore = next; break; }
        }

        // Remove empty state if present
        var empty = card.querySelector('.empty-state');
        if (empty) empty.remove();

        if (insertBefore) {
            card.insertBefore(bucket, insertBefore);
        } else {
            card.appendChild(bucket);
        }
    }

    // Create the due-item
    var list = bucket.querySelector('.due-list');
    var li = document.createElement('li');
    li.className = 'due-item';
    li.dataset.uuid = uuid;
    var safeTitle = taskTitle.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    var projectHtml = taskProject
        ? '<span class="due-project">' + taskProject.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</span>'
        : '';
    li.innerHTML = '<a class="task-circle" href="things:///show?id=' + encodeURIComponent(uuid) + '" title="Open in Things"></a>'
        + '<span class="due-title">' + safeTitle + '</span>'
        + projectHtml
        + '<span class="task-deadline ' + info.cls + '">' + info.label + '</span>';
    list.appendChild(li);

    _refreshDueSoonCounts(card);
}

function _refreshDueSoonCounts(card) {
    if (!card) return;

    // Update per-bucket counts, remove empty buckets
    card.querySelectorAll('.due-bucket').forEach(function(bucket) {
        var count = bucket.querySelectorAll('.due-item').length;
        var countEl = bucket.querySelector('.due-bucket-count');
        if (countEl) countEl.textContent = count;
        if (count === 0) bucket.remove();
    });

    // Update urgent badge (Overdue + Today)
    var overdue = card.querySelectorAll('.due-bucket-overdue .due-item').length;
    var todayCount = card.querySelectorAll('.due-bucket-today .due-item').length;
    var urgent = overdue + todayCount;

    var badge = card.querySelector('.due-soon-badge');
    var h3 = card.querySelector('h3');
    if (urgent > 0) {
        if (badge) {
            badge.textContent = urgent;
        } else if (h3) {
            var span = document.createElement('span');
            span.className = 'due-soon-badge';
            span.textContent = urgent;
            h3.appendChild(document.createTextNode(' '));
            h3.appendChild(span);
        }
    } else if (badge) {
        badge.remove();
    }

    // Show empty state if nothing left
    if (!card.querySelector('.due-item')) {
        if (!card.querySelector('.empty-state')) {
            var p = document.createElement('p');
            p.className = 'empty-state';
            p.textContent = 'No upcoming deadlines';
            card.appendChild(p);
        }
    }
}

function applyDeadlineChanges() {
    var changes = getDeadlineChanges();
    var cutoff = Date.now() - 604800000; // 7-day safety net
    Object.keys(changes).forEach(function(uuid) {
        // Only expire as a safety net after 7 days
        if (changes[uuid].ts < cutoff) {
            removeDeadlineChange(uuid);
            return;
        }

        var dateStr = changes[uuid].date;
        var li = document.querySelector('.task-item[data-uuid="' + uuid + '"]');
        if (!li) return;

        // Check if the server already has this deadline (no need to re-apply)
        var pill = li.querySelector('.task-deadline');
        if (pill && pill.dataset.deadline === dateStr) {
            removeDeadlineChange(uuid);
            return;
        }

        // Re-apply the deadline to the task pill
        var info = _deadlineLabelAndClass(dateStr);

        if (pill) {
            pill.textContent = info.label;
            pill.className = 'task-deadline ' + info.cls;
            pill.dataset.deadline = dateStr;
        } else {
            var dueBtn = li.querySelector('.task-due-btn');
            var newPill = document.createElement('span');
            newPill.className = 'task-deadline ' + info.cls;
            newPill.dataset.deadline = dateStr;
            newPill.textContent = info.label;
            newPill.onclick = function(e) { e.stopPropagation(); openDatePicker(e, uuid); };

            var mainRow = li.querySelector('.task-main-row');
            if (mainRow) {
                if (dueBtn) {
                    mainRow.insertBefore(newPill, dueBtn);
                    dueBtn.remove();
                } else {
                    mainRow.appendChild(newPill);
                }
            }
        }

        // Also update inline edit form
        var editDate = document.getElementById('tedit-date-' + uuid);
        if (editDate) editDate.value = dateStr;

        // Update Due Soon card
        var taskTitle = li.dataset.title || (li.querySelector('.task-title') ? li.querySelector('.task-title').textContent : '');
        var projEl = li.querySelector('.task-project');
        var taskProject = projEl ? projEl.textContent : '';
        _updateDueSoonForTask(uuid, dateStr, taskTitle, taskProject);

        // Re-fire the Things URL so the change is retried if Things missed it
        if (THINGS_AUTH_TOKEN && !uuid.startsWith('temp-')) {
            var retryUrl = 'things:///update?id=' + encodeURIComponent(uuid)
                + '&deadline=' + encodeURIComponent(dateStr)
                + '&auth-token=' + encodeURIComponent(THINGS_AUTH_TOKEN);
            // Use iframe to avoid navigating away; fall back silently
            try {
                var iframe = document.createElement('iframe');
                iframe.style.display = 'none';
                iframe.src = retryUrl;
                document.body.appendChild(iframe);
                setTimeout(function() { iframe.remove(); }, 2000);
            } catch(e) {}
        }
    });
}

function getCompletedTasks() {
    try {
        var stored = localStorage.getItem(COMPLETED_TASKS_KEY);
        if (stored) return JSON.parse(stored);
    } catch(e) {}
    return {};
}

function saveCompletedTask(uuid) {
    var completed = getCompletedTasks();
    completed[uuid] = Date.now();
    // Auto-expire after 24 hours so stale entries don't pile up
    var cutoff = Date.now() - 86400000;
    Object.keys(completed).forEach(function(k) {
        if (completed[k] < cutoff) delete completed[k];
    });
    try { localStorage.setItem(COMPLETED_TASKS_KEY, JSON.stringify(completed)); } catch(e) {}
}

function removeCompletedTask(uuid) {
    var completed = getCompletedTasks();
    delete completed[uuid];
    try { localStorage.setItem(COMPLETED_TASKS_KEY, JSON.stringify(completed)); } catch(e) {}
}

// ── Deleted task persistence ──
function getDeletedTasks() {
    try {
        var stored = localStorage.getItem(DELETED_TASKS_KEY);
        if (stored) return JSON.parse(stored);
    } catch(e) {}
    return {};
}

function saveDeletedTask(uuid) {
    var deleted = getDeletedTasks();
    deleted[uuid] = Date.now();
    // Auto-expire after 24 hours (Things will have processed the deletion by then)
    var cutoff = Date.now() - 86400000;
    Object.keys(deleted).forEach(function(k) {
        if (deleted[k] < cutoff) delete deleted[k];
    });
    try { localStorage.setItem(DELETED_TASKS_KEY, JSON.stringify(deleted)); } catch(e) {}
}

function applyDeletedTasks() {
    var deleted = getDeletedTasks();
    document.querySelectorAll('.task-item[data-uuid]').forEach(function(li) {
        if (deleted[li.dataset.uuid]) {
            li.remove();
        }
    });
}

function applyCompletedTasks() {
    var completed = getCompletedTasks();
    document.querySelectorAll('.task-item[data-uuid]').forEach(function(li) {
        if (completed[li.dataset.uuid]) {
            li.classList.add('completed');
        }
    });
}

function completeTask(event, el) {
    event.preventDefault();
    var li = el.closest('.task-item');
    var uuid = li.dataset.uuid;
    var isCompleted = li.classList.contains('completed');

    if (isCompleted) {
        // Uncheck — remove completed state
        li.classList.remove('completed');
        if (uuid) removeCompletedTask(uuid);
        // Tell Things to reopen the task if it has a real UUID
        if (uuid && !uuid.startsWith('temp-')) {
            var url = 'things:///update?id=' + encodeURIComponent(uuid) + '&completed=false'
                    + (THINGS_AUTH_TOKEN ? '&auth-token=' + encodeURIComponent(THINGS_AUTH_TOKEN) : '');
            _fireThingsUrl(url);
        }
    } else {
        // Check — mark completed
        li.classList.add('completed');
        if (uuid) saveCompletedTask(uuid);
        // Only call Things if this is a real task (not a temp pending one)
        if (uuid && !uuid.startsWith('temp-')) {
            _fireThingsUrl(el.href);
        }
    }
}

// Restore completed/deleted state, re-inject pending tasks, and re-apply deadline changes on page load
applyDeletedTasks();
applyCompletedTasks();
injectPendingTasks();
applyDeadlineChanges();

// ── Sub-tab switching ──
function switchTasksSubtab(tab) {
    document.querySelectorAll('.tasks-subtab').forEach(function(btn) {
        btn.classList.toggle('active', btn.id === 'subtab-' + tab);
    });
    document.querySelectorAll('.tasks-subpanel').forEach(function(panel) {
        panel.style.display = (panel.id === 'subpanel-' + tab) ? '' : 'none';
    });
    try { localStorage.setItem('dashboard-tasks-subtab', tab); } catch(e) {}
}

// Restore last active sub-tab
(function() {
    try {
        var saved = localStorage.getItem('dashboard-tasks-subtab');
        if (saved && document.getElementById('subpanel-' + saved)) {
            switchTasksSubtab(saved);
        }
    } catch(e) {}
})();

// ── Add task ──
function showNewCategoryInput() {
    var listSelect = document.getElementById('newTaskList');
    // Revert select to previous value so "__new__" isn't stuck
    listSelect.value = listSelect.dataset.lastValue || listSelect.options[0].value;

    var wrap = document.getElementById('newCategoryWrap');
    if (!wrap) return;
    wrap.style.display = 'flex';
    var inp = document.getElementById('newCategoryInput');
    if (inp) { inp.value = ''; inp.focus(); }
}

function confirmNewCategory() {
    var inp = document.getElementById('newCategoryInput');
    var listSelect = document.getElementById('newTaskList');
    var name = inp ? inp.value.trim() : '';
    if (!name) { cancelNewCategory(); return; }

    // Insert into dropdown before the separator
    var newOpt = document.createElement('option');
    newOpt.value = name;
    newOpt.textContent = name;
    var sep = listSelect.querySelector('option[disabled]');
    listSelect.insertBefore(newOpt, sep);
    listSelect.value = name;

    document.getElementById('newCategoryWrap').style.display = 'none';
}

function cancelNewCategory() {
    document.getElementById('newCategoryWrap').style.display = 'none';
}

function addTask() {
    var input = document.getElementById('newTaskInput');
    var listSelect = document.getElementById('newTaskList');
    var title = input.value.trim();
    if (!title) return;

    var list = listSelect ? listSelect.value : 'today';
    var listLabel = listSelect ? listSelect.options[listSelect.selectedIndex].text : 'Today';

    // Handle new category creation — show inline input instead of prompt()
    if (list === '__new__') {
        showNewCategoryInput();
        return;
    }

    // Save the current selection for when __new__ reverts
    if (listSelect) listSelect.dataset.lastValue = list;

    // Things URL scheme — add task via hidden iframe
    var thingsUrl = 'things:///add?title=' + encodeURIComponent(title)
            + '&show-quick-entry=false'
            + '&reveal=false'
            + '&list=' + encodeURIComponent(list);

    _fireThingsUrl(thingsUrl);

    // Optimistically add to the matching area group in the UI
    var areaId = list.replace(/\s+/g, '-').replace(/[^a-z0-9-]/gi, '').toLowerCase();
    var taskList = document.getElementById('area-body-' + areaId);
    if (!taskList) {
        taskList = document.querySelector('#panel-tasks .task-list');
    }

    // Generate a temporary UUID so the task can be checked off immediately
    var tempUuid = 'temp-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
    var safeTitle = title.replace(/</g,'&lt;').replace(/>/g,'&gt;');
    var safeLabel = listLabel.replace(/</g,'&lt;').replace(/>/g,'&gt;');

    // Save to localStorage so it survives page reloads until Things picks it up
    savePendingTask({ uuid: tempUuid, title: title, list: list, listLabel: listLabel, added: Date.now() });

    if (taskList) {
        var li = document.createElement('li');
        li.className = 'task-item';
        li.dataset.uuid = tempUuid;
        li.draggable = true;
        li.innerHTML = '<span class="task-drag-handle">&#x2807;</span>'
            + '<a class="task-circle" href="things:///show" onclick="completeTask(event,this)"></a>'
            + '<div class="task-content"><span class="task-title">' + safeTitle + '</span>'
            + '<span class="task-project" style="color:var(--green);">' + safeLabel + ' · syncing…</span></div>';
        taskList.insertBefore(li, taskList.firstChild);
        taskList.style.maxHeight = taskList.scrollHeight + 'px';
    }

    input.value = '';
    input.focus();
}

// ── Inline task edit ──
function openTaskEdit(uuid) {
    // Close any other open edits first
    document.querySelectorAll('.task-edit-form').forEach(function(f) {
        if (f.id !== 'tedit-' + uuid) {
            f.style.display = 'none';
        }
    });
    var form = document.getElementById('tedit-' + uuid);
    if (!form) return;
    var isOpen = form.style.display !== 'none';
    form.style.display = isOpen ? 'none' : 'block';
    if (!isOpen) {
        var inp = document.getElementById('tedit-title-' + uuid);
        if (inp) { inp.focus(); inp.select(); }
    }
}

function saveTaskEdit(uuid) {
    var titleInput = document.getElementById('tedit-title-' + uuid);
    var dateInput  = document.getElementById('tedit-date-' + uuid);
    if (!titleInput) return;

    var newTitle    = titleInput.value.trim();
    var newDeadline = dateInput ? dateInput.value : '';

    if (!newTitle) return;

    // Build Things update URL (fired AFTER DOM updates)
    var url = 'things:///update?id=' + encodeURIComponent(uuid)
            + '&title=' + encodeURIComponent(newTitle);
    if (newDeadline) {
        url += '&deadline=' + encodeURIComponent(newDeadline);
    }
    if (THINGS_AUTH_TOKEN) url += '&auth-token=' + encodeURIComponent(THINGS_AUTH_TOKEN);

    // Update the UI optimistically
    var li = document.querySelector('.task-item[data-uuid="' + uuid + '"]');
    if (li) {
        // Update title display
        var titleSpan = li.querySelector('.task-title');
        if (titleSpan) titleSpan.textContent = newTitle;
        li.dataset.title = newTitle;

        // Update or remove deadline pill
        var deadlinePill = li.querySelector('.task-deadline');
        if (newDeadline) {
            var dl = new Date(newDeadline + 'T00:00:00');
            var formatted = dl.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            if (deadlinePill) {
                deadlinePill.textContent = formatted;
                deadlinePill.dataset.deadline = newDeadline;
            } else {
                // Insert after title
                var meta = li.querySelector('.task-main-row');
                if (meta) {
                    var span = document.createElement('span');
                    span.className = 'task-deadline';
                    span.dataset.deadline = newDeadline;
                    span.textContent = formatted;
                    meta.appendChild(span);
                }
            }
        } else if (deadlinePill) {
            deadlinePill.remove();
        }
    }

    // Persist deadline change + update Due Soon card
    if (newDeadline) {
        saveDeadlineChange(uuid, newDeadline);
        var taskTitle = newTitle;
        var projEl = li ? li.querySelector('.task-project') : null;
        var taskProject = projEl ? projEl.textContent : '';
        _updateDueSoonForTask(uuid, newDeadline, taskTitle, taskProject);
    } else {
        removeDeadlineChange(uuid);
        _removeDueSoonTask(uuid);
    }

    // Close the form
    cancelTaskEdit(uuid);

    // Fire Things URL AFTER all DOM updates and persistence
    _fireThingsUrl(url);
}

function cancelTaskEdit(uuid) {
    var form = document.getElementById('tedit-' + uuid);
    if (form) form.style.display = 'none';
}

// Save on Enter key, cancel on Escape in edit inputs
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.target.classList.contains('task-edit-input')) {
        var form = e.target.closest('.task-edit-form');
        if (form) {
            var id = form.id.replace('tedit-', '');
            saveTaskEdit(id);
        }
    }
    if (e.key === 'Escape' && (e.target.classList.contains('task-edit-input') || e.target.classList.contains('task-edit-date'))) {
        var form = e.target.closest('.task-edit-form');
        if (form) {
            var id = form.id.replace('tedit-', '');
            cancelTaskEdit(id);
        }
    }
});

// ── Double-click to edit tasks (matches calendar dblclick behaviour) ──
document.addEventListener('dblclick', function(e) {
    // Only on the tasks panel
    if (!e.target.closest('#panel-tasks')) return;
    // Ignore dblclicks on buttons, inputs, or inside edit forms
    if (e.target.closest('button, input, select, .task-edit-form, .task-actions')) return;

    var li = e.target.closest('.task-item');
    if (!li) return;
    var uuid = li.dataset.uuid;
    if (!uuid) return;

    e.preventDefault();

    // If this task doesn't have an edit form yet (dynamically added), create one
    _ensureEditForm(li, uuid);

    openTaskEdit(uuid);
});

// Ensure a task-item has an edit form + action buttons (for dynamically-added tasks)
function _ensureEditForm(li, uuid) {
    if (document.getElementById('tedit-' + uuid)) return; // already has form

    var content = li.querySelector('.task-content');
    if (!content) return;

    var currentTitle = '';
    var titleEl = li.querySelector('.task-title');
    if (titleEl) currentTitle = titleEl.textContent.trim();
    var safeTitle = currentTitle.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Add edit form
    var form = document.createElement('div');
    form.className = 'task-edit-form';
    form.id = 'tedit-' + uuid;
    form.style.display = 'none';
    form.innerHTML = '<input class="task-edit-input" id="tedit-title-' + uuid + '" type="text" value="' + safeTitle + '" />'
        + '<input class="task-edit-date" id="tedit-date-' + uuid + '" type="date" value="" />'
        + '<button class="task-edit-save" onclick="saveTaskEdit(\'' + uuid + '\')">Save</button>'
        + '<button class="task-edit-cancel" onclick="cancelTaskEdit(\'' + uuid + '\')">Cancel</button>';
    content.appendChild(form);

    // Add action buttons if missing
    if (!li.querySelector('.task-actions')) {
        var actions = document.createElement('div');
        actions.className = 'task-actions';
        actions.innerHTML = '<button class="task-action-btn task-edit-btn" onclick="openTaskEdit(\'' + uuid + '\')" title="Edit">'
            + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            + '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
            + '<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>'
            + '</svg></button>'
            + '<button class="task-action-btn task-delete-btn" onclick="deleteTask(\'' + uuid + '\', this)" title="Delete">'
            + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            + '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/>'
            + '</svg></button>';
        li.appendChild(actions);
    }

    // Wrap title in task-main-row if not already
    if (!content.querySelector('.task-main-row')) {
        var mainRow = document.createElement('div');
        mainRow.className = 'task-main-row';
        // Move existing task-title and task-project into main row
        var titleSpan = content.querySelector('.task-title');
        var projSpan = content.querySelector('.task-project');
        if (titleSpan) mainRow.appendChild(titleSpan);
        if (projSpan) mainRow.appendChild(projSpan);
        content.insertBefore(mainRow, content.firstChild);
    }
}

// ── Delete task ──
function deleteTask(uuid, btnEl) {
    var li = btnEl ? btnEl.closest('.task-item') : document.querySelector('.task-item[data-uuid="' + uuid + '"]');
    if (!li) return;

    // Persist deletion so the task stays hidden after page reload
    saveDeletedTask(uuid);

    // Visual fade-out
    li.style.transition = 'opacity 0.3s ease, max-height 0.3s ease 0.3s';
    li.style.opacity = '0';
    li.style.overflow = 'hidden';
    setTimeout(function() {
        li.style.maxHeight = li.offsetHeight + 'px';
        setTimeout(function() {
            li.style.maxHeight = '0';
            li.style.padding = '0';
            li.style.margin = '0';
            setTimeout(function() {
                li.remove();
                // Fire Things delete URL after DOM cleanup to avoid
                // navigating away before the removal finishes
                var url = 'things:///update?id=' + encodeURIComponent(uuid) + '&trash=true'
                        + (THINGS_AUTH_TOKEN ? '&auth-token=' + encodeURIComponent(THINGS_AUTH_TOKEN) : '');
                _fireThingsUrl(url);
            }, 300);
        }, 10);
    }, 300);
}

// ── Task notes toggle ──
function toggleTaskNotes(uuid) {
    var notesDiv = document.getElementById('tnotes-' + uuid);
    if (!notesDiv) return;
    var isVisible = notesDiv.style.display !== 'none' && notesDiv.style.display !== '';
    notesDiv.style.display = isVisible ? 'none' : 'block';
    // Toggle active state on the notes button
    var li = document.querySelector('.task-item[data-uuid="' + uuid + '"]');
    if (li) {
        var btn = li.querySelector('.task-notes-btn');
        if (btn) btn.classList.toggle('active', !isVisible);
    }
}

// ── Project area group collapse/expand ──
// ── Area section toggle (Today / Upcoming area groups) ──
function toggleAreaSection(id) {
    var body = document.getElementById('area-body-' + id);
    var chevron = document.getElementById('area-chevron-' + id);
    if (!body) return;
    var isCollapsed = body.classList.contains('area-collapsed');
    if (isCollapsed) {
        body.classList.remove('area-collapsed');
        body.style.maxHeight = '';        // clear inline constraint first
        var h = body.scrollHeight;        // reads true content height
        body.style.maxHeight = '0';       // reset for animation start
        body.offsetHeight;               // force reflow
        body.style.maxHeight = h + 'px'; // CSS transition: 0 → h
        if (chevron) chevron.classList.remove('collapsed');
    } else {
        body.style.maxHeight = body.scrollHeight + 'px';
        body.offsetHeight; // force reflow
        body.classList.add('area-collapsed');
        body.style.maxHeight = '0';
        if (chevron) chevron.classList.add('collapsed');
    }
    try {
        var key = 'dashboard-area-collapsed';
        var state = JSON.parse(localStorage.getItem(key) || '{}');
        if (isCollapsed) { delete state[id]; } else { state[id] = true; }
        localStorage.setItem(key, JSON.stringify(state));
    } catch(e) {}
}

// ── Main section toggle (TODAY / UPCOMING / PROJECTS) ──
function toggleMainSection(id) {
    var body = document.getElementById('main-body-' + id);
    var chevron = document.getElementById('main-chevron-' + id);
    if (!body) return;
    var isCollapsed = body.classList.contains('section-collapsed');
    if (isCollapsed) {
        body.classList.remove('section-collapsed');
        body.style.maxHeight = '';        // clear inline constraint first
        var h = body.scrollHeight;        // reads true content height (no max-height)
        body.style.maxHeight = '0';       // reset for animation start
        body.offsetHeight;               // force reflow (commit the 0 state)
        body.style.maxHeight = h + 'px'; // CSS transition fires: 0 → h
        // Refresh area bodies so their own toggles work on first click
        body.querySelectorAll('.area-body:not(.area-collapsed)').forEach(function(ab) {
            ab.style.maxHeight = '';
            ab.style.maxHeight = ab.scrollHeight + 'px';
        });
        if (chevron) chevron.classList.remove('collapsed');
    } else {
        // Read actual content height for a smooth collapse animation
        body.style.maxHeight = body.scrollHeight + 'px';
        body.offsetHeight; // force reflow
        body.classList.add('section-collapsed');
        body.style.maxHeight = '0';
        if (chevron) chevron.classList.add('collapsed');
    }
    try {
        var key = 'dashboard-main-section-collapsed';
        var state = JSON.parse(localStorage.getItem(key) || '{}');
        if (isCollapsed) { delete state[id]; } else { state[id] = true; }
        localStorage.setItem(key, JSON.stringify(state));
    } catch(e) {}
}

// Restore main section open/closed state from localStorage
(function initMainSections() {
    try {
        var key = 'dashboard-main-section-collapsed';
        var state = JSON.parse(localStorage.getItem(key) || '{}');
        Object.keys(state).forEach(function(id) {
            var body = document.getElementById('main-body-' + id);
            var chevron = document.getElementById('main-chevron-' + id);
            if (body) { body.classList.add('section-collapsed'); body.style.maxHeight = '0'; }
            if (chevron) chevron.classList.add('collapsed');
        });
        // Open sections: don't pre-set maxHeight — the panel may be hidden at
        // init time (scrollHeight = 0), which would incorrectly cap visible content.
        // The collapse branch in toggleMainSection reads scrollHeight at click time.
    } catch(e) {}
})();

function toggleProjectAreaSection(areaGroupId) {
    var slug = areaGroupId.replace('proj-area-', '');
    var body    = document.getElementById('proj-area-body-' + slug);
    var chevron = document.getElementById('area-chevron-' + areaGroupId);
    if (!body) return;
    var isCollapsed = body.classList.contains('area-collapsed');
    if (isCollapsed) {
        body.classList.remove('area-collapsed');
        body.style.maxHeight = '';
        var h = body.scrollHeight;
        body.style.maxHeight = '0';
        body.offsetHeight;
        body.style.maxHeight = h + 'px';
        if (chevron) chevron.classList.remove('collapsed');
    } else {
        body.style.maxHeight = body.scrollHeight + 'px';
        body.offsetHeight;
        body.classList.add('area-collapsed');
        body.style.maxHeight = '0';
        if (chevron) chevron.classList.add('collapsed');
    }
    try {
        var key = 'dashboard-proj-area-collapsed';
        var state = JSON.parse(localStorage.getItem(key) || '{}');
        if (isCollapsed) { delete state[areaGroupId]; } else { state[areaGroupId] = true; }
        localStorage.setItem(key, JSON.stringify(state));
    } catch(e) {}
}

function initProjectAreaSections() {
    try {
        var key = 'dashboard-proj-area-collapsed';
        var state = JSON.parse(localStorage.getItem(key) || '{}');
        Object.keys(state).forEach(function(areaGroupId) {
            var slug = areaGroupId.replace('proj-area-', '');
            var body    = document.getElementById('proj-area-body-' + slug);
            var chevron = document.getElementById('area-chevron-' + areaGroupId);
            if (body) { body.classList.add('area-collapsed'); body.style.maxHeight = '0'; }
            if (chevron) chevron.classList.add('collapsed');
        });
    } catch(e) {}
    // Set maxHeight for all non-collapsed area bodies
    document.querySelectorAll('.project-area-body:not(.area-collapsed)').forEach(function(body) {
        body.style.maxHeight = body.scrollHeight + 'px';
    });
}

// ── New project form ──
var _newProjectArea = '';

function showNewProjectForm(areaName) {
    _newProjectArea = areaName;
    var form = document.getElementById('newProjectForm');
    var label = document.getElementById('newProjectAreaLabel');
    var input = document.getElementById('newProjectTitle');
    if (!form) return;

    // Move form into the correct area body
    var slug = areaName.replace(/\s+/g, '-').replace(/[^a-z0-9-]/gi, '').toLowerCase();
    var areaBody = document.getElementById('proj-area-body-' + slug);
    if (areaBody) {
        areaBody.appendChild(form);
        // Expand the area if collapsed
        if (areaBody.classList.contains('area-collapsed')) {
            var areaGroupId = 'proj-area-' + slug;
            toggleProjectAreaSection(areaGroupId);
        }
    }

    if (label) label.textContent = areaName;
    form.style.display = 'block';
    if (input) { input.value = ''; input.focus(); }

    // Expand parent area body to show form
    if (areaBody) {
        areaBody.style.maxHeight = areaBody.scrollHeight + 200 + 'px';
    }
}

function confirmNewProject() {
    var input = document.getElementById('newProjectTitle');
    var title = input ? input.value.trim() : '';
    if (!title) { cancelNewProject(); return; }

    // Things URL scheme to create a project in a specific area
    // things:///add-project?title=NAME&area=AREA_NAME
    var url = 'things:///add-project?title=' + encodeURIComponent(title);
    if (_newProjectArea && _newProjectArea !== '(No Area)') {
        url += '&area=' + encodeURIComponent(_newProjectArea);
    }
    _fireThingsUrl(url);

    cancelNewProject();
}

function cancelNewProject() {
    var form = document.getElementById('newProjectForm');
    if (form) {
        form.style.display = 'none';
        // Move back to end of subpanel so it's ready to be re-appended
        var panel = document.getElementById('subpanel-projects');
        if (panel) panel.appendChild(form);
    }
    _newProjectArea = '';
}

// ── Project section collapse/expand ──
function toggleProjectSection(projId) {
    var body    = document.getElementById('area-body-' + projId);
    var chevron = document.getElementById('area-chevron-' + projId);
    if (!body) return;
    var isCollapsed = body.classList.contains('area-collapsed');
    if (isCollapsed) {
        body.classList.remove('area-collapsed');
        body.style.maxHeight = '';
        var h = body.scrollHeight;
        body.style.maxHeight = '0';
        body.offsetHeight; // force reflow
        body.style.maxHeight = h + 'px';
        if (chevron) chevron.classList.remove('collapsed');
    } else {
        body.style.maxHeight = body.scrollHeight + 'px';
        body.offsetHeight; // force reflow
        body.classList.add('area-collapsed');
        body.style.maxHeight = '0';
        if (chevron) chevron.classList.add('collapsed');
    }
    try {
        var key = 'dashboard-proj-collapsed';
        var state = JSON.parse(localStorage.getItem(key) || '{}');
        if (isCollapsed) { delete state[projId]; } else { state[projId] = true; }
        localStorage.setItem(key, JSON.stringify(state));
    } catch(e) {}
}

function initProjectSections() {
    try {
        var key = 'dashboard-proj-collapsed';
        var state = JSON.parse(localStorage.getItem(key) || '{}');
        Object.keys(state).forEach(function(projId) {
            var body    = document.getElementById('area-body-' + projId);
            var chevron = document.getElementById('area-chevron-' + projId);
            if (body) { body.classList.add('area-collapsed'); body.style.maxHeight = '0'; }
            if (chevron) chevron.classList.add('collapsed');
        });
    } catch(e) {}
    // Set maxHeight for all non-collapsed project bodies
    document.querySelectorAll('#main-body-projects .area-body:not(.area-collapsed)').forEach(function(body) {
        body.style.maxHeight = body.scrollHeight + 'px';
    });
}

initProjectSections();
initProjectAreaSections();

// ── Date picker popover ──
var _activePopover = null;

function _closeDatePopover() {
    if (_activePopover) {
        _activePopover.remove();
        _activePopover = null;
    }
    document.removeEventListener('click', _closeDatePopoverOutside, true);
    document.removeEventListener('keydown', _closeDatePopoverEsc, true);
}

function _closeDatePopoverOutside(e) {
    if (_activePopover && !_activePopover.contains(e.target)) {
        _closeDatePopover();
    }
}

function _closeDatePopoverEsc(e) {
    if (e.key === 'Escape') _closeDatePopover();
}

function _formatDateISO(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
        + '-' + String(d.getDate()).padStart(2, '0');
}

function _dayLabel(d) {
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function openDatePicker(event, uuid) {
    event.preventDefault();
    _closeDatePopover();

    var trigger = event.target.closest('.task-deadline, .task-due-btn');
    var li = document.querySelector('.task-item[data-uuid="' + uuid + '"]');
    var currentDeadline = '';
    if (li) {
        var pill = li.querySelector('.task-deadline');
        if (pill) currentDeadline = pill.dataset.deadline || '';
    }

    var now = new Date();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1);

    // Next Saturday
    var saturday = new Date(today);
    saturday.setDate(today.getDate() + ((6 - today.getDay() + 7) % 7 || 7));

    // Next Monday
    var monday = new Date(today);
    monday.setDate(today.getDate() + ((1 - today.getDay() + 7) % 7 || 7));

    // +1 week from today
    var nextWeek = new Date(today); nextWeek.setDate(today.getDate() + 7);

    var popover = document.createElement('div');
    popover.className = 'task-date-popover';

    var options = [
        { icon: '📌', label: 'Today',     date: today,    day: '' },
        { icon: '➡️', label: 'Tomorrow',  date: tomorrow, day: _dayLabel(tomorrow) },
        { icon: '🗓', label: 'Saturday',   date: saturday, day: _dayLabel(saturday) },
        { icon: '📅', label: 'Next Monday', date: monday, day: _dayLabel(monday) },
        { icon: '⏳', label: 'In a Week',  date: nextWeek, day: _dayLabel(nextWeek) }
    ];

    var html = '';
    options.forEach(function(opt) {
        var ds = _formatDateISO(opt.date);
        var isCurrent = ds === currentDeadline ? ' style="background:var(--accent-ring)"' : '';
        html += '<button class="date-pick-option"' + isCurrent + ' onclick="setTaskDeadline(\'' + uuid + '\',\'' + ds + '\')">'
            + '<span class="date-pick-icon">' + opt.icon + '</span>'
            + '<span class="date-pick-label">' + opt.label + '</span>'
            + (opt.day ? '<span class="date-pick-day">' + opt.day + '</span>' : '')
            + '</button>';
    });

    // Divider + custom date
    html += '<div class="date-pick-divider"></div>';
    html += '<div class="date-pick-custom">'
        + '<input type="date" id="datePick-custom-' + uuid + '" value="' + (currentDeadline || _formatDateISO(tomorrow)) + '">'
        + '<button onclick="var v=document.getElementById(\'datePick-custom-' + uuid + '\').value;if(v)setTaskDeadline(\'' + uuid + '\',v)">Set</button>'
        + '</div>';

    // Clear option (only if a deadline exists)
    if (currentDeadline) {
        html += '<div class="date-pick-divider"></div>';
        html += '<button class="date-pick-option destructive" onclick="clearTaskDeadline(\'' + uuid + '\')">'
            + '<span class="date-pick-icon">✕</span>'
            + '<span class="date-pick-label">Remove deadline</span>'
            + '</button>';
    }

    popover.innerHTML = html;
    document.body.appendChild(popover);
    _activePopover = popover;

    // Position near trigger
    if (trigger) {
        var rect = trigger.getBoundingClientRect();
        var popW = popover.offsetWidth;
        var popH = popover.offsetHeight;
        var left = rect.left;
        var top = rect.bottom + 6;

        // Keep within viewport
        if (left + popW > window.innerWidth - 12) left = window.innerWidth - popW - 12;
        if (left < 12) left = 12;
        if (top + popH > window.innerHeight - 12) top = rect.top - popH - 6;

        popover.style.left = left + 'px';
        popover.style.top = top + 'px';
    }

    // Close on outside click (delayed to avoid immediate close)
    setTimeout(function() {
        document.addEventListener('click', _closeDatePopoverOutside, true);
        document.addEventListener('keydown', _closeDatePopoverEsc, true);
    }, 50);
}

function setTaskDeadline(uuid, dateStr) {
    _closeDatePopover();

    // Build Things URL (fired AFTER DOM updates)
    var url = 'things:///update?id=' + encodeURIComponent(uuid)
            + '&deadline=' + encodeURIComponent(dateStr);
    if (THINGS_AUTH_TOKEN) url += '&auth-token=' + encodeURIComponent(THINGS_AUTH_TOKEN);

    // Update UI optimistically
    var li = document.querySelector('.task-item[data-uuid="' + uuid + '"]');
    if (!li) return;

    var dl = new Date(dateStr + 'T00:00:00');
    var today = new Date(); today.setHours(0,0,0,0);
    var delta = Math.round((dl - today) / 86400000);

    // Determine label and class
    var label, cls;
    if (delta < -1) {
        label = 'Overdue · ' + dl.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        cls = 'deadline-overdue';
    } else if (delta === -1) {
        label = 'Yesterday'; cls = 'deadline-overdue';
    } else if (delta === 0) {
        label = 'Today'; cls = 'deadline-today';
    } else if (delta === 1) {
        label = 'Tomorrow'; cls = 'deadline-tomorrow';
    } else if (delta <= 6) {
        label = dl.toLocaleDateString('en-US', { weekday: 'long' }); cls = 'deadline-week';
    } else if (delta <= 13) {
        label = 'Next ' + dl.toLocaleDateString('en-US', { weekday: 'short' }); cls = 'deadline-later';
    } else if (dl.getFullYear() === today.getFullYear()) {
        label = dl.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); cls = 'deadline-later';
    } else {
        label = dl.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); cls = 'deadline-later';
    }

    var pill = li.querySelector('.task-deadline');
    var dueBtn = li.querySelector('.task-due-btn');

    if (pill) {
        // Update existing pill
        pill.textContent = label;
        pill.className = 'task-deadline ' + cls;
        pill.dataset.deadline = dateStr;
    } else {
        // Create new pill (replace the + due button)
        var newPill = document.createElement('span');
        newPill.className = 'task-deadline ' + cls;
        newPill.dataset.deadline = dateStr;
        newPill.textContent = label;
        newPill.onclick = function(e) { e.stopPropagation(); openDatePicker(e, uuid); };

        var mainRow = li.querySelector('.task-main-row');
        if (mainRow) {
            if (dueBtn) {
                mainRow.insertBefore(newPill, dueBtn);
                dueBtn.remove();
            } else {
                mainRow.appendChild(newPill);
            }
        }
    }

    // Also update the inline edit form date input if it exists
    var editDate = document.getElementById('tedit-date-' + uuid);
    if (editDate) editDate.value = dateStr;

    // Persist to localStorage so it survives page regeneration
    saveDeadlineChange(uuid, dateStr);

    // Update the Due Soon card
    var taskTitle = li.dataset.title || (li.querySelector('.task-title') ? li.querySelector('.task-title').textContent : '');
    var projEl = li.querySelector('.task-project');
    var taskProject = projEl ? projEl.textContent : '';
    _updateDueSoonForTask(uuid, dateStr, taskTitle, taskProject);

    // Fire Things URL AFTER all DOM updates and persistence
    _fireThingsUrl(url);
}

function clearTaskDeadline(uuid) {
    _closeDatePopover();

    // Build Things URL (fired AFTER DOM updates)
    var url = 'things:///update?id=' + encodeURIComponent(uuid)
            + '&deadline=';
    if (THINGS_AUTH_TOKEN) url += '&auth-token=' + encodeURIComponent(THINGS_AUTH_TOKEN);

    // Remove deadline pill, add back the + due button
    var li = document.querySelector('.task-item[data-uuid="' + uuid + '"]');
    if (!li) return;

    var pill = li.querySelector('.task-deadline');
    if (pill) {
        var btn = document.createElement('button');
        btn.className = 'task-due-btn';
        btn.title = 'Set due date';
        btn.onclick = function(e) { e.stopPropagation(); openDatePicker(e, uuid); };
        btn.innerHTML = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            + 'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            + '<rect x="3" y="4" width="18" height="18" rx="2"/>'
            + '<line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>'
            + '<line x1="3" y1="10" x2="21" y2="10"/>'
            + '</svg>';
        pill.parentNode.insertBefore(btn, pill);
        pill.remove();
    }

    // Clear the inline edit form date input
    var editDate = document.getElementById('tedit-date-' + uuid);
    if (editDate) editDate.value = '';

    // Remove from localStorage and Due Soon card
    removeDeadlineChange(uuid);
    _removeDueSoonTask(uuid);

    // Fire Things URL AFTER all DOM updates
    _fireThingsUrl(url);
}


/* ── Today tab expand "+X more" tasks in place ── */
function expandTodayTasks(btn, e) {
    e.stopPropagation();
    var ul = btn.closest('ul');
    if (!ul) return;
    ul.querySelectorAll('.today-task-item[style*="display:none"]').forEach(function(li) {
        li.style.display = '';
    });
    btn.remove();
}


/* ── Today tab quick-complete ── */
function completeTaskFromToday(btn, e) {
    e.stopPropagation();
    var li = btn.closest('.today-task-item');
    var uuid = li && li.dataset.uuid;
    if (!uuid) return;

    // Build Things URL (same pattern as full Tasks tab)
    var token = window.THINGS_AUTH_TOKEN || '';
    var url = 'things:///update?id=' + encodeURIComponent(uuid) + '&completed=true'
        + (token ? '&auth-token=' + encodeURIComponent(token) : '');

    // Optimistic UI: fade then hide the row
    li.style.transition = 'opacity 0.25s';
    li.style.opacity = '0.25';
    setTimeout(function() { li.style.display = 'none'; }, 280);

    _fireThingsUrl(url);
}

// ── Invalidate stale Today calendar card and next-event pill ──
// If the static HTML was generated on a previous day, hide the outdated events.
(function() {
    function getTodayStr() {
        var now = new Date();
        return now.getFullYear() + '-'
            + String(now.getMonth() + 1).padStart(2, '0') + '-'
            + String(now.getDate()).padStart(2, '0');
    }

    function invalidateStaleContent() {
        var todayStr = getTodayStr();

        // Today calendar card
        var card = document.querySelector('.today-calendar[data-date]');
        if (card && card.getAttribute('data-date') !== todayStr) {
            var body = card.querySelector('.today-card-body');
            if (body) body.innerHTML = '<p class="today-empty">No events today</p>';
            var count = card.querySelector('.today-card-count');
            if (count) count.remove();
        }

        // Next-event pill in the header
        var pill = document.querySelector('.next-event-pill[data-date]');
        if (pill && pill.getAttribute('data-date') !== todayStr) {
            pill.remove();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', invalidateStaleContent);
    } else {
        invalidateStaleContent();
    }
})();
