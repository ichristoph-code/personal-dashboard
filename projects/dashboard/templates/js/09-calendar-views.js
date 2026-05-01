// ── Calendar Colors (per-calendar name) ──
var CAL_COLOR_PALETTE = [
    '#667eea', '#e53e3e', '#38a169', '#d69e2e', '#9f7aea',
    '#ed8936', '#3182ce', '#dd6b20', '#319795', '#b83280',
    '#2b6cb0', '#c05621', '#2c7a7b', '#6b46c1', '#c53030'
];
var _calColorCache = {};
function getCalColor(calName) {
    // Check user color overrides first
    try {
        var overrides = JSON.parse(localStorage.getItem('dashboard-cal-colors') || '{}');
        if (overrides[calName]) return overrides[calName];
    } catch(e) {}
    if (_calColorCache[calName]) return _calColorCache[calName];
    var hash = 0;
    for (var i = 0; i < calName.length; i++) {
        hash = ((hash << 5) - hash) + calName.charCodeAt(i);
        hash = hash & hash;
    }
    _calColorCache[calName] = CAL_COLOR_PALETTE[Math.abs(hash) % CAL_COLOR_PALETTE.length];
    return _calColorCache[calName];
}

// Convert a hex color (#rrggbb) to an rgba() string with given alpha
function hexToRgba(hex, alpha) {
    var r = parseInt(hex.slice(1,3), 16);
    var g = parseInt(hex.slice(3,5), 16);
    var b = parseInt(hex.slice(5,7), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
}

// Perceived luminance — returns true if color is "light" (needs dark text)
function isLightColor(hex) {
    var r = parseInt(hex.slice(1,3), 16) / 255;
    var g = parseInt(hex.slice(3,5), 16) / 255;
    var b = parseInt(hex.slice(5,7), 16) / 255;
    // sRGB luminance approximation
    return (0.299 * r + 0.587 * g + 0.114 * b) > 0.55;
}

// Darken a hex color by multiplying each channel by a factor (0–1)
function darkenHex(hex, factor) {
    var r = Math.round(parseInt(hex.slice(1,3), 16) * factor);
    var g = Math.round(parseInt(hex.slice(3,5), 16) * factor);
    var b = Math.round(parseInt(hex.slice(5,7), 16) * factor);
    return '#' + [r,g,b].map(function(v){ return ('0'+v.toString(16)).slice(-2); }).join('');
}

// Lighten a hex color by blending toward white by factor (0–1)
function lightenHex(hex, factor) {
    var r = Math.round(parseInt(hex.slice(1,3), 16) + (255 - parseInt(hex.slice(1,3), 16)) * factor);
    var g = Math.round(parseInt(hex.slice(3,5), 16) + (255 - parseInt(hex.slice(3,5), 16)) * factor);
    var b = Math.round(parseInt(hex.slice(5,7), 16) + (255 - parseInt(hex.slice(5,7), 16)) * factor);
    return '#' + [r,g,b].map(function(v){ return ('0'+v.toString(16)).slice(-2); }).join('');
}

// Return a readable text color for a calendar event chip.
// In dark mode: lighten the calendar color (text on dark bg).
// In light mode: darken it aggressively (text on light bg).
function evtTextColor(calColor) {
    var isDark = document.documentElement.classList.contains('dark-mode');
    return isDark ? lightenHex(calColor, 0.55) : darkenHex(calColor, 0.38);
}

// ── Calendar Views ──
var CAL_VIEW_KEY = 'dashboard-cal-view';
var currentCalView = 'day';
var calViewYear, calViewMonth, calViewWeekStart;

function _buildSharedEvtForm() {
    // Build the shared add/edit form once into #calEvtFormContainer
    var container = document.getElementById('calEvtFormContainer');
    if (!container || document.getElementById('weekEvtForm')) return; // already built
    var cals = (typeof CALENDAR_LIST !== 'undefined') ? CALENDAR_LIST : [];
    var calOpts = cals.map(function(c) {
        return '<option value="' + c.replace(/"/g,'&quot;') + '">' + c.replace(/</g,'&lt;') + '</option>';
    }).join('');
    container.innerHTML = '<div class="card week-evt-form" id="weekEvtForm" style="display:none">'
        + '<h3 id="weekEvtFormTitle">Add Event</h3>'
        + '<div class="add-event-form">'
        + '<div class="add-event-row">'
        + '<input type="text" class="add-event-input" id="weekEvtTitle" placeholder="Event title" style="flex:2">'
        + '<input type="text" class="add-event-input" id="weekEvtLoc" placeholder="Location" style="flex:1">'
        + '</div>'
        + '<div class="add-event-row add-event-datetime">'
        + '<input type="date" class="add-event-input" id="weekEvtDate">'
        + '<input type="time" class="add-event-input" id="weekEvtStart" value="09:00">'
        + '<span class="add-event-to">to</span>'
        + '<input type="time" class="add-event-input" id="weekEvtEnd" value="10:00">'
        + '</div>'
        + '<div class="add-event-row" style="gap:6px">'
        + '<select class="add-event-input evt-cal-select" id="weekEvtCal" onchange="weekEvtUpdateSwatch()">' + calOpts + '</select>'
        + '<button class="evt-cal-swatch" id="weekEvtSwatch" onclick="weekEvtOpenColorPicker(this)" title="Change calendar color" style="width:28px;height:28px;flex-shrink:0;border:2px solid var(--border);border-radius:6px;cursor:pointer;padding:0"></button>'
        + '<input type="hidden" id="weekEvtEditId">'
        + '<button class="add-event-btn" id="weekEvtSubmitBtn" onclick="weekEvtSubmit()">Add Event</button>'
        + '<button class="evt-cancel-btn" onclick="weekEvtCancel()">Cancel</button>'
        + '</div></div></div>';
    weekEvtUpdateSwatch();
}

function initCalView() {
    var now = new Date();
    calViewYear = now.getFullYear();
    calViewMonth = now.getMonth();
    // Week start = Sunday of current week
    var d = new Date(now);
    var day = d.getDay(); // 0=Sun
    var diff = d.getDate() - day;
    calViewWeekStart = new Date(d.setDate(diff));
    calViewWeekStart.setHours(0,0,0,0);

    // Build the shared edit form once — persists across view switches
    _buildSharedEvtForm();

    try {
        var saved = localStorage.getItem(CAL_VIEW_KEY);
        if (saved && ['day','week','month','year'].indexOf(saved) !== -1) {
            switchCalView(saved, true);
        }
    } catch(e) {}
}

function switchCalView(view, noSave) {
    currentCalView = view;
    if (!noSave) {
        try { localStorage.setItem(CAL_VIEW_KEY, view); } catch(e) {}
    }
    document.querySelectorAll('.cal-view-btn').forEach(function(btn) {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    var dayView = document.getElementById('calDayView');
    var altView = document.getElementById('calAltView');
    var navBtns = document.querySelector('.cal-nav');
    if (!dayView || !altView) return;

    if (view === 'day') {
        dayView.style.display = '';
        altView.style.display = 'none';
        altView.innerHTML = '';
        if (navBtns) navBtns.style.display = 'none';
    } else {
        dayView.style.display = 'none';
        altView.style.display = '';
        if (navBtns) navBtns.style.display = 'flex';
        if (view === 'week') renderWeekView();
        else if (view === 'month') renderMonthView();
        else if (view === 'year') renderYearView();
    }
}

function goToEvent(eventId) {
    // Switch to calendar tab and day view, then scroll to and highlight the event
    switchTab('calendar');
    if (currentCalView !== 'day') {
        switchCalView('day');
    }
    // Allow DOM to update, then find and scroll to the event
    setTimeout(function() {
        var row = document.querySelector('.evt-wrap[data-eid="' + eventId.replace(/"/g, '\\"') + '"]');
        if (row) {
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            row.style.transition = 'background 0.3s ease, box-shadow 0.3s ease';
            row.style.background = 'var(--accent-bg)';
            row.style.boxShadow = 'inset 3px 0 0 var(--accent)';
            row.style.borderRadius = '6px';
            setTimeout(function() {
                row.style.background = '';
                row.style.boxShadow = '';
                row.style.borderRadius = '';
            }, 2500);
        }
    }, 100);
}

function navigateCal(direction) {
    if (currentCalView === 'week') {
        calViewWeekStart.setDate(calViewWeekStart.getDate() + direction * 7);
        renderWeekView();
    } else if (currentCalView === 'month') {
        calViewMonth += direction;
        if (calViewMonth > 11) { calViewMonth = 0; calViewYear++; }
        if (calViewMonth < 0) { calViewMonth = 11; calViewYear--; }
        renderMonthView();
    } else if (currentCalView === 'year') {
        calViewYear += direction;
        renderYearView();
    }
}

function navigateCalToday() {
    var now = new Date();
    calViewYear = now.getFullYear();
    calViewMonth = now.getMonth();
    var day = now.getDay(); // 0=Sun
    var diff = now.getDate() - day;
    calViewWeekStart = new Date(now);
    calViewWeekStart.setDate(diff);
    calViewWeekStart.setHours(0,0,0,0);
    if (currentCalView === 'week') renderWeekView();
    else if (currentCalView === 'month') renderMonthView();
    else if (currentCalView === 'year') renderYearView();
}

function getEventsForDate(dateStr) {
    if (typeof CALENDAR_EVENTS === 'undefined') return [];
    return CALENDAR_EVENTS.filter(function(evt) {
        var startDate = evt.start.substring(0, 10);
        var endDate = evt.end.substring(0, 10);
        if (evt.all_day && startDate !== endDate) {
            return dateStr >= startDate && dateStr <= endDate;
        }
        return startDate === dateStr;
    });
}

function dateStr(d) {
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}

function renderWeekView() {
    var altView = document.getElementById('calAltView');
    var label = document.getElementById('calNavLabel');
    var today = dateStr(new Date());
    var days = [];
    for (var i = 0; i < 7; i++) {
        var d = new Date(calViewWeekStart);
        d.setDate(d.getDate() + i);
        days.push(d);
    }
    var startLabel = days[0].toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    var endLabel = days[6].toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    if (label) label.textContent = startLabel + ' – ' + endLabel;

    var html = '<div class="cal-week-grid">';
    // Header row
    html += '<div class="cal-week-header">';
    var dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    var wxData = (typeof WEATHER_FORECAST !== 'undefined') ? WEATHER_FORECAST : {};
    for (var i = 0; i < 7; i++) {
        var ds = dateStr(days[i]);
        var isToday = ds === today ? ' cal-today' : '';
        var wx = wxData[ds];
        var wxPill = wx
            ? '<span class="cal-week-wx-pill">'
                + '<span class="cal-week-wx-icon">' + wx.icon + '</span>'
                + '<span class="cal-week-wx-high">' + wx.high + '°</span>'
                + '<span class="cal-week-wx-sep">/</span>'
                + '<span class="cal-week-wx-low">' + wx.low + '°</span>'
              + '</span>'
            : '';
        html += '<div class="cal-week-day-header' + isToday + '">'
            + '<span class="cal-week-day-name">' + dayNames[i] + '</span>'
            + '<span class="cal-week-day-num">' + days[i].getDate() + '</span>'
            + wxPill
            + '</div>';
    }
    html += '</div>';
    // Body
    html += '<div class="cal-week-body">';
    for (var i = 0; i < 7; i++) {
        var ds = dateStr(days[i]);
        var isToday = ds === today ? ' cal-today' : '';
        var evts = getEventsForDate(ds);
        html += '<div class="cal-week-cell' + isToday + '">';
        // Add event button for this day
        html += '<button class="cal-week-add-btn" onclick="weekAddEvent(\'' + ds + '\')" title="Add event">+</button>';
        evts.forEach(function(evt) {
            var time = '';
            if (!evt.all_day) {
                var parts = evt.start.split(' ');
                if (parts.length > 1) {
                    var tp = parts[1].split(':');
                    var h = parseInt(tp[0]); var m = tp[1];
                    var ampm = h >= 12 ? 'p' : 'a';
                    h = h % 12 || 12;
                    time = (m === '00') ? h + ampm + ' ' : h + ':' + m + ampm + ' ';
                }
            }
            var cls = evt.all_day ? 'cal-week-evt all-day' : 'cal-week-evt';
            var calColor = getCalColor(evt.calendar || '');
            var eid = evt.event_id || '';
            var actions = '';
            if (eid) {
                var eidSafe = eid.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                actions = '<span class="cal-week-evt-actions">'
                    + '<button class="cal-week-evt-btn" onclick="event.stopPropagation();weekEditEvent(\'' + eidSafe + '\',\'' + ds + '\')" title="Edit">&#9998;</button>'
                    + '<button class="cal-week-evt-btn cal-week-evt-del" onclick="event.stopPropagation();deleteEvent(\'' + eidSafe + '\');" title="Delete">&times;</button>'
                    + '</span>';
            }
            var wkBgColor = hexToRgba(calColor, evt.all_day ? 0.55 : 0.45);
            var wkTextColor = evtTextColor(calColor);
            var dataAttrs = eid ? ' data-eid="' + eid.replace(/"/g,'&quot;') + '" data-ds="' + ds + '" data-cal="' + (evt.calendar||'').replace(/"/g,'&quot;') + '"' : '';
            html += '<div class="' + cls + '"' + dataAttrs + ' title="' + evt.title.replace(/"/g, '&quot;') + '" style="background:' + wkBgColor + ';color:' + wkTextColor + ';border-left-color:' + calColor + (eid ? ';cursor:pointer' : '') + '">'
                + '<span class="cal-week-evt-time">' + time + '</span>'
                + evt.title.replace(/</g, '&lt;').replace(/>/g, '&gt;')
                + actions
                + '</div>';
        });
        html += '</div>';
    }
    html += '</div></div>';

    // ── Weather Forecast Banner ──
    // Collect forecast data for days that have weather info
    var forecastDays = [];
    if (typeof WEATHER_FORECAST !== 'undefined') {
        // Gather all available forecast dates (not just the 7 visible week days)
        var allForecastDates = Object.keys(WEATHER_FORECAST).sort();
        allForecastDates.forEach(function(ds) {
            var wx = WEATHER_FORECAST[ds];
            if (!wx) return;
            var d = new Date(ds + 'T00:00:00');
            var dayLabel;
            if (ds === today) {
                dayLabel = 'Today';
            } else {
                var tomorrow = new Date();
                tomorrow.setDate(tomorrow.getDate() + 1);
                if (ds === dateStr(tomorrow)) {
                    dayLabel = 'Tomorrow';
                } else {
                    dayLabel = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
                }
            }
            forecastDays.push({
                label: dayLabel,
                icon: wx.icon,
                high: wx.high,
                low: wx.low,
                desc: wx.desc || ''
            });
        });
    }

    if (forecastDays.length > 0) {
        html += '<div class="cal-week-forecast-banner">';
        html += '<h3>Weather Forecast</h3>';
        html += '<div class="cal-week-forecast-row">';
        forecastDays.forEach(function(day) {
            html += '<div class="cal-week-forecast-day">'
                + '<div class="cal-week-forecast-label">' + day.label + '</div>'
                + '<div class="cal-week-forecast-icon">' + day.icon + '</div>'
                + '<div class="cal-week-forecast-temps">'
                + '<span class="forecast-high">' + day.high + '\u00b0</span>'
                + '<span class="forecast-low">' + day.low + '\u00b0</span>'
                + '</div>'
                + '<div class="cal-week-forecast-desc">' + day.desc + '</div>'
                + '</div>';
        });
        html += '</div></div>';
    }

    altView.innerHTML = html;
}

function weekEvtUpdateSwatch() {
    var sel = document.getElementById('weekEvtCal');
    var swatch = document.getElementById('weekEvtSwatch');
    if (!sel || !swatch) return;
    swatch.style.background = getCalColor(sel.value);
}

function weekEvtOpenColorPicker(btn) {
    var sel = document.getElementById('weekEvtCal');
    var eid = document.getElementById('weekEvtEditId').value;
    // Reuse the day-view color picker — it only needs _colorPickerCalName + _colorPickerEid
    if (sel) openCalColorPicker(eid || '__week__', btn);
}

function weekAddEvent(dateStr) {
    var form = document.getElementById('weekEvtForm');
    form.style.display = '';
    document.getElementById('weekEvtFormTitle').textContent = 'Add Event';
    document.getElementById('weekEvtTitle').value = '';
    document.getElementById('weekEvtDate').value = dateStr;
    document.getElementById('weekEvtStart').value = '09:00';
    document.getElementById('weekEvtEnd').value = '10:00';
    document.getElementById('weekEvtLoc').value = '';
    document.getElementById('weekEvtEditId').value = '';
    document.getElementById('weekEvtSubmitBtn').textContent = 'Add Event';
    weekEvtUpdateSwatch();
    form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    document.getElementById('weekEvtTitle').focus();
}

function weekEditEvent(eid, dateStr) {
    // Find the event in CALENDAR_EVENTS
    var evt = null;
    if (typeof CALENDAR_EVENTS !== 'undefined') {
        for (var i = 0; i < CALENDAR_EVENTS.length; i++) {
            if (CALENDAR_EVENTS[i].event_id === eid) { evt = CALENDAR_EVENTS[i]; break; }
        }
    }
    var form = document.getElementById('weekEvtForm');
    form.style.display = '';
    document.getElementById('weekEvtFormTitle').textContent = 'Edit Event';
    document.getElementById('weekEvtTitle').value = evt ? evt.title : '';
    document.getElementById('weekEvtDate').value = evt ? evt.start.substring(0, 10) : dateStr;
    var startTime = '09:00', endTime = '10:00';
    if (evt && !evt.all_day) {
        var sparts = evt.start.split(' ');
        var eparts = evt.end.split(' ');
        if (sparts.length > 1) startTime = sparts[1].substring(0, 5);
        if (eparts.length > 1) endTime = eparts[1].substring(0, 5);
    }
    document.getElementById('weekEvtStart').value = startTime;
    document.getElementById('weekEvtEnd').value = endTime;
    document.getElementById('weekEvtLoc').value = evt ? (evt.location || '') : '';
    document.getElementById('weekEvtEditId').value = eid;
    document.getElementById('weekEvtSubmitBtn').textContent = 'Save';
    // Set calendar select
    var calSel = document.getElementById('weekEvtCal');
    if (calSel && evt && evt.calendar) {
        // Try to select matching option
        var found = false;
        for (var i = 0; i < calSel.options.length; i++) {
            if (calSel.options[i].value === evt.calendar) {
                calSel.selectedIndex = i;
                found = true;
                break;
            }
        }
        // If calendar not in list, add it
        if (!found) {
            var opt = document.createElement('option');
            opt.value = evt.calendar;
            opt.textContent = evt.calendar;
            opt.selected = true;
            calSel.insertBefore(opt, calSel.firstChild);
        }
    }
    weekEvtUpdateSwatch();
    form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    document.getElementById('weekEvtTitle').focus();
}

function weekEvtSubmit() {
    var title = document.getElementById('weekEvtTitle').value.trim();
    var date = document.getElementById('weekEvtDate').value;
    var startTime = document.getElementById('weekEvtStart').value;
    var endTime = document.getElementById('weekEvtEnd').value;
    var location = document.getElementById('weekEvtLoc').value.trim();
    var editId = document.getElementById('weekEvtEditId').value;
    var calSel = document.getElementById('weekEvtCal');
    var newCal = calSel ? calSel.value : '';

    if (!title) { document.getElementById('weekEvtTitle').focus(); return; }

    var start = date + 'T' + startTime;
    var end = date + 'T' + endTime;

    var url;
    if (editId) {
        url = 'calhelper://edit?id=' + encodeURIComponent(editId)
            + '&title=' + encodeURIComponent(title)
            + '&start=' + encodeURIComponent(start)
            + '&end=' + encodeURIComponent(end);
    } else {
        url = 'calhelper://add?title=' + encodeURIComponent(title)
            + '&start=' + encodeURIComponent(start)
            + '&end=' + encodeURIComponent(end);
    }
    if (location) url += '&location=' + encodeURIComponent(location);
    if (newCal)   url += '&calendar=' + encodeURIComponent(newCal);

    var iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    setTimeout(function() { iframe.remove(); }, 3000);

    weekEvtCancel();

    // Update CALENDAR_EVENTS in memory so re-renders reflect the change
    if (typeof CALENDAR_EVENTS !== 'undefined') {
        if (editId) {
            // Edit: find and update the existing entry
            for (var i = 0; i < CALENDAR_EVENTS.length; i++) {
                if (CALENDAR_EVENTS[i].event_id === editId) {
                    CALENDAR_EVENTS[i].title    = title;
                    CALENDAR_EVENTS[i].start    = date + ' ' + startTime;
                    CALENDAR_EVENTS[i].end      = date + ' ' + endTime;
                    CALENDAR_EVENTS[i].location = location;
                    if (newCal) CALENDAR_EVENTS[i].calendar = newCal;
                    break;
                }
            }
        } else {
            // New event: append optimistically
            CALENDAR_EVENTS.push({
                title: title,
                calendar: newCal || 'Calendar',
                start: date + ' ' + startTime,
                end: date + ' ' + endTime,
                all_day: false,
                location: location,
                event_id: ''
            });
        }
    }

    // Re-render the current view so the event appears in the right slot
    setTimeout(function() {
        if (currentCalView === 'week') renderWeekView();
        else if (currentCalView === 'month') renderMonthView();
        else if (currentCalView === 'day' && typeof renderCalDay === 'function') renderCalDay();
    }, 150);
}

function weekEvtCancel() {
    var form = document.getElementById('weekEvtForm');
    if (form) form.style.display = 'none';
}

function renderMonthView() {
    var altView = document.getElementById('calAltView');
    var label = document.getElementById('calNavLabel');
    var today = dateStr(new Date());
    var monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    if (label) label.textContent = monthNames[calViewMonth] + ' ' + calViewYear;

    var firstDay = new Date(calViewYear, calViewMonth, 1);
    var lastDay = new Date(calViewYear, calViewMonth + 1, 0);
    // Start on Monday
    var startOffset = firstDay.getDay(); // 0=Sun
    var totalDays = lastDay.getDate();
    var weeks = Math.ceil((startOffset + totalDays) / 7);

    var html = '<div class="cal-month-grid">';
    // Header
    html += '<div class="cal-month-header">';
    ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].forEach(function(n) {
        html += '<div class="cal-month-day-name">' + n + '</div>';
    });
    html += '</div>';
    // Days — render ALL events; dynamic trimming happens post-render
    html += '<div class="cal-month-body">';
    var dayNum = 1 - startOffset;
    for (var w = 0; w < weeks; w++) {
        html += '<div class="cal-month-row">';
        for (var d = 0; d < 7; d++) {
            var currentDate = new Date(calViewYear, calViewMonth, dayNum);
            var ds = dateStr(currentDate);
            var inMonth = dayNum >= 1 && dayNum <= totalDays;
            var isToday = ds === today ? ' cal-today' : '';
            var outsideClass = inMonth ? '' : ' cal-outside';
            var evts = getEventsForDate(ds);
            html += '<div class="cal-month-cell' + isToday + outsideClass + '">';
            html += '<div class="cal-month-cell-num">' + currentDate.getDate() + '</div>';
            if (evts.length > 0 && inMonth) {
                // Sort: all-day first, then by start time
                evts.sort(function(a, b) {
                    if (a.all_day && !b.all_day) return -1;
                    if (!a.all_day && b.all_day) return 1;
                    return a.start < b.start ? -1 : 1;
                });
                evts.forEach(function(evt, idx) {
                    var color = getCalColor(evt.calendar || '');
                    var safeTitle = evt.title.replace(/</g,'&lt;').replace(/>/g,'&gt;');
                    var timePrefix = '';
                    if (!evt.all_day && evt.start.length > 10) {
                        var tp = evt.start.split(' ')[1].split(':');
                        var h = parseInt(tp[0]);
                        var m = tp[1];
                        var ampm = h >= 12 ? 'p' : 'a';
                        h = h % 12 || 12;
                        var timeTxt = (m === '00') ? h + ampm : h + ':' + m + ampm;
                        timePrefix = '<span class="cal-month-evt-time">' + timeTxt + '</span>';
                    }
                    var allDayClass = evt.all_day ? ' all-day' : '';
                    var bgAlpha = evt.all_day ? 0.55 : 0.45;
                    var bgColor = hexToRgba(color, bgAlpha);
                    var textColor = evtTextColor(color);
                    var mDataAttrs = evt.event_id
                        ? ' data-eid="' + evt.event_id.replace(/"/g,'&quot;') + '" data-ds="' + ds + '" data-cal="' + (evt.calendar||'').replace(/"/g,'&quot;') + '"'
                        : '';
                    html += '<div class="cal-month-evt' + allDayClass + '" data-mi="' + idx
                        + '"' + mDataAttrs
                        + ' style="background:' + bgColor + ';color:' + textColor + ';--evt-color:' + color + (evt.event_id ? ';cursor:pointer' : '') + '" title="' + safeTitle + '">'
                        + timePrefix + safeTitle + '</div>';
                });
                // Placeholder "+N more" filled in by JS after render
                html += '<div class="cal-month-more" style="display:none"></div>';
            }
            html += '</div>';
            dayNum++;
        }
        html += '</div>';
    }
    html += '</div></div>';
    altView.innerHTML = html;

    // ── Post-render: trim each cell to fit available height ──
    requestAnimationFrame(function() {
        altView.querySelectorAll('.cal-month-cell').forEach(function(cell) {
            var chips = Array.from(cell.querySelectorAll('.cal-month-evt'));
            if (chips.length === 0) return;

            var morePill = cell.querySelector('.cal-month-more');
            var cellH = cell.clientHeight;
            var numEl = cell.querySelector('.cal-month-cell-num');
            var numH = numEl ? numEl.offsetHeight + (parseInt(getComputedStyle(numEl).marginBottom) || 3) : 20;
            // Reserve ~14px for the "+N more" pill when overflow exists
            var MORE_H = 14;
            var available = cellH - numH - 4; // 4px bottom padding buffer

            var used = 0;
            var lastVisible = -1;
            for (var i = 0; i < chips.length; i++) {
                // Check if this chip + possible overflow pill fits
                var chipH = chips[i].offsetHeight + 2; // 2px margin-bottom
                var needed = chipH + (i < chips.length - 1 ? MORE_H : 0);
                if (used + needed <= available) {
                    used += chipH;
                    lastVisible = i;
                } else {
                    break;
                }
            }

            var overflow = chips.length - (lastVisible + 1);
            // Hide chips beyond lastVisible
            for (var i = lastVisible + 1; i < chips.length; i++) {
                chips[i].style.display = 'none';
            }
            // Show/update "+N more" pill
            if (morePill) {
                if (overflow > 0) {
                    morePill.textContent = '+' + overflow + ' more';
                    morePill.style.display = '';
                } else {
                    morePill.style.display = 'none';
                }
            }
        });
    });
}

function renderYearView() {
    var altView = document.getElementById('calAltView');
    var label = document.getElementById('calNavLabel');
    var today = dateStr(new Date());
    if (label) label.textContent = calViewYear;

    var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var html = '<div class="cal-year-grid">';
    for (var m = 0; m < 12; m++) {
        html += '<div class="cal-year-month" onclick="calViewMonth=' + m + ';switchCalView(\'month\')">';
        html += '<div class="cal-year-month-name">' + monthNames[m] + '</div>';
        html += '<div class="cal-year-mini">';
        // Mini month grid
        var firstDay = new Date(calViewYear, m, 1);
        var lastDay = new Date(calViewYear, m + 1, 0);
        var startOffset = firstDay.getDay(); // 0=Sun
        var totalDays = lastDay.getDate();
        var dayNum = 1 - startOffset;
        var weeks = Math.ceil((startOffset + totalDays) / 7);
        for (var w = 0; w < weeks; w++) {
            html += '<div class="cal-year-row">';
            for (var d = 0; d < 7; d++) {
                var currentDate = new Date(calViewYear, m, dayNum);
                var ds = dateStr(currentDate);
                var inMonth = dayNum >= 1 && dayNum <= totalDays;
                var isToday = ds === today ? ' cal-today' : '';
                var evts = inMonth ? getEventsForDate(ds) : [];
                var evtClass = '';
                var isVacation = evts.some(function(e) {
                    return e.calendar === "Ian's Vacation" && e.all_day;
                });
                if (evts.length > 0) evtClass = ' has-events';
                if (evts.length >= 3) evtClass = ' has-many-events';
                if (isVacation) evtClass += ' cal-vacation';
                if (!inMonth) evtClass = ' cal-outside';
                var yearData = (inMonth && evts.length > 0)
                    ? ' data-month="' + m + '" style="cursor:pointer"'
                    : '';
                html += '<div class="cal-year-cell' + isToday + evtClass + '"' + yearData + '>'
                    + (inMonth ? dayNum : '') + '</div>';
                dayNum++;
            }
            html += '</div>';
        }
        html += '</div></div>';
    }
    html += '</div>';
    altView.innerHTML = html;
}

// ── renderCalDay: re-render the day view from CALENDAR_EVENTS ───────────────
// Called after an edit so the event moves to its new date/time slot without
// needing a full dashboard refresh. Mirrors the logic in builders/calendar.py.
function renderCalDay() {
    var dayView = document.getElementById('calDayView');
    if (!dayView || typeof CALENDAR_EVENTS === 'undefined') return;

    var now = new Date();
    var todayStr = dateStr(now);
    var tomorrowDate = new Date(now); tomorrowDate.setDate(tomorrowDate.getDate() + 1);
    var tomorrowStr = dateStr(tomorrowDate);
    var cutoffDate = new Date(now); cutoffDate.setDate(cutoffDate.getDate() + 14);
    var cutoffStr = dateStr(cutoffDate);

    // Expand multi-day all-day events onto each day they span
    var expanded = [];
    CALENDAR_EVENTS.forEach(function(evt) {
        var startDate = evt.start.substring(0, 10);
        var endDate   = evt.end.substring(0, 10);
        if (evt.all_day && startDate !== endDate) {
            var cur = new Date(startDate + 'T00:00:00');
            var end = new Date(endDate   + 'T00:00:00');
            var dayNum = 0;
            var total = Math.round((end - cur) / 86400000) + 1;
            while (cur <= end) {
                dayNum++;
                var copy = Object.assign({}, evt);
                copy._display_date = dateStr(cur);
                if (total > 1) copy._span_label = 'Day ' + dayNum + ' of ' + total;
                expanded.push(copy);
                cur.setDate(cur.getDate() + 1);
            }
        } else {
            var copy = Object.assign({}, evt);
            copy._display_date = startDate;
            expanded.push(copy);
        }
    });

    // Group by display date
    var byDate = {};
    expanded.forEach(function(evt) {
        var d = evt._display_date;
        if (!byDate[d]) byDate[d] = [];
        byDate[d].push(evt);
    });

    // Sort events within each day: all-day first, then by start time
    Object.keys(byDate).forEach(function(d) {
        byDate[d].sort(function(a, b) {
            if (a.all_day && !b.all_day) return -1;
            if (!a.all_day && b.all_day) return 1;
            return a.start < b.start ? -1 : a.start > b.start ? 1 : 0;
        });
    });

    // Collect all dates that currently have day cards rendered (preserve structure)
    var existingCards = dayView.querySelectorAll('.day-card');
    var allDates = [];
    existingCards.forEach(function(card) {
        var d = card.dataset.date;
        if (d) allDates.push(d);
    });
    // Also include any new dates from edited events
    Object.keys(byDate).forEach(function(d) {
        if (d <= cutoffStr && allDates.indexOf(d) === -1) allDates.push(d);
    });
    allDates.sort();

    // Rebuild each day card in place
    allDates.forEach(function(ds) {
        var card = dayView.querySelector('.day-card[data-date="' + ds + '"]');
        if (!card) return; // don't create new cards (weather data isn't available in JS)

        // Preserve the header (day label + weather pill)
        var header = card.querySelector('.day-header');
        var headerHtml = header ? header.outerHTML : '';

        var evts = byDate[ds] || [];
        var evtHtml = '';
        if (evts.length === 0) {
            evtHtml = '<p class="evt-none">No events</p>';
        }
        evts.forEach(function(evt) {
            var eid = evt.event_id || '';
            var canEdit = eid && !evt._span_label;
            var color = getCalColor(evt.calendar || '');

            // Format time string
            var timeStr = '';
            if (evt.all_day) {
                timeStr = evt._span_label ? 'All day &middot; ' + evt._span_label : 'All day';
            } else {
                try {
                    var s = new Date(evt.start.replace(' ', 'T'));
                    var e = new Date(evt.end.replace(' ', 'T'));
                    timeStr = formatTime(s) + ' &ndash; ' + formatTime(e);
                } catch(err) { timeStr = evt.start.substring(11, 16); }
            }

            var locHtml = evt.location
                ? '<span class="evt-loc">' + _esc(evt.location) + '</span>'
                : '';

            var actionsHtml = '';
            var editFormHtml = '';
            if (canEdit) {
                var eidSafe = eid.replace(/'/g, "\\'");
                var calSafe = (evt.calendar || '').replace(/'/g, "\\'");
                actionsHtml = '<span class="evt-actions">'
                    + '<button class="evt-edit-btn" onclick="editEvent(\'' + eidSafe + '\',\'' + calSafe + '\')" title="Edit">'
                    + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>'
                    + '</button>'
                    + '<button class="evt-del-btn" onclick="deleteEvent(\'' + eidSafe + '\')" title="Delete">'
                    + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
                    + '</button></span>';

                var startVal = evt.start.replace(' ', 'T');
                var endVal   = evt.end.replace(' ', 'T');
                var startDate = evt.start.substring(0, 10);
                var startTime = startVal.length > 11 ? startVal.substring(11, 16) : '09:00';
                var endTime   = endVal.length   > 11 ? endVal.substring(11, 16)   : '10:00';
                var calEsc = _esc(evt.calendar || '');

                editFormHtml = '<div class="evt-edit-form" id="edit-' + _esc(eid) + '" style="display:none">'
                    + '<div class="add-event-row">'
                    + '<input type="text" class="add-event-input" value="' + _esc(evt.title) + '" id="edit-title-' + _esc(eid) + '" placeholder="Title" style="flex:2">'
                    + '<input type="text" class="add-event-input" value="' + _esc(evt.location || '') + '" id="edit-loc-' + _esc(eid) + '" placeholder="Location" style="flex:1">'
                    + '</div>'
                    + '<div class="add-event-row add-event-datetime" style="margin-top:4px">'
                    + '<input type="date" class="add-event-input" value="' + startDate + '" id="edit-date-' + _esc(eid) + '">'
                    + '<input type="time" class="add-event-input" value="' + startTime + '" id="edit-start-' + _esc(eid) + '">'
                    + '<span class="add-event-to">to</span>'
                    + '<input type="time" class="add-event-input" value="' + endTime + '" id="edit-end-' + _esc(eid) + '">'
                    + '</div>'
                    + '<div class="add-event-row" style="margin-top:4px;gap:6px">'
                    + '<select class="add-event-input evt-cal-select" id="edit-cal-' + _esc(eid) + '" onchange="updateCalSwatch(\'' + eidSafe + '\')">'
                    + '<option value="' + calEsc + '" selected>' + calEsc + '</option>'
                    + '</select>'
                    + '<button class="evt-cal-swatch" id="edit-swatch-' + _esc(eid) + '" onclick="openCalColorPicker(\'' + eidSafe + '\',this)" title="Change calendar color" style="background:' + color + ';width:28px;height:28px;flex-shrink:0;border:2px solid var(--border);border-radius:6px;cursor:pointer;padding:0"></button>'
                    + '<button class="add-event-btn" onclick="saveEventEdit(\'' + eidSafe + '\')">Save</button>'
                    + '<button class="evt-cancel-btn" onclick="cancelEdit(\'' + eidSafe + '\')">Cancel</button>'
                    + '</div></div>';
            }

            var rowCursor = canEdit ? 'cursor:pointer' : 'cursor:default';
            var calEscAttr = _esc(evt.calendar || '');
            evtHtml +=
                '<div class="evt-wrap" data-eid="' + _esc(eid) + '" data-cal="' + calEscAttr + '" style="border-left:3px solid ' + color + ';padding-left:10px">'
                + '<div class="evt-row" style="' + rowCursor + '">'
                + '<div class="evt-time">' + timeStr + '</div>'
                + '<div class="evt-detail"><span class="evt-title">' + _esc(evt.title) + '</span>'
                + '<span class="evt-cal" style="color:' + color + '">' + _esc(evt.calendar || '') + '</span>'
                + actionsHtml + locHtml + '</div>'
                + '</div>'
                + editFormHtml
                + '</div>';
        });

        card.innerHTML = headerHtml + evtHtml;
    });

    // Re-apply calendar color overrides
    if (typeof applyCalColorOverrides === 'function') applyCalColorOverrides();
}

// HTML-escape helper for renderCalDay
function _esc(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

initCalView();

// ── Single delegated dblclick listener for all calendar views ──────────────
// Handles day view (.evt-row), week/month chips (.cal-week-evt, .cal-month-evt),
// and year view day cells (.cal-year-cell). Uses data attributes to avoid
// inline onclick interference and text-selection race conditions.
document.addEventListener('dblclick', function(e) {
    // Ignore dblclicks on buttons (edit/delete action buttons)
    if (e.target.closest('button')) return;

    // ── Day view: .evt-row inside .evt-wrap[data-eid] ──
    var evtRow = e.target.closest('.evt-row');
    if (evtRow) {
        var wrap = evtRow.closest('.evt-wrap[data-eid]');
        if (wrap) {
            var eid = wrap.dataset.eid;
            var cal = wrap.dataset.cal || '';
            if (eid) { e.preventDefault(); editEvent(eid, cal); }
        }
        return;
    }

    // ── Week / Month view chips ──
    var chip = e.target.closest('.cal-week-evt[data-eid], .cal-month-evt[data-eid]');
    if (chip) {
        var eid = chip.dataset.eid;
        var ds  = chip.dataset.ds || '';
        if (eid) { e.preventDefault(); weekEditEvent(eid, ds); }
        return;
    }

    // ── Year view: day cell with data-month ──
    var cell = e.target.closest('.cal-year-cell[data-month]');
    if (cell) {
        e.preventDefault();
        calViewMonth = parseInt(cell.dataset.month);
        switchCalView('month');
    }
});
