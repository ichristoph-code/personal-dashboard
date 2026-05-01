# Implementation Plan: Contacts/Birthdays, Pomodoro Timer, Today Briefing

## Overview

Three features, touching the source layer, builder layer, CSS, JS, and dashboard.py orchestrator.
New tab order: **Today → Calendar → Tasks → Email → News → iMessage → Financials → Notes → Contacts → System**

---

## Feature 1: Contacts/Birthdays

### 1a. Data Source — `sources/contacts.py`

Add two new functions to the existing file:

**`get_all_contacts()`** — Full contact list for the Contacts tab
- Query `ZABCDRECORD` for: first name, last name, org, birthday (`ZBIRTHDAY`), note
- JOIN phone numbers and emails per contact
- Fetch thumbnails for all contacts (batch, not on-demand)
- Return: `[{name, first, last, org, birthday, phones: [], emails: [], thumb, note}, ...]`
- Birthday is stored as Core Data timestamp (seconds since 2001-01-01) — convert to `"MM-DD"` and `"YYYY-MM-DD"` format
- Cache to `.contacts_full_cache.json` with 30-min TTL (same pattern as existing)

**`get_upcoming_birthdays(days=30)`** — Lightweight version for Calendar card + Today briefing
- Calls `get_all_contacts()`, filters to contacts with birthdays in the next N days
- Calculates age if birth year is known
- Returns: `[{name, birthday_display, days_until, age, thumb}, ...]` sorted by `days_until`

### 1b. Builder — `builders/contacts.py` (new file)

**`build_contacts_html(contacts)`** — Two-panel layout (like Notes/iMessage)
- Left sidebar: searchable contact list with thumbnails, grouped alphabetically
- Right panel: contact detail card (name, phones, emails, birthday, notes)
- Search input filters contacts in real-time (JS)

**`build_birthdays_card(upcoming_birthdays)`** — Compact card for Calendar tab
- Shows upcoming birthdays in the next 30 days
- Each entry: thumbnail + name + date + age badge
- Styled like `due-soon-card`

### 1c. CSS — `templates/css/11-contacts.css` (new file)

- Two-panel layout classes
- Contact list items with thumbnails
- Birthday card styling
- Contact detail card layout
- Responsive/mobile

### 1d. JS — `templates/js/06-contacts.js` (new file)

- `selectContact(id)` — show contact details in right panel
- `filterContacts(query)` — search/filter contacts
- `initContactsList()` — wire up click handlers

### 1e. Wiring

- `sources/__init__.py`: export `get_all_contacts`, `get_upcoming_birthdays`
- `builders/__init__.py`: export `build_contacts_html`, `build_birthdays_card`
- `dashboard.py`:
  - Add `"contacts"` to `TAB_SOURCES`
  - Add source fetchers for contacts + birthdays
  - Add `_build_contacts_panel()`
  - Add birthday card in `_build_calendar_panel()`
  - Add `/api/tab/contacts` handling
  - Add contacts tab button + panel in HTML
  - Add contacts badge (upcoming birthdays in 7 days)

---

## Feature 2: Pomodoro Timer

Pure frontend — no backend changes needed.

### 2a. CSS — `templates/css/02-pomodoro.css` (new file)

- `.pomodoro-widget` — compact inline display in header-actions
- Timer display with SVG ring progress indicator
- States: idle (muted), working (warm red/orange glow), break (green glow)
- Controls: play/pause, reset
- Session dots (4 dots showing cycle progress)
- Responsive sizing for mobile

### 2b. JS — `templates/js/07-pomodoro.js` (new file)

- Timer state machine: IDLE → WORKING → SHORT_BREAK → WORKING → ... → LONG_BREAK
- Standard durations: 25min work, 5min short break, 15min long break (every 4th)
- `startPomodoro()`, `pausePomodoro()`, `resetPomodoro()`, `skipPhase()`
- Countdown uses `setInterval(1000)` — update display + SVG ring
- Audio notification via Web Audio API on phase completion
- State persisted in `localStorage('dashboard-pomodoro')` so timer survives refresh
- On page load: restore timer state, resume countdown if running
- Visual: `MM:SS` remaining + phase label + session count (e.g., "2/4")

