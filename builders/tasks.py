"""Things 3 task list HTML builders."""

from datetime import datetime, date, timedelta
from html import escape


def _smart_deadline(deadline_str):
    """Return (label, css_class) for a deadline date string.

    Labels:
        Overdue      → "Overdue"  / "Yesterday" (if 1 day ago)
        Today        → "Today"
        Tomorrow     → "Tomorrow"
        This week    → weekday name ("Wed", "Thu")
        Next week    → "Next Mon", "Next Tue"
        This month   → "Mar 15"
        Later        → "Mar 15" or "Mar 15, 2027" if different year
    CSS classes:
        deadline-overdue   – red, past due
        deadline-today     – orange/urgent
        deadline-tomorrow  – warm
        deadline-week      – accent, this week
        deadline-later     – muted/neutral
    """
    try:
        dl = datetime.strptime(deadline_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None, None

    today = date.today()
    delta = (dl - today).days

    if delta < -1:
        label = f"Overdue · {dl.strftime('%b %-d')}"
        return label, "deadline-overdue"
    elif delta == -1:
        return "Yesterday", "deadline-overdue"
    elif delta == 0:
        return "Today", "deadline-today"
    elif delta == 1:
        return "Tomorrow", "deadline-tomorrow"
    elif delta <= 6:
        # This week — show weekday name
        return dl.strftime("%A"), "deadline-week"
    elif delta <= 13:
        # Next week
        return f"Next {dl.strftime('%a')}", "deadline-later"
    elif dl.year == today.year:
        return dl.strftime("%b %-d"), "deadline-later"
    else:
        return dl.strftime("%b %-d, %Y"), "deadline-later"


def _bucket_by_time(tasks):
    """Group tasks into time-based buckets for the Upcoming panel.

    Returns a list of (bucket_label, [tasks]) tuples in chronological order.
    Buckets: This Week, This Month, Later.
    Overdue and Today are handled separately in the Today tab.
    """
    today = date.today()
    # End of this week (Sunday inclusive)
    days_until_sun = (6 - today.weekday()) % 7 or 7  # always >= 1
    end_of_week = today + timedelta(days=days_until_sun)
    # End of this month
    if today.month == 12:
        end_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        end_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)

    buckets = {
        "This Week": [],
        "This Month": [],
        "Later": [],
    }

    for task in tasks:
        dl_str = task.get("deadline", "")
        if not dl_str:
            buckets["Later"].append(task)
            continue
        try:
            dl = datetime.strptime(dl_str, '%Y-%m-%d').date()
        except ValueError:
            buckets["Later"].append(task)
            continue

        if dl <= end_of_week:
            buckets["This Week"].append(task)
        elif dl <= end_of_month:
            buckets["This Month"].append(task)
        else:
            buckets["Later"].append(task)

    # Return only non-empty buckets, in order
    order = ["This Week", "This Month", "Later"]
    return [(name, buckets[name]) for name in order if buckets[name]]


