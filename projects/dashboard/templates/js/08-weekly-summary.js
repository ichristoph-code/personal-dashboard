// ── Weekly Summary / Productivity Stats ──
function _datStr(d) {
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}

function renderWeeklySummary() {
    var container = document.getElementById('weeklySummary');
    if (!container) return;

    // Tasks completed this week (from localStorage)
    var completed = getCompletedTasks();
    var now = Date.now();
    var weekAgo = now - 7 * 86400000;
    var tasksCompletedThisWeek = 0;
    Object.keys(completed).forEach(function(k) {
        if (completed[k] >= weekAgo) tasksCompletedThisWeek++;
    });

    // Habits: calculate streak and weekly completion rate
    var habits = getHabits();
    var habitsCompletedToday = 0;
    var totalHabitChecks = 0;
    var totalHabitPossible = 0;
    var todayState = getTodayState();
    habits.forEach(function(h) { if (todayState[h.id]) habitsCompletedToday++; });
    for (var d = 0; d < 7; d++) {
        var dt = new Date();
        dt.setDate(dt.getDate() - d);
        var key = 'habits-' + dt.toISOString().slice(0, 10);
        try {
            var ds = localStorage.getItem(key);
            if (ds) {
                var dayState = JSON.parse(ds);
                habits.forEach(function(h) { if (dayState[h.id]) totalHabitChecks++; });
            }
        } catch(e) {}
        totalHabitPossible += habits.length;
    }
    var habitRate = totalHabitPossible > 0 ? Math.round((totalHabitChecks / totalHabitPossible) * 100) : 0;

    // Busiest day this week (from calendar events)
    var dayCounts = {};
    var dayLabels = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    if (typeof CALENDAR_EVENTS !== 'undefined') {
        var weekStart = new Date();
        weekStart.setDate(weekStart.getDate() - weekStart.getDay() + 1);
        weekStart.setHours(0,0,0,0);
        var weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 6);
        var ws = _datStr(weekStart);
        var we = _datStr(weekEnd);
        CALENDAR_EVENTS.forEach(function(evt) {
            var ed = evt.start.substring(0, 10);
            if (ed >= ws && ed <= we) {
                dayCounts[ed] = (dayCounts[ed] || 0) + 1;
            }
        });
    }
    var busiestDay = '';
    var busiestCount = 0;
    Object.keys(dayCounts).forEach(function(d) {
        if (dayCounts[d] > busiestCount) {
            busiestCount = dayCounts[d];
            busiestDay = d;
        }
    });
    var busiestLabel = '';
    if (busiestDay) {
        var bd = new Date(busiestDay + 'T12:00:00');
        busiestLabel = dayLabels[bd.getDay()] + ' (' + busiestCount + ' events)';
    }

    // Current streak: consecutive days with all habits done
    var currentStreak = 0;
    for (var d = 0; d < 365; d++) {
        var dt = new Date();
        dt.setDate(dt.getDate() - d);
        var key = 'habits-' + dt.toISOString().slice(0, 10);
        try {
            var ds = localStorage.getItem(key);
            if (!ds) break;
            var dayState = JSON.parse(ds);
            var allDone = habits.length > 0;
            habits.forEach(function(h) { if (!dayState[h.id]) allDone = false; });
            if (allDone) currentStreak++;
            else break;
        } catch(e) { break; }
    }

    var html = '<div class="weekly-stats">';
    html += '<div class="weekly-stat"><div class="weekly-stat-value">' + tasksCompletedThisWeek + '</div><div class="weekly-stat-label">Tasks Done</div></div>';
    html += '<div class="weekly-stat"><div class="weekly-stat-value">' + habitRate + '%</div><div class="weekly-stat-label">Habit Rate</div></div>';
    html += '<div class="weekly-stat"><div class="weekly-stat-value">' + currentStreak + '<span class="weekly-stat-unit">d</span></div><div class="weekly-stat-label">Streak</div></div>';
    if (busiestLabel) {
        html += '<div class="weekly-stat"><div class="weekly-stat-value weekly-stat-text">' + busiestLabel + '</div><div class="weekly-stat-label">Busiest Day</div></div>';
    }
    html += '</div>';
    container.innerHTML = html;
}
renderWeeklySummary();
