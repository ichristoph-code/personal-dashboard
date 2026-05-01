"""Calendar and weather forecast HTML builders."""

import json
from datetime import datetime, timedelta
from html import escape

from .helpers import _cal_color


def build_calendar_html(events, weather=None, include_scripts=True):
    """Build the calendar section HTML with per-day cards and add-event form.

    weather: dict from get_weather() — forecast data embedded into day card headers.
    include_scripts: if False, omit the inline <script> tags (for AJAX updates).
    """
    # Build a date→forecast lookup for quick access
    forecast_by_date = {}
    if weather and weather.get("forecast"):
        for day in weather["forecast"]:
            forecast_by_date[day["date"]] = day

    today_date_str = datetime.now().strftime('%Y-%m-%d')

    # Embed event data as JSON for JS-driven calendar views
    events_json_data = []
    if events:
        for evt in events:
            events_json_data.append({
                "title": evt["title"],
                "calendar": evt["calendar"],
                "start": evt["start"],
                "end": evt["end"],
                "all_day": evt["all_day"],
                "location": evt.get("location", ""),
                "event_id": evt.get("event_id", ""),
            })
    events_json = json.dumps(events_json_data)
    forecast_json = json.dumps(forecast_by_date)
    events_script = ''
    if include_scripts:
        events_script = (
            f'<script>var CALENDAR_EVENTS = {events_json}; '
            f'var WEATHER_FORECAST = {forecast_json};</script>'
        )

    # View switcher bar
    view_switcher = '''<div class="cal-view-bar">
        <button class="cal-view-btn active" onclick="switchCalView('day')" data-view="day">Day</button>
        <button class="cal-view-btn" onclick="switchCalView('week')" data-view="week">Week</button>
        <button class="cal-view-btn" onclick="switchCalView('month')" data-view="month">Month</button>
        <button class="cal-view-btn" onclick="switchCalView('year')" data-view="year">Year</button>
        <div class="cal-nav">
            <button class="cal-nav-btn" onclick="navigateCal(-1)" title="Previous">&lsaquo;</button>
            <span class="cal-nav-label" id="calNavLabel"></span>
            <button class="cal-nav-btn" onclick="navigateCal(1)" title="Next">&rsaquo;</button>
            <button class="cal-nav-today-btn" onclick="navigateCalToday()">Today</button>
        </div>
    </div>'''

    # Floating add-event button + dialog (replaces the old fixed card)
    add_event_fab = '''<button class="cal-add-fab" onclick="openAddEventDialog()" title="Add event">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
    </button>'''

    add_event_dialog = '''<div class="cal-add-dialog-overlay" id="addEventOverlay" style="display:none" onclick="if(event.target===this)closeAddEventDialog()">
        <div class="cal-add-dialog">
            <div class="cal-add-dialog-header">
                <h3>New Event</h3>
                <button class="cal-add-dialog-close" onclick="closeAddEventDialog()" title="Close">&times;</button>
            </div>
            <div class="add-event-form">
                <div class="add-event-row">
                    <input type="text" class="add-event-input" id="eventTitle" placeholder="Event title" />
                </div>
                <div class="add-event-row add-event-datetime">
                    <input type="date" class="add-event-input" id="eventDate" />
                    <input type="time" class="add-event-input" id="eventStart" value="09:00" />
                    <span class="add-event-to">to</span>
                    <input type="time" class="add-event-input" id="eventEnd" value="10:00" />
                </div>
                <div class="add-event-row">
                    <input type="text" class="add-event-input" id="eventLocation" placeholder="Location (optional)" />
                </div>
                <div class="add-event-row" style="justify-content:flex-end;gap:8px;margin-top:4px">
                    <button class="evt-cancel-btn" onclick="closeAddEventDialog()">Cancel</button>
                    <button class="add-event-btn" onclick="addEvent()">Add Event</button>
                </div>
            </div>
        </div>
    </div>'''

    if events is None:
        return events_script + view_switcher + add_event_fab + add_event_dialog + '''<div id="calDayView"><div class="card">
            <h3>Calendar</h3>
            <p class="muted">Calendar access not available. Run <code>cal_helper</code> and grant calendar permission in System Settings &gt; Privacy &amp; Security &gt; Calendars.</p>
        </div></div><div id="calAltView"></div>'''

    # Expand multi-day events so they appear on each day they span
    expanded = []
    for evt in events:
        start_date = evt["start"][:10]
        end_date = evt["end"][:10]
        if start_date != end_date and evt["all_day"]:
            sd = datetime.strptime(start_date, '%Y-%m-%d')
            ed = datetime.strptime(end_date, '%Y-%m-%d')
            day_num = 0
            total_days = (ed - sd).days + 1
            current = sd
            while current <= ed:
                day_num += 1
                day_str = current.strftime('%Y-%m-%d')
                copy = dict(evt)
                copy["_display_date"] = day_str
                if total_days > 1:
                    copy["_span_label"] = f"Day {day_num} of {total_days}"
                expanded.append(copy)
                current += timedelta(days=1)
        else:
            evt_copy = dict(evt)
            evt_copy["_display_date"] = start_date
            expanded.append(evt_copy)

    # Group events by display date
    days = {}
    for evt in expanded:
        date_str = evt["_display_date"]
        days.setdefault(date_str, []).append(evt)

    html_parts = [events_script, view_switcher, add_event_fab, add_event_dialog, '<div id="calDayView">']
    today_str = today_date_str
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    # Only render detailed day cards for the next 14 days; month/year views
    # are JS-driven from the CALENDAR_EVENTS JSON and don't need HTML cards.
    day_card_cutoff = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')

    # Build the set of dates to render: all event dates + all forecast dates,
    # so weather-only days (no events) still get a card with the weather pill.
    forecast_dates = sorted(forecast_by_date.keys())
    all_dates = sorted(set(list(days.keys()) + forecast_dates))

    for date_str in all_dates:
        if date_str < today_str:
            continue
        if date_str > day_card_cutoff:
            break
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        if date_str == today_str:
            day_label = "Today"
        elif date_str == tomorrow_str:
            day_label = "Tomorrow"
        else:
            day_label = dt.strftime('%A, %b %d')

        is_today = date_str == today_str
        card_class = "card day-card today-card" if is_today else "card day-card"

        # Weather pill for this day
        wx = forecast_by_date.get(date_str)
        weather_pill = ''
        if wx:
            weather_pill = (
                f'<span class="day-weather-pill">'
                f'<span class="day-wx-icon">{wx["icon"]}</span>'
                f'<span class="day-wx-high">{wx["high"]}°</span>'
                f'<span class="day-wx-sep">/</span>'
                f'<span class="day-wx-low">{wx["low"]}°</span>'
                f'</span>'
            )

        html_parts.append(
            f'<div class="{card_class}" data-date="{date_str}">'
            f'<div class="day-header">'
            f'<div class="day-label">{day_label}</div>'
            f'{weather_pill}'
            f'</div>'
        )
        day_events = days.get(date_str, [])
        if not day_events:
            html_parts.append('<p class="evt-none">No events</p>')
        for evt in day_events:
            title = escape(evt["title"])
            cal = escape(evt["calendar"])
            cal_color = _cal_color(evt["calendar"])
            if evt["all_day"]:
                span_label = evt.get("_span_label", "")
                time_str = f"All day &middot; {span_label}" if span_label else "All day"
            else:
                try:
                    start_dt = datetime.strptime(evt["start"], '%Y-%m-%d %H:%M')
                    end_dt = datetime.strptime(evt["end"], '%Y-%m-%d %H:%M')
                    time_str = f'{start_dt.strftime("%-I:%M %p")} &ndash; {end_dt.strftime("%-I:%M %p")}'
                except ValueError:
                    time_str = evt["start"][11:]
            loc_html = f'<span class="evt-loc">{escape(evt["location"])}</span>' if evt.get("location") else ''
            eid = escape(evt.get("event_id", ""))
            is_span = bool(evt.get("_span_label"))
            # Edit/delete buttons — shown for all events with an ID
            actions = ''
            if eid:
                eid_js = eid.replace("'", "\\'")
                cal_js = evt.get("calendar", "").replace("'", "\\'")
                actions = (
                    f'<span class="evt-actions">'
                    f'<button class="evt-edit-btn" onclick="editEvent(\'{eid_js}\',\'{cal_js}\')" title="Edit">'
                    f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>'
                    f'</button>'
                    f'<button class="evt-del-btn" onclick="deleteEvent(\'{eid_js}\')" title="Delete">'
                    f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
                    f'</button>'
                    f'</span>'
                )
            # Inline edit form (hidden by default) — only on first occurrence to avoid duplicate IDs
            edit_form = ''
            if eid and not is_span:
                evt_start_val = evt["start"].replace(" ", "T") if " " in evt["start"] else evt["start"]
                evt_end_val = evt["end"].replace(" ", "T") if " " in evt["end"] else evt["end"]
                cal_esc = escape(evt.get("calendar", ""))
                edit_form = (
                    f'<div class="evt-edit-form" id="edit-{eid}" style="display:none">'
                    f'<div class="add-event-row">'
                    f'<input type="text" class="add-event-input" value="{title}" id="edit-title-{eid}" placeholder="Title" style="flex:2">'
                    f'<input type="text" class="add-event-input" value="{escape(evt.get("location", ""))}" id="edit-loc-{eid}" placeholder="Location" style="flex:1">'
                    f'</div>'
                    f'<div class="add-event-row add-event-datetime" style="margin-top:4px">'
                    f'<input type="date" class="add-event-input" value="{evt["start"][:10]}" id="edit-date-{eid}">'
                    f'<input type="time" class="add-event-input" value="{evt_start_val[11:16] if len(evt_start_val) > 11 else "09:00"}" id="edit-start-{eid}">'
                    f'<span class="add-event-to">to</span>'
                    f'<input type="time" class="add-event-input" value="{evt_end_val[11:16] if len(evt_end_val) > 11 else "10:00"}" id="edit-end-{eid}">'
                    f'</div>'
                    f'<div class="add-event-row" style="margin-top:4px;gap:6px">'
                    f'<select class="add-event-input evt-cal-select" id="edit-cal-{eid}" onchange="updateCalSwatch(\'{eid_js}\')">'
                    f'<option value="{cal_esc}" selected>{cal_esc}</option>'
                    f'</select>'
                    f'<button class="evt-cal-swatch" id="edit-swatch-{eid}" onclick="openCalColorPicker(\'{eid_js}\',this)" title="Change calendar color" style="background:{cal_color};width:28px;height:28px;flex-shrink:0;border:2px solid var(--border);border-radius:6px;cursor:pointer;padding:0"></button>'
                    f'<button class="add-event-btn" onclick="saveEventEdit(\'{eid_js}\')">Save</button>'
                    f'<button class="evt-cancel-btn" onclick="cancelEdit(\'{eid_js}\')">Cancel</button>'
                    f'</div></div>'
                )
            can_edit = bool(eid)
            cal_js_attr = escape(evt.get("calendar", ""))
            row_cursor = 'cursor:pointer' if can_edit else 'cursor:default'
            html_parts.append(
                f'<div class="evt-wrap" data-eid="{eid}" data-cal="{cal_js_attr}" style="border-left: 3px solid {cal_color}; padding-left: 10px;">'
                f'<div class="evt-row" style="{row_cursor}">'
                f'<div class="evt-time">{time_str}</div>'
                f'<div class="evt-detail"><span class="evt-title">{title}</span>'
                f'<span class="evt-cal" style="color:{cal_color}">{cal}</span>{actions}{loc_html}</div>'
                f'</div>'
                f'{edit_form}</div>'
            )
        html_parts.append('</div>')

    html_parts.append('</div><!-- /calDayView -->')
    html_parts.append('<div id="calAltView"></div>')
    html_parts.append('<div id="calEvtFormContainer"></div>')
    return '\n'.join(html_parts)


def build_weather_forecast_html(weather):
    """Build 5-day forecast cards for the Calendar tab."""
    if not weather or not weather.get("forecast"):
        return ''
    today_str = datetime.now().strftime('%Y-%m-%d')
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    cards = []
    for day in weather["forecast"]:
        d = day["date"]
        if d == today_str:
            label = "Today"
        elif d == tomorrow_str:
            label = "Tomorrow"
        else:
            try:
                label = datetime.strptime(d, '%Y-%m-%d').strftime('%a %b %d')
            except ValueError:
                label = d
        cards.append(
            f'<div class="forecast-day">'
            f'<div class="forecast-label">{label}</div>'
            f'<div class="forecast-icon">{day["icon"]}</div>'
            f'<div class="forecast-temps">'
            f'<span class="forecast-high">{day["high"]}\u00b0</span>'
            f'<span class="forecast-low">{day["low"]}\u00b0</span>'
            f'</div>'
            f'<div class="forecast-desc">{escape(day["desc"])}</div>'
            f'</div>'
        )
    return (
        '<div class="card forecast-card"><h3>5-Day Forecast</h3>'
        '<div class="forecast-row">' + ''.join(cards) + '</div></div>'
    )
