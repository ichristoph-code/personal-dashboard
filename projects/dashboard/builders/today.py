"""Today Briefing tab — morning dashboard with aggregated data at a glance."""

import json
from datetime import datetime, timedelta
from html import escape
from pathlib import Path


def build_today_html(data):
    """Build the Today briefing panel HTML.

    Args:
        data: dict with keys:
            weather, calendar_events, things_data, mail_messages,
            imessages, upcoming_birthdays, net_worth, ready_to_assign,
            briefing (str), commute (dict)
    """
    parts = []

    # ── AI Morning Briefing (full-width, above grid) ──
    briefing = data.get("briefing")
    if briefing:
        parts.append(
            f'<div class="today-briefing">'
            f'<span class="today-briefing-icon">✨</span>'
            f'<p class="today-briefing-text">{escape(briefing)}</p>'
            f'</div>'
        )

    parts.append('<div class="today-grid" id="today-grid">')

    # ── Weather Card ──
    weather = data.get("weather")
    parts.append(_build_weather_card(weather))

    # ── Calendar Card ──
    events = data.get("calendar_events")
    parts.append(_build_calendar_card(events))

    # ── Tasks Card ──
    things = data.get("things_data") or {}
    parts.append(_build_tasks_card(things))

    # ── Email Card ──
    mail = data.get("mail_messages")
    parts.append(_build_email_card(mail))

    # ── iMessage Card ──
    imessages = data.get("imessages")
    parts.append(_build_imessage_card(imessages))

    # ── Financial Snapshot ──
    parts.append(_build_finance_card(
        data.get("net_worth", 0),
        data.get("ready_to_assign", 0),
    ))

    # ── Birthdays Card ──
    birthdays = data.get("upcoming_birthdays") or []
    parts.append(_build_birthdays_card(birthdays))

    # ── Commute Card ──
    commute = data.get("commute")
    if commute:
        parts.append(_build_commute_card(commute))

    parts.append('</div>')  # today-grid
    return "\n".join(parts)


_DRAG_HANDLE = '<span class="card-drag-handle" title="Drag to reorder">\u283f</span>'


def _build_weather_card(weather):
    """Current weather conditions card."""
    if not weather:
        return (
            '<div class="today-card today-weather draggable-card" data-card-id="today-weather" onclick="switchTab(\'calendar\')">'
            + _DRAG_HANDLE +
            '<div class="today-card-header">'
            '<span class="today-card-icon">🌤️</span>'
            '<span class="today-card-title">Weather</span>'
            '</div>'
            '<div class="today-card-body">'
            '<p class="muted">Weather data unavailable</p>'
            '</div></div>'
        )

    icon = weather.get("current_icon", "🌡️")
    temp = weather.get("current_temp", "--")
    desc = escape(weather.get("current_desc", ""))
    feels = weather.get("feels_like", "")

    # Today's forecast (first day)
    forecast = weather.get("forecast", [])
    today_hi = today_lo = ""
    if forecast:
        today = forecast[0]
        today_hi = today.get("high", "")
        today_lo = today.get("low", "")

    feels_html = f'<span class="today-weather-feels">Feels like {feels}°</span>' if feels else ""
    hilo_html = ""
    if today_hi and today_lo:
        hilo_html = (
            f'<span class="today-weather-hilo">'
            f'H: {today_hi}° &nbsp; L: {today_lo}°'
            f'</span>'
        )

    # 5-day forecast strip (days 1–4, skipping today which is shown above)
    forecast_strip = ""
    future = forecast[1:5] if len(forecast) > 1 else []
    if future:
        _DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_parts = []
        for day in future:
            try:
                dt = datetime.strptime(day["date"], "%Y-%m-%d")
                dow = _DOW[dt.weekday()]
            except Exception:
                dow = day.get("date", "")[-5:]
            d_icon = day.get("icon", "")
            d_hi = day.get("high", "--")
            d_lo = day.get("low", "--")
            day_parts.append(
                f'<div class="today-forecast-day">'
                f'<span class="today-forecast-dow">{dow}</span>'
                f'<span class="today-forecast-icon">{d_icon}</span>'
                f'<span class="today-forecast-hi">{d_hi}°</span>'
                f'<span class="today-forecast-lo">{d_lo}°</span>'
                f'</div>'
            )
        forecast_strip = (
            '<div class="today-forecast-strip">' +
            "".join(day_parts) +
            '</div>'
        )

    return (
        '<div class="today-card today-weather draggable-card" data-card-id="today-weather" onclick="switchTab(\'calendar\')">'
        + _DRAG_HANDLE +
        f'<div class="today-card-header">'
        f'<span class="today-card-icon">{icon}</span>'
        f'<span class="today-card-title">Weather</span>'
        f'</div>'
        f'<div class="today-card-body">'
        f'<div class="today-weather-main">'
        f'<span class="today-weather-temp">{temp}°F</span>'
        f'<span class="today-weather-desc">{desc}</span>'
        f'</div>'
        f'{feels_html}'
        f'{hilo_html}'
        f'{forecast_strip}'
        f'</div></div>'
    )