def build_task_li(task, token, show_project=True):
    """Build a single task list item with inline edit/deadline/delete actions."""
    title_raw = task["title"]
    title = escape(title_raw)
    uuid = escape(task.get("uuid", ""))
    deadline_raw = task.get("deadline", "")
    notes_raw = task.get("notes", "")
    is_today = task.get("today", False)

    # Meta pills
    meta = ''
    if show_project and task.get("project"):
        meta += f'<span class="task-project">{escape(task["project"])}</span>'
    if deadline_raw:
        label, dl_cls = _smart_deadline(deadline_raw)
        if label:
            meta += (
                f'<span class="task-deadline {dl_cls}" '
                f'data-deadline="{escape(deadline_raw)}" '
                f'onclick="event.stopPropagation();openDatePicker(event,\'{uuid}\')"'
                f'>{label}</span>'
            )
    else:
        # Show a subtle "+ due" button on hover for tasks without a deadline
        meta += (
            f'<button class="task-due-btn" '
            f'onclick="event.stopPropagation();openDatePicker(event,\'{uuid}\')" '
            f'title="Set due date">'
            f'<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            f'<rect x="3" y="4" width="18" height="18" rx="2"/>'
            f'<line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>'
            f'<line x1="3" y1="10" x2="21" y2="10"/>'
            f'</svg></button>'
        )
    if is_today:
        meta += '<span class="task-today-pill">Today</span>'

    # Complete button
    if token:
        complete_href = f"things:///update?id={uuid}&amp;completed=true&amp;auth-token={escape(token)}"
    else:
        complete_href = f"things:///show?id={uuid}"

    # Notes preview (collapsed by default)
    notes_html = ''
    if notes_raw:
        notes_html = (
            f'<div class="task-notes" id="tnotes-{uuid}">'
            f'{escape(notes_raw[:500])}'
            f'</div>'
        )

    # Inline edit form (hidden by default)
    edit_html = (
        f'<div class="task-edit-form" id="tedit-{uuid}" style="display:none">'
        f'<input class="task-edit-input" id="tedit-title-{uuid}" type="text" value="{title}" />'
        f'<input class="task-edit-date" id="tedit-date-{uuid}" type="date" value="{escape(deadline_raw)}" />'
        f'<button class="task-edit-save" onclick="saveTaskEdit(\'{uuid}\')">Save</button>'
        f'<button class="task-edit-cancel" onclick="cancelTaskEdit(\'{uuid}\')">Cancel</button>'
        f'</div>'
    )

    return (
        f'<li class="task-item" data-uuid="{uuid}" data-title="{title}" draggable="true">'
        f'<span class="task-drag-handle" title="Drag to reorder">&#x2807;</span>'
        f'<a class="task-circle" href="{complete_href}" onclick="completeTask(event, this)"></a>'
        f'<div class="task-content">'
        f'<div class="task-main-row">'
        f'<span class="task-title">{title}</span>'
        f'{meta}'
        f'</div>'
        f'{notes_html}'
        f'{edit_html}'
        f'</div>'
        f'<div class="task-actions">'
        f'<button class="task-action-btn task-edit-btn" onclick="openTaskEdit(\'{uuid}\')" title="Edit">'
        f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
        f'<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>'
        f'</svg></button>'
        + (f'<button class="task-action-btn task-notes-btn" onclick="toggleTaskNotes(\'{uuid}\')" title="Notes">&#x1F4DD;</button>' if notes_raw else '')
        + f'<button class="task-action-btn task-delete-btn" onclick="deleteTask(\'{uuid}\', this)" title="Delete">'
        f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        f'<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/>'
        f'</svg></button>'
        f'</div>'
        f'</li>'
    )


def _area_section(area_name, tasks, prefix, token, show_project=True, area_uuid=''):
    """Build a collapsible area group."""
    area_id = prefix + area_name.replace(' ', '-').replace('(', '').replace(')', '').lower()
    area_esc = escape(area_name)
    things_link = ''
    if area_uuid:
        href = f"things:///show?id={escape(area_uuid)}"
        things_link = (
            f'<a class="area-open-btn" href="{href}" onclick="event.stopPropagation()" title="Open in Things">'
            f'<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
            f'<polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>'
            f'</svg></a>'
        )
    lines = []
    lines.append(f'<div class="area-group" data-area-id="{area_id}">')
    lines.append(
        f'<div class="area-header" onclick="toggleAreaSection(\'{area_id}\')">'
        f'<span class="area-drag-handle">&#x2807;</span>'
        f'<span class="area-header-label">{area_esc}</span>'
        f'<span class="area-count">{len(tasks)}</span>'
        f'{things_link}'
        f'<span class="area-chevron" id="area-chevron-{area_id}">&#9662;</span>'
        f'</div>'
    )
    lines.append(f'<ul class="task-list area-body" id="area-body-{area_id}">')
    for task in tasks:
        lines.append(build_task_li(task, token, show_project=show_project))
    lines.append('</ul></div>')
    return '\n'.join(lines)


