// ── Calendar color overrides (localStorage) ──────────────────────────────────
var CAL_COLOR_OVERRIDE_KEY = 'dashboard-cal-colors';

function getCalColorOverrides() {
    try {
        var s = localStorage.getItem(CAL_COLOR_OVERRIDE_KEY);
        return s ? JSON.parse(s) : {};
    } catch(e) { return {}; }
}

function setCalColorOverride(calName, color) {
    var overrides = getCalColorOverrides();
    overrides[calName] = color;
    try { localStorage.setItem(CAL_COLOR_OVERRIDE_KEY, JSON.stringify(overrides)); } catch(e) {}
}

// getCalColor() is defined in 09-calendar-views.js and already checks overrides.


// Safe getElementById that handles special chars (colons, @, dots, etc.) in IDs.
// Uses attribute selector [id="..."] which requires no escaping.
function _byId(id) {
    try {
        return document.querySelector('[id="' + id.replace(/"/g, '\\"') + '"]');
    } catch(e) { return null; }
}

// ── Calendar select population ─────────────────────────────────────────────────
// Populate all calendar <select> dropdowns in edit forms from CALENDAR_LIST
function populateCalSelects() {
    var cals = (typeof CALENDAR_LIST !== 'undefined') ? CALENDAR_LIST : [];
    document.querySelectorAll('.evt-cal-select').forEach(function(sel) {
        var current = sel.options[0] ? sel.options[0].value : '';
        sel.innerHTML = '';
        var overrides = getCalColorOverrides();
        cals.forEach(function(name) {
            var opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            if (name === current) opt.selected = true;
            sel.appendChild(opt);
        });
        // If current calendar isn't in CALENDAR_LIST, add it
        var found = cals.some(function(n){ return n === current; });
        if (!found && current) {
            var opt = document.createElement('option');
            opt.value = current; opt.textContent = current; opt.selected = true;
            sel.insertBefore(opt, sel.firstChild);
        }
    });
}


// ── Populate a single edit form's calendar select ─────────────────────────────
function populateCalSelect(eid, currentCal) {
    var sel = _byId('edit-cal-' + eid);
    if (!sel) return;
    var cals = (typeof CALENDAR_LIST !== 'undefined') ? CALENDAR_LIST : [];
    var overrides = getCalColorOverrides();
    sel.innerHTML = '';
    cals.forEach(function(name) {
        var opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        if (name === currentCal) opt.selected = true;
        sel.appendChild(opt);
    });
    // Add current if missing
    var found = cals.some(function(n){ return n === currentCal; });
    if (!found && currentCal) {
        var opt = document.createElement('option');
        opt.value = currentCal; opt.textContent = currentCal; opt.selected = true;
        sel.insertBefore(opt, sel.firstChild);
    }
    // Sync swatch color to current cal
    updateCalSwatch(eid);
}

// Update the color swatch button when the selected calendar changes
function updateCalSwatch(eid) {
    var sel = _byId('edit-cal-' + eid);
    var swatch = _byId('edit-swatch-' + eid);
    if (!sel || !swatch) return;
    var calName = sel.value;
    var color = getCalColor(calName);
    swatch.style.background = color;
}


// ── Edit event (day view) ─────────────────────────────────────────────────────
function editEvent(eid, calName) {
    // Close any other open forms first
    document.querySelectorAll('.evt-edit-form').forEach(function(f) {
        if (f.id !== 'edit-' + eid) f.style.display = 'none';
    });
    var form = _byId('edit-' + eid);
    if (form) {
        form.style.display = 'block';
        populateCalSelect(eid, calName || '');
        // Scroll the form into view smoothly
        setTimeout(function() {
            form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 50);
    }
}

function cancelEdit(eid) {
    var form = _byId('edit-' + eid);
    if (form) form.style.display = 'none';
}

function saveEventEdit(eid) {
    var title = _byId('edit-title-' + eid).value.trim();
    var date = _byId('edit-date-' + eid).value;
    var startTime = _byId('edit-start-' + eid).value;
    var endTime = _byId('edit-end-' + eid).value;
    var location = _byId('edit-loc-' + eid).value.trim();
    var calSel = _byId('edit-cal-' + eid);
    var newCal = calSel ? calSel.value : '';

    if (!title) return;
    var start = date + 'T' + startTime;
    var end = date + 'T' + endTime;

    // Fire off to iCal via calhelper URL scheme
    var url = 'calhelper://edit?id=' + encodeURIComponent(eid)
        + '&title=' + encodeURIComponent(title)
        + '&start=' + encodeURIComponent(start)
        + '&end=' + encodeURIComponent(end);
    if (location) url += '&location=' + encodeURIComponent(location);
    if (newCal)   url += '&calendar=' + encodeURIComponent(newCal);

    var iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    setTimeout(function() { iframe.remove(); }, 3000);

    // Update CALENDAR_EVENTS in memory so re-renders show the new values
    if (typeof CALENDAR_EVENTS !== 'undefined') {
        for (var i = 0; i < CALENDAR_EVENTS.length; i++) {
            if (CALENDAR_EVENTS[i].event_id === eid) {
                CALENDAR_EVENTS[i].title    = title;
                CALENDAR_EVENTS[i].start    = date + ' ' + startTime;
                CALENDAR_EVENTS[i].end      = date + ' ' + endTime;
                CALENDAR_EVENTS[i].location = location;
                if (newCal) CALENDAR_EVENTS[i].calendar = newCal;
                break;
            }
        }
    }

    cancelEdit(eid);

    // Re-render the current view so the event moves to its new time/date slot
    if (typeof currentCalView !== 'undefined') {
        if (currentCalView === 'day') {
            if (typeof renderCalDay === 'function') renderCalDay();
        } else if (currentCalView === 'week') {
            if (typeof renderWeekView === 'function') renderWeekView();
        } else if (currentCalView === 'month') {
            if (typeof renderMonthView === 'function') renderMonthView();
        }
    }
}


// ── Color picker ──────────────────────────────────────────────────────────────
var CAL_PALETTE = [
    '#667eea','#e53e3e','#38a169','#d69e2e','#9f7aea',
    '#ed8936','#3182ce','#dd6b20','#319795','#b83280',
    '#2b6cb0','#c05621','#2c7a7b','#6b46c1','#c53030',
    // Extra vivid options
    '#f56565','#48bb78','#4299e1','#ed64a6','#ecc94b',
    '#68d391','#63b3ed','#fc8181','#76e4f7','#b794f4',
    '#f6ad55','#81e6d9','#a0aec0','#1a202c','#ffffff'
];

var _colorPickerEid = null;
var _colorPickerCalName = null;

function openCalColorPicker(eid, swatchBtn) {
    closeCalColorPicker();
    var sel = _byId('edit-cal-' + eid);
    var calName = sel ? sel.value : '';
    _colorPickerEid = eid;
    _colorPickerCalName = calName;

    var overrides = getCalColorOverrides();
    var currentColor = overrides[calName] || getCalColor(calName);

    var picker = document.createElement('div');
    picker.id = 'calColorPicker';
    picker.className = 'cal-color-picker';

    var header = '<div class="cal-color-picker-header">'
        + '<span class="cal-color-picker-title">Color for <strong>' + calName.replace(/</g,'&lt;') + '</strong></span>'
        + '<button class="cal-color-picker-close" onclick="closeCalColorPicker()">&times;</button>'
        + '</div>';

    var swatches = '<div class="cal-color-picker-swatches">';
    CAL_PALETTE.forEach(function(c) {
        var active = c.toLowerCase() === currentColor.toLowerCase() ? ' active' : '';
        swatches += '<button class="cal-color-swatch-opt' + active + '" style="background:' + c + '" '
            + 'onclick="pickCalColor(\'' + c + '\', true)" title="' + c + '"></button>';
    });
    swatches += '</div>';

    var custom = '<div class="cal-color-picker-custom">'
        + '<label class="cal-color-picker-label">Custom</label>'
        + '<input type="color" id="calColorCustom" value="' + currentColor + '" '
        + 'oninput="pickCalColor(this.value, false)">'
        + '<button class="cal-color-picker-apply-btn" onclick="pickCalColor(document.getElementById(\'calColorCustom\').value, true)">Apply</button>'
        + '</div>';

    var reset = '<div class="cal-color-picker-reset">'
        + '<button class="cal-color-picker-reset-btn" onclick="resetCalColor()">Reset to default</button>'
        + '</div>';

    picker.innerHTML = header + swatches + custom + reset;

    // Position near the swatch button
    var rect = swatchBtn.getBoundingClientRect();
    picker.style.top = (rect.bottom + window.scrollY + 6) + 'px';
    picker.style.left = Math.min(rect.left + window.scrollX, window.innerWidth - 240) + 'px';

    document.body.appendChild(picker);

    // Close on outside click
    setTimeout(function() {
        document.addEventListener('mousedown', _colorPickerOutside);
    }, 10);
}

function _colorPickerOutside(e) {
    var picker = document.getElementById('calColorPicker');
    if (picker && !picker.contains(e.target)) {
        closeCalColorPicker();
    }
}

function closeCalColorPicker() {
    var picker = document.getElementById('calColorPicker');
    if (picker) picker.remove();
    document.removeEventListener('mousedown', _colorPickerOutside);
    _colorPickerEid = null;
    _colorPickerCalName = null;
}

function pickCalColor(color, closeAfter) {
    if (!_colorPickerCalName) return;
    setCalColorOverride(_colorPickerCalName, color);

    // Update active state in picker — compare via title attribute (stores the hex)
    document.querySelectorAll('.cal-color-swatch-opt').forEach(function(b) {
        b.classList.toggle('active', b.title.toLowerCase() === color.toLowerCase());
    });

    // Update the swatch button in the edit form
    if (_colorPickerEid) {
        var swatch = _byId('edit-swatch-' + _colorPickerEid);
        if (swatch) swatch.style.background = color;
        // Also sync week/month form swatch if open
        var wkSwatch = document.getElementById('weekEvtSwatch');
        if (wkSwatch) wkSwatch.style.background = color;
    }

    // Sync the custom color input to the picked color
    var customInput = document.getElementById('calColorCustom');
    if (customInput && color.match(/^#[0-9a-f]{6}$/i)) customInput.value = color;

    // Live-update all visible event rows for this calendar
    applyCalColorOverrides();

    if (closeAfter) closeCalColorPicker();
}

function resetCalColor() {
    if (!_colorPickerCalName) return;
    var overrides = getCalColorOverrides();
    delete overrides[_colorPickerCalName];
    try { localStorage.setItem(CAL_COLOR_OVERRIDE_KEY, JSON.stringify(overrides)); } catch(e) {}
    applyCalColorOverrides();
    if (_colorPickerEid) updateCalSwatch(_colorPickerEid);
    closeCalColorPicker();
}

// Apply stored color overrides to all visible evt-row elements
function applyCalColorOverrides() {
    var overrides = getCalColorOverrides();
    document.querySelectorAll('.evt-wrap[data-eid]').forEach(function(row) {
        var calEl = row.querySelector('.evt-cal');
        if (!calEl) return;
        var calName = calEl.textContent.trim();
        var color = overrides[calName];
        if (color) {
            row.style.borderLeftColor = color;
            calEl.style.color = color;
        }
    });
}

// Helper: convert hex to rgb string for comparison
function _hexToRgb(hex) {
    var r = parseInt(hex.slice(1,3),16);
    var g = parseInt(hex.slice(3,5),16);
    var b = parseInt(hex.slice(5,7),16);
    return 'rgb(' + r + ', ' + g + ', ' + b + ')';
}

// Apply overrides on page load
applyCalColorOverrides();


// ── Floating add-event dialog ────────────────────────────────────────────────
function openAddEventDialog(presetDate) {
    var overlay = document.getElementById('addEventOverlay');
    if (!overlay) return;
    // Always default date to today (fresh each open) unless a preset is given
    var dateInput = document.getElementById('eventDate');
    if (dateInput) {
        var now = new Date();
        var todayStr = now.getFullYear() + '-' + String(now.getMonth()+1).padStart(2,'0')
            + '-' + String(now.getDate()).padStart(2,'0');
        dateInput.value = presetDate || todayStr;
    }
    // Reset time fields to reasonable defaults
    var startInput = document.getElementById('eventStart');
    var endInput = document.getElementById('eventEnd');
    if (startInput) startInput.value = '09:00';
    if (endInput) endInput.value = '10:00';
    // Clear previous values
    var titleInput = document.getElementById('eventTitle');
    var locInput = document.getElementById('eventLocation');
    if (titleInput) titleInput.value = '';
    if (locInput) locInput.value = '';

    overlay.style.display = 'flex';
    // Focus the title field after a brief animation delay
    setTimeout(function() { if (titleInput) titleInput.focus(); }, 80);
}

function closeAddEventDialog() {
    var overlay = document.getElementById('addEventOverlay');
    if (overlay) overlay.style.display = 'none';
}

// ── Add event (day view) ─────────────────────────────────────────────────────
function addEvent() {
    var title = document.getElementById('eventTitle').value.trim();
    var date = document.getElementById('eventDate').value;
    var startTime = document.getElementById('eventStart').value;
    var endTime = document.getElementById('eventEnd').value;
    var location = document.getElementById('eventLocation').value.trim();

    if (!title) { document.getElementById('eventTitle').focus(); return; }
    if (!date) { document.getElementById('eventDate').focus(); return; }
    if (!startTime) { document.getElementById('eventStart').focus(); return; }
    if (!endTime) { document.getElementById('eventEnd').focus(); return; }

    var start = date + 'T' + startTime;
    var end = date + 'T' + endTime;

    var url = 'calhelper://add?title=' + encodeURIComponent(title)
        + '&start=' + encodeURIComponent(start)
        + '&end=' + encodeURIComponent(end);
    if (location) url += '&location=' + encodeURIComponent(location);

    var iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    setTimeout(function() { iframe.remove(); }, 3000);

    // Optimistic UI
    var startDt = new Date(date + 'T' + startTime);
    var endDt = new Date(date + 'T' + endTime);
    var timeStr = formatTime(startDt) + ' – ' + formatTime(endDt);
    var evtRow = document.createElement('div');
    evtRow.className = 'evt-row';
    evtRow.innerHTML = '<div class="evt-time">' + timeStr + '</div>'
        + '<div class="evt-detail"><span class="evt-title">' + title.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</span>'
        + '<span class="evt-cal" style="color:#38a169">just added</span>'
        + (location ? '<span class="evt-loc">' + location.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</span>' : '')
        + '</div>';

    var dayCards = document.querySelectorAll('#panel-calendar .day-card');
    var targetCard = null;
    dayCards.forEach(function(card) {
        var label = card.querySelector('.day-label');
        if (label && label.textContent === 'Today') targetCard = card;
    });
    if (!targetCard && dayCards.length > 0) targetCard = dayCards[0];
    if (targetCard) targetCard.appendChild(evtRow);

    // Close the dialog and clear fields
    closeAddEventDialog();
}

function formatTime(dt) {
    var h = dt.getHours();
    var m = dt.getMinutes();
    var ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    return h + ':' + (m < 10 ? '0' : '') + m + ' ' + ampm;
}

// Enter key support for event form
document.querySelectorAll('.add-event-input').forEach(function(input) {
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') addEvent();
    });
});

// Escape key to close the add-event dialog
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        var overlay = document.getElementById('addEventOverlay');
        if (overlay && overlay.style.display !== 'none') {
            closeAddEventDialog();
        }
    }
});


// ── Dashboard refresh ─────────────────────────────────────────────────────────
// Primary implementation is in 13-keyboard-widgets.js (with skeleton overlay).
// This is kept as a thin fallback in case that file hasn't loaded yet.


// ── Delete event ──────────────────────────────────────────────────────────────
function deleteEvent(eid) {
    if (!confirm('Delete this event?')) return;
    var url = 'calhelper://delete?id=' + encodeURIComponent(eid);
    var iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    setTimeout(function() { iframe.remove(); }, 3000);

    // Remove from in-memory data so re-renders don't resurrect it
    if (typeof CALENDAR_EVENTS !== 'undefined') {
        CALENDAR_EVENTS = CALENDAR_EVENTS.filter(function(e) {
            return e.event_id !== eid;
        });
    }

    // Remove all DOM elements for this event (may appear in multiple views)
    document.querySelectorAll('[data-eid="' + eid + '"]').forEach(function(row) {
        row.style.opacity = '0.3';
        row.style.textDecoration = 'line-through';
        setTimeout(function() { row.remove(); }, 1000);
    });
}