def _build_calendar_card(events):
    """Today's calendar events card."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    _CAL_OPEN = f'<div class="today-card today-calendar draggable-card" data-card-id="today-calendar" data-date="{today_str}" onclick="switchTab(\'calendar\')">' + _DRAG_HANDLE
    if not events:
        return (
            _CAL_OPEN +
            '<div class="today-card-header">'
            '<span class="today-card-icon">📅</span>'
            '<span class="today-card-title">Calendar</span>'
            '</div>'
            '<div class="today-card-body">'
            '<p class="today-empty">No events today</p>'
            '</div></div>'
        )

    today_events = [e for e in events if e["start"].startswith(today_str)]

    if not today_events:
        return (
            _CAL_OPEN +
            '<div class="today-card-header">'
            '<span class="today-card-icon">📅</span>'
            '<span class="today-card-title">Calendar</span>'
            '</div>'
            '<div class="today-card-body">'
            '<p class="today-empty">No events today</p>'
            '</div></div>'
        )

    parts = [
        _CAL_OPEN,
        '<div class="today-card-header">',
        '<span class="today-card-icon">📅</span>',
        '<span class="today-card-title">Calendar</span>',
        f'<span class="today-card-count">{len(today_events)}</span>',
        '</div>',
        '<div class="today-card-body">',
        '<ul class="today-event-list">',
    ]

    now = datetime.now()
    for evt in today_events[:6]:  # cap at 6
        title = escape(evt["title"])
        is_past = False
        if evt.get("all_day"):
            time_str = "All day"
        else:
            try:
                dt = datetime.strptime(evt["start"], '%Y-%m-%d %H:%M')
                time_str = dt.strftime('%-I:%M %p')
                end_str = evt.get("end", "")
                if end_str:
                    dt_end = datetime.strptime(end_str, '%Y-%m-%d %H:%M')
                else:
                    dt_end = dt + timedelta(hours=1)
                is_past = dt_end < now
            except ValueError:
                time_str = ""

        past_class = " today-event--past" if is_past else ""
        parts.append(
            f'<li class="today-event{past_class}" onclick="event.stopPropagation()">'
            f'<span class="today-event-time">{time_str}</span>'
            f'<span class="today-event-title">{title}</span>'
            f'<a class="today-event-cal-link" href="x-apple-cal://" '
            f'title="Open Calendar" onclick="event.stopPropagation()">↗</a>'
            f'</li>'
        )

    if len(today_events) > 6:
        parts.append(
            f'<li class="today-event today-more">'
            f'+{len(today_events) - 6} more events'
            f'</li>'
        )

    parts.extend(['</ul>', '</div></div>'])
    return "\n".join(parts)


def _build_tasks_card(things_data):
    """Today's tasks card."""
    today_tasks = things_data.get("today", [])
    count = len(today_tasks)

    parts = [
        '<div class="today-card today-tasks draggable-card" data-card-id="today-tasks" onclick="switchTab(\'tasks\')">' + _DRAG_HANDLE,
        '<div class="today-card-header">',
        '<span class="today-card-icon">✅</span>',
        '<span class="today-card-title">Tasks</span>',
    ]
    if count:
        parts.append(f'<span class="today-card-count">{count}</span>')
    parts.append('</div>')

    parts.append('<div class="today-card-body">')
    if not today_tasks:
        parts.append('<p class="today-empty">No tasks for today</p>')
    else:
        parts.append('<ul class="today-task-list">')
        for i, task in enumerate(today_tasks):
            title = escape(task.get("title", ""))
            uuid = escape(task.get("uuid", ""))
            project = task.get("project", "")
            proj_html = ""
            if project:
                proj_html = f'<span class="today-task-project">{escape(project)}</span>'
            hidden = ' style="display:none"' if i >= 8 else ''
            parts.append(
                f'<li class="today-task-item" data-uuid="{uuid}" onclick="event.stopPropagation()"{hidden}>'
                f'<button class="today-task-check" '
                f'onclick="completeTaskFromToday(this,event)" title="Complete task">○</button>'
                f'<span class="today-task-title">{title}</span>'
                f'{proj_html}'
                f'</li>'
            )
        if count > 8:
            parts.append(
                f'<li class="today-task-item today-more" '
                f'onclick="expandTodayTasks(this,event)">+{count - 8} more</li>'
            )
        parts.append('</ul>')

    parts.append('</div></div>')
    return "\n".join(parts)