def build_things_html(things_data, auth_token=''):
    """Build the full Things tasks section: Today, Upcoming, Projects."""
    today    = things_data.get("today", [])
    upcoming = things_data.get("upcoming", [])
    projects = things_data.get("projects", [])
    areas    = things_data.get("areas", {})  # name -> uuid

    if not today and not upcoming and not projects:
        return '<div class="card"><h3>Tasks</h3><p class="muted">No tasks found.</p></div>'

    parts = []

    # ── Weekly stats strip (populated by JS) ──
    parts.append('<div class="task-stats-strip" id="weeklySummary"></div>')

    # ── Add-task row ──
    all_areas, seen = [], set()
    for task in today + upcoming:
        a = task.get("area", "")
        if a and a not in seen:
            all_areas.append(a); seen.add(a)
    for p in projects:
        a = p.get("area", "")
        if a and a not in seen:
            all_areas.append(a); seen.add(a)

    # Areas and projects (alphabetized)
    area_options = sorted(all_areas, key=lambda x: x.lower())
    project_options = sorted([p["title"] for p in projects], key=lambda x: x.lower())

    # Build a single alphabetized list of destinations
    all_options = []
    for area in area_options:
        all_options.append((area.lower(), area, area))
    for title in project_options:
        all_options.append((title.lower(), title, title))
    all_options.append(('inbox', 'Inbox', 'inbox'))
    all_options.sort(key=lambda x: x[0])

    options = ''
    for _, label, value in all_options:
        options += f'<option value="{escape(value)}">{escape(label)}</option>'
    options += '<option disabled>─────────</option>'
    options += '<option value="today">Due: Today</option>'
    options += '<option value="__new__">+ New category\u2026</option>'

    parts.append(
        '<div class="add-task-row">'
        '<input type="text" class="add-task-input" id="newTaskInput" '
        'placeholder="New task\u2026" onkeydown="if(event.key===\'Enter\')addTask()">'
        f'<select class="add-task-list" id="newTaskList" onchange="if(this.value===\'__new__\')showNewCategoryInput()">{options}</select>'
        '<button class="add-task-btn" onclick="addTask()" title="Add task">+'
        '</button></div>'
        '<div class="add-task-row" id="newCategoryWrap" style="display:none;margin-top:6px;">'
        '<input type="text" class="add-task-input" id="newCategoryInput" placeholder="Category name\u2026" '
        'onkeydown="if(event.key===\'Enter\')confirmNewCategory();else if(event.key===\'Escape\')cancelNewCategory()">'
        '<button class="add-task-btn" onclick="confirmNewCategory()" title="Add category" style="background:var(--green)">&#10003;</button>'
        '<button class="add-task-btn" onclick="cancelNewCategory()" title="Cancel" style="background:var(--border);color:var(--text-muted)">&times;</button>'
        '</div>'
    )

    has_projects = bool(projects)

    # ── TODAY section (expanded by default) ──
    today_date = date.today()
    overdue_tasks = []
    normal_tasks = []
    for task in today:
        dl_str = task.get("deadline", "")
        if dl_str:
            try:
                dl = datetime.strptime(dl_str, '%Y-%m-%d').date()
                if dl < today_date:
                    overdue_tasks.append(task)
                    continue
            except ValueError:
                pass
        normal_tasks.append(task)

    today_count = len(today)
    parts.append(
        f'<div class="task-main-section" id="section-today">'
        f'<div class="task-main-section-header" onclick="toggleMainSection(\'today\')">'
        f'<span class="task-main-section-title">Today</span>'
        f'<span class="task-main-section-count">{today_count}</span>'
        f'<span class="task-main-section-chevron" id="main-chevron-today">&#9662;</span>'
        f'</div>'
        f'<div class="task-main-section-body" id="main-body-today">'
    )
    if overdue_tasks:
        parts.append('<div class="task-overdue-section">')
        parts.append(_area_section("Overdue", overdue_tasks, 'overdue-', auth_token,
                                   show_project=True))
        parts.append('</div>')
    if normal_tasks:
        today_by_area = {}
        for task in normal_tasks:
            today_by_area.setdefault(task.get("area", "(No Area)"), []).append(task)
        for area_name, tasks in sorted(today_by_area.items(), key=lambda x: x[0].lower()):
            parts.append(_area_section(area_name, tasks, '', auth_token,
                                       area_uuid=areas.get(area_name, '')))
    if not overdue_tasks and not normal_tasks:
        parts.append('<p class="muted" style="padding:16px 0">No tasks for today.</p>')
    parts.append('</div></div>')  # close section-body + section-today

    # ── UPCOMING section (collapsed by default) ──
    upcoming_count = len(upcoming)
    parts.append(
        f'<div class="task-main-section" id="section-upcoming">'
        f'<div class="task-main-section-header" onclick="toggleMainSection(\'upcoming\')">'
        f'<span class="task-main-section-title">Upcoming</span>'
        f'<span class="task-main-section-count">{upcoming_count}</span>'
        f'<span class="task-main-section-chevron collapsed" id="main-chevron-upcoming">&#9662;</span>'
        f'</div>'
        f'<div class="task-main-section-body section-collapsed" id="main-body-upcoming" style="max-height:0">'
    )
    if upcoming:
        buckets = _bucket_by_time(upcoming)
        for bucket_name, tasks in buckets:
            parts.append(_area_section(bucket_name, tasks, 'upcoming-', auth_token,
                                       show_project=True))
    else:
        parts.append('<p class="muted" style="padding:16px 0">No upcoming tasks.</p>')
    parts.append('</div></div>')  # close section-body + section-upcoming

    # ── PROJECTS section (collapsed by default) ──
    if has_projects:
        proj_task_count = sum(len(p.get("tasks", [])) for p in projects)
        parts.append(
            f'<div class="task-main-section" id="section-projects">'
            f'<div class="task-main-section-header" onclick="toggleMainSection(\'projects\')">'
            f'<span class="task-main-section-title">Projects</span>'
            f'<span class="task-main-section-count">{proj_task_count}</span>'
            f'<span class="task-main-section-chevron collapsed" id="main-chevron-projects">&#9662;</span>'
            f'</div>'
            f'<div class="task-main-section-body section-collapsed" id="main-body-projects" style="max-height:0">'
        )

        # Group projects by area, preserving order from Things
        area_order = []
        projects_by_area = {}
        for proj in projects:
            a = proj["area"] or "(No Area)"
            if a not in projects_by_area:
                area_order.append(a)
                projects_by_area[a] = []
            projects_by_area[a].append(proj)

        for area_name in area_order:
            area_projs = projects_by_area[area_name]
            area_slug = area_name.replace(' ', '-').replace('(', '').replace(')', '').lower()
            area_esc = escape(area_name)
            area_proj_id = 'proj-area-' + area_slug

            parts.append(f'<div class="project-area-group" id="{area_proj_id}">')
            parts.append(
                f'<div class="project-area-header" onclick="toggleProjectAreaSection(\'{area_proj_id}\')">'
                f'<span class="area-drag-handle" title="Drag to reorder">&#x2807;</span>'
                f'<span class="project-area-label">{area_esc}</span>'
                f'<span class="area-count">{len(area_projs)}</span>'
                f'<button class="add-project-btn" onclick="event.stopPropagation();showNewProjectForm(\'{escape(area_name)}\')" title="New project in {area_esc}">+</button>'
                f'<span class="area-chevron" id="area-chevron-{area_proj_id}">&#9662;</span>'
                f'</div>'
            )
            parts.append(f'<div class="project-area-body" id="proj-area-body-{area_slug}">')

            for proj in area_projs:
                puuid = escape(proj["uuid"])
                ptitle = escape(proj["title"])
                pnotes = escape(proj.get("notes", ""))
                tasks = proj.get("tasks", [])
                open_count = len(tasks)
                proj_id = 'proj-' + proj["uuid"].replace('-', '')

                things_href = f"things:///show?id={puuid}"
                parts.append(f'<div class="project-group" id="{proj_id}">')
                parts.append(
                    f'<div class="project-header" onclick="toggleProjectSection(\'{proj_id}\')">'
                    f'<span class="proj-drag-handle" title="Drag to reorder">&#x2807;</span>'
                    f'<span class="project-title">{ptitle}</span>'
                    f'<span class="area-count">{open_count}</span>'
                    f'<a class="project-open-btn" href="{things_href}" onclick="event.stopPropagation()" title="Open in Things">'
                    f'<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                    f'<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
                    f'<polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>'
                    f'</svg></a>'
                    f'<span class="area-chevron" id="area-chevron-{proj_id}">&#9662;</span>'
                    f'</div>'
                )
                if pnotes.strip():
                    parts.append(f'<div class="project-notes">{pnotes}</div>')
                parts.append(f'<ul class="task-list area-body" id="area-body-{proj_id}">')
                if tasks:
                    for task in tasks:
                        parts.append(build_task_li(task, auth_token, show_project=False))
                else:
                    parts.append('<li class="task-item-empty">No open tasks</li>')
                parts.append('</ul></div>')

            parts.append('</div></div>')  # close project-area-body + project-area-group

        # New project form (hidden, shown by JS)
        parts.append(
            '<div class="new-project-form" id="newProjectForm" style="display:none">'
            '<div class="new-project-form-inner">'
            '<div class="new-project-area-label" id="newProjectAreaLabel"></div>'
            '<input type="text" class="add-task-input" id="newProjectTitle" placeholder="Project name\u2026" '
            'onkeydown="if(event.key===\'Enter\')confirmNewProject();else if(event.key===\'Escape\')cancelNewProject()">'
            '<div class="new-project-actions">'
            '<button class="add-task-btn" onclick="confirmNewProject()" style="background:var(--green);width:auto;padding:0 14px;font-size:0.85em">Create</button>'
            '<button class="add-task-btn" onclick="cancelNewProject()" style="background:var(--border);color:var(--text-muted);width:auto;padding:0 14px;font-size:0.85em">&times; Cancel</button>'
            '</div></div>'
            '</div>'
        )
        parts.append('</div></div>')  # close section-body + section-projects

    return '\n'.join(parts)