### 2c. Wiring

- `dashboard.py`: Add pomodoro widget HTML in `header-actions` div (between clock and website launcher)
- `13-keyboard-widgets.js`: Add keyboard shortcut `P` to toggle pomodoro start/pause

---

## Feature 3: Today Briefing Tab

### 3a. Builder — `builders/today.py` (new file)

**`build_today_html(data)`** — Aggregates data from all sources

Takes a dict with pre-fetched data and renders a grid of summary cards:

1. **Weather Card** — Current conditions + today's high/low
2. **Calendar Card** — Today's events in compact timeline
3. **Tasks Card** — Today's Things tasks count + list (top 8), link to Tasks tab
4. **Email Card** — Unread count + top 3 subjects, link to Email tab
5. **iMessage Card** — Unread count, link to iMessage tab
6. **Financial Snapshot** — Net worth + ready to assign, link to Financials tab
7. **Birthdays Card** — Any birthdays today/this week, link to Contacts tab

Each card is clickable → `switchTab('...')`.

### 3b. CSS — `templates/css/04-today.css` (new file)

- `.today-grid` — responsive grid layout
- `.today-card` — glass-morphism style cards with icon + content
- `.today-card:hover` — subtle lift/glow effect
- Each card type gets a color accent on the left border
- Responsive: 2 columns on tablet, 1 on mobile

### 3c. Wiring

- `builders/__init__.py`: export `build_today_html`
- `dashboard.py`:
  - Add `"today"` to `TAB_SOURCES` (uses calendar, weather, things, mail, imessages, birthdays)
  - `_build_today_panel()` uses already-fetched results from the common fetch
  - Add Today tab button as FIRST tab (active by default)
  - Add Today panel as first `tab-panel`
  - Default tab becomes `'today'` instead of `'calendar'`
- `templates/js/13-keyboard-widgets.js`:
  - Update `TAB_NAMES` array: prepend `'today'`
  - Update keyboard shortcut overlay (1=Today, 2=Calendar, etc.)
  - Update `_reinitTab`, `_updateBadges`, default tab restore logic

---

## Implementation Order

1. `sources/contacts.py` — add get_all_contacts + get_upcoming_birthdays
2. `builders/contacts.py` — new file (contacts tab + birthday card)
3. `builders/today.py` — new file (Today briefing builder)
4. CSS files — 02-pomodoro.css, 04-today.css, 11-contacts.css
5. JS files — 06-contacts.js, 07-pomodoro.js
6. `sources/__init__.py` + `builders/__init__.py` — add exports
7. `dashboard.py` — wire everything (source fetching, tab panels, server endpoints, pomodoro HTML)
8. `templates/js/13-keyboard-widgets.js` — update TAB_NAMES, shortcuts, _reinitTab, _updateBadges, default tab

---

## Files Modified (existing)

| File | Changes |
|------|---------|
| `sources/contacts.py` | Add `get_all_contacts()`, `get_upcoming_birthdays()` |
| `sources/__init__.py` | Add 2 new exports |
| `builders/__init__.py` | Add 3 new exports |
| `dashboard.py` | New tabs, panels, source wiring, API endpoints, pomodoro HTML |
| `templates/js/13-keyboard-widgets.js` | TAB_NAMES, shortcuts overlay, _reinitTab, _updateBadges |

## Files Created (new)

| File | Purpose |
|------|---------|
| `builders/contacts.py` | Contacts tab + birthdays card HTML builders |
| `builders/today.py` | Today briefing HTML builder |
| `templates/css/02-pomodoro.css` | Pomodoro timer widget styles |
| `templates/css/04-today.css` | Today briefing tab styles |
| `templates/css/11-contacts.css` | Contacts tab styles |
| `templates/js/06-contacts.js` | Contact list interaction |
| `templates/js/07-pomodoro.js` | Pomodoro timer logic |