def _build_email_card(mail_messages):
    """Unread email summary card."""
    unread_count = 0
    top_subjects = []

    if mail_messages:
        for folder_msgs in mail_messages.values():
            for m in folder_msgs:
                if not m.get("read"):
                    unread_count += 1
                    if len(top_subjects) < 3:
                        top_subjects.append(m.get("subject", "(no subject)"))

    parts = [
        '<div class="today-card today-email draggable-card" data-card-id="today-email" onclick="switchTab(\'email\')">' + _DRAG_HANDLE,
        '<div class="today-card-header">',
        '<span class="today-card-icon">📧</span>',
        '<span class="today-card-title">Email</span>',
    ]
    if unread_count:
        parts.append(f'<span class="today-card-count">{unread_count}</span>')
    parts.append('</div>')

    parts.append('<div class="today-card-body">')
    if unread_count == 0:
        parts.append('<p class="today-empty">Inbox zero 🎉</p>')
    else:
        parts.append(f'<p class="today-stat">{unread_count} unread</p>')
        if top_subjects:
            parts.append('<ul class="today-subject-list">')
            for subj in top_subjects:
                parts.append(
                    f'<li class="today-subject">{escape(subj[:60])}</li>'
                )
            parts.append('</ul>')

    parts.append('</div></div>')
    return "\n".join(parts)


def _build_imessage_card(imessages):
    """Unread iMessage summary card."""
    unread = 0
    if imessages:
        unread = sum(c.get("unread_count", 0) for c in imessages)

    parts = [
        '<div class="today-card today-imessage draggable-card" data-card-id="today-imessage" onclick="switchTab(\'imessage\')">' + _DRAG_HANDLE,
        '<div class="today-card-header">',
        '<span class="today-card-icon">💬</span>',
        '<span class="today-card-title">iMessage</span>',
    ]
    if unread:
        parts.append(f'<span class="today-card-count">{unread}</span>')
    parts.append('</div>')

    parts.append('<div class="today-card-body">')
    if unread == 0:
        parts.append('<p class="today-empty">All caught up</p>')
    else:
        parts.append(f'<p class="today-stat">{unread} unread message{"s" if unread != 1 else ""}</p>')
        # Show top unread conversation names
        if imessages:
            unread_convos = [c for c in imessages if c.get("unread_count", 0) > 0]
            if unread_convos:
                parts.append('<ul class="today-subject-list">')
                for c in unread_convos[:3]:
                    name = escape(c.get("display_name", "Unknown"))
                    cnt = c["unread_count"]
                    parts.append(
                        f'<li class="today-subject">{name} ({cnt})</li>'
                    )
                parts.append('</ul>')

    parts.append('</div></div>')
    return "\n".join(parts)


def _build_nw_sparkline():
    """Build an inline SVG sparkline from .net_worth_history.json (last 30 days)."""
    history_path = Path(__file__).parent.parent / '.net_worth_history.json'
    try:
        with open(history_path) as f:
            history = json.load(f)
        if len(history) < 2:
            return ''
        values = [e['value'] for e in history[-30:]]
        min_v, max_v = min(values), max(values)
        if max_v == min_v:
            return ''
        W, H = 200, 36
        pts = []
        n = len(values) - 1
        for i, v in enumerate(values):
            x = round(i * W / n, 1)
            y = round(H - (v - min_v) / (max_v - min_v) * H, 1)
            pts.append(f'{x},{y}')
        color = '#48bb78' if values[-1] >= values[0] else '#fc8181'
        return (
            f'<svg class="today-sparkline" viewBox="0 0 {W} {H}" '
            f'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
            f'</svg>'
        )
    except Exception:
        return ''


def _build_finance_card(net_worth, ready_to_assign):
    """Financial snapshot card."""
    nw_class = "positive" if net_worth >= 0 else "negative"
    rta_class = "positive" if ready_to_assign >= 0 else "negative"
    sparkline = _build_nw_sparkline()

    eye_open = '<svg class="tf-eye-open" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>'
    eye_closed = '<svg class="tf-eye-closed" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>'
    return (
        '<div class="today-card today-finance draggable-card" data-card-id="today-finance" onclick="switchTab(\'financials\')">'
        + _DRAG_HANDLE +
        f'<div class="today-card-header">'
        f'<span class="today-card-icon">💰</span>'
        f'<span class="today-card-title">Finances</span>'
        f'<button class="today-finance-privacy-btn" onclick="toggleTodayFinancePrivacy(event)" title="Show/hide balances">{eye_open}{eye_closed}</button>'
        f'</div>'
        f'<div class="today-card-body">'
        f'<div class="today-finance-row">'
        f'<span class="today-finance-label">Net Worth</span>'
        f'<span class="today-finance-value {nw_class}">${net_worth:,.0f}</span>'
        f'</div>'
        f'{sparkline}'
        f'<div class="today-finance-row">'
        f'<span class="today-finance-label">Ready to Assign</span>'
        f'<span class="today-finance-value {rta_class}">${ready_to_assign:,.0f}</span>'
        f'</div>'
        f'</div></div>'
    )


def _build_commute_card(commute):
    """Estimated commute time card."""
    minutes = commute.get("minutes", 0)
    maps_url = escape(commute.get("maps_url", "#"))
    dest = escape(commute.get("work_address", "Work"))
    hours = minutes // 60
    mins  = minutes % 60
    time_str = f"{hours}h {mins}m" if hours else f"{minutes} min"

    return (
        '<div class="today-card today-commute draggable-card" data-card-id="today-commute">'
        + _DRAG_HANDLE +
        f'<div class="today-card-header">'
        f'<span class="today-card-icon">🚗</span>'
        f'<span class="today-card-title">Commute</span>'
        f'</div>'
        f'<div class="today-card-body">'
        f'<div class="today-commute-time">{time_str}</div>'
        f'<div class="today-commute-dest">{dest}</div>'
        f'<p class="today-commute-note">Baseline estimate · no live traffic</p>'
        f'<a href="{maps_url}" class="today-commute-link">Open in Maps →</a>'
        f'</div></div>'
    )


def _build_birthdays_card(upcoming_birthdays):
    """Upcoming birthdays card for the Today panel."""
    # Only show birthdays in the next 7 days
    soon = [b for b in upcoming_birthdays if b["days_until"] <= 7]

    parts = [
        '<div class="today-card today-birthdays draggable-card" data-card-id="today-birthdays" onclick="switchTab(\'contacts\')">' + _DRAG_HANDLE,
        '<div class="today-card-header">',
        '<span class="today-card-icon">🎂</span>',
        '<span class="today-card-title">Birthdays</span>',
    ]
    if soon:
        parts.append(f'<span class="today-card-count">{len(soon)}</span>')
    parts.append('</div>')

    parts.append('<div class="today-card-body">')
    if not soon:
        parts.append('<p class="today-empty">No birthdays this week</p>')
    else:
        parts.append('<ul class="today-birthday-list">')
        for b in soon[:5]:
            name = escape(b["name"])
            if b["days_until"] == 0:
                when = "Today!"
            elif b["days_until"] == 1:
                when = "Tomorrow"
            else:
                when = f"In {b['days_until']} days"
            age_html = ""
            if b.get("age") is not None:
                age_html = f' <span class="today-bday-age">(turning {b["age"]})</span>'
            parts.append(
                f'<li class="today-birthday-item">'
                f'<span class="today-bday-name">{name}{age_html}</span>'
                f'<span class="today-bday-when">{when}</span>'
                f'</li>'
            )
        parts.append('</ul>')

    parts.append('</div></div>')
    return "\n".join(parts)
