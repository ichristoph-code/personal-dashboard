"""Due Soon card — compact view of tasks with approaching deadlines."""

from datetime import date, datetime
from html import escape

from .tasks import _smart_deadline, build_task_li


def build_due_soon_html(things_data, auth_token=""):
    """Build a compact card showing tasks that are due or due soon.

    Pulls from things_data["today"] and things_data["upcoming"],
    groups them by deadline urgency, and renders a compact list.
    Returns an HTML string (empty string if no deadlined tasks).
    """
    if not things_data:
        return ""

    today_tasks = things_data.get("today") or []
    upcoming_tasks = things_data.get("upcoming") or []

    # Collect all tasks that have a deadline, deduplicating by uuid
    seen = set()
    deadlined = []
    for task in today_tasks + upcoming_tasks:
        dl = task.get("deadline")
        if not dl or task.get("uuid") in seen:
            continue
        seen.add(task["uuid"])
        deadlined.append(task)

    # Sort by deadline date
    def _dl_sort(t):
        try:
            return datetime.strptime(t["deadline"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return date.max
    deadlined.sort(key=_dl_sort)

    if not deadlined:
        return (
            '<div class="card due-soon-card draggable-card" data-card-id="due-soon">'
            '<span class="card-drag-handle" title="Drag to reorder">&#x2807;</span>'
            '<h3>Due Soon</h3>'
            '<p class="empty-state">No upcoming deadlines</p>'
            '</div>'
        )

    # Group into buckets
    buckets = {
        "Overdue": [],
        "Today": [],
        "Tomorrow": [],
        "This Week": [],
        "Next Week": [],
        "Later": [],
    }
    for task in deadlined:
        label, css_class = _smart_deadline(task["deadline"])
        if not label:
            continue
        if css_class == "deadline-overdue":
            buckets["Overdue"].append((task, label, css_class))
        elif css_class == "deadline-today":
            buckets["Today"].append((task, label, css_class))
        elif css_class == "deadline-tomorrow":
            buckets["Tomorrow"].append((task, label, css_class))
        elif css_class == "deadline-week":
            buckets["This Week"].append((task, label, css_class))
        else:
            # deadline-later covers next week and beyond
            try:
                dl = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
                delta = (dl - date.today()).days
            except (ValueError, TypeError):
                delta = 999
            if delta <= 13:
                buckets["Next Week"].append((task, label, css_class))
            else:
                buckets["Later"].append((task, label, css_class))

    # Count urgent tasks for the header badge
    urgent = len(buckets["Overdue"]) + len(buckets["Today"])
    badge = ""
    if urgent:
        badge = f' <span class="due-soon-badge">{urgent}</span>'

    # Build HTML
    lines = [
        '<div class="card due-soon-card draggable-card" data-card-id="due-soon">',
        '<span class="card-drag-handle" title="Drag to reorder">&#x2807;</span>',
        f'<h3>Due Soon{badge}</h3>',
    ]

    for bucket_name in ["Overdue", "Today", "Tomorrow", "This Week", "Next Week", "Later"]:
        items = buckets[bucket_name]
        if not items:
            continue

        bucket_css = bucket_name.lower().replace(" ", "-")
        lines.append(f'<div class="due-bucket due-bucket-{bucket_css}">')
        lines.append(f'<div class="due-bucket-label">{bucket_name}'
                     f'<span class="due-bucket-count">{len(items)}</span></div>')
        lines.append('<ul class="due-list">')

        for task, dl_label, dl_class in items:
            title = escape(task.get("title", ""))
            project = task.get("project") or ""
            uuid = task.get("uuid", "")

            # Things URL for completing the task
            complete_url = f"things:///show?id={uuid}" if uuid else "#"

            project_html = ""
            if project:
                project_html = f'<span class="due-project">{escape(project)}</span>'

            pill_html = f'<span class="task-deadline {dl_class}">{escape(dl_label)}</span>'

            lines.append(
                f'<li class="due-item" data-uuid="{escape(uuid)}">'
                f'<a class="task-circle" href="{complete_url}" title="Open in Things"></a>'
                f'<span class="due-title">{title}</span>'
                f'{project_html}'
                f'{pill_html}'
                f'</li>'
            )

        lines.append('</ul>')
        lines.append('</div>')

    lines.append('</div>')
    return "\n".join(lines)


def build_due_today_html(things_data, auth_token=""):
    """Build a card showing only tasks that are due today.

    Pulls from all task sources (today, upcoming, projects) and filters
    to tasks whose deadline == today. Includes overdue tasks as well.
    """
    if not things_data:
        return ""

    today_str = date.today().strftime("%Y-%m-%d")
    today_date = date.today()

    # Gather tasks from all sources
    all_tasks = []
    all_tasks.extend(things_data.get("today") or [])
    all_tasks.extend(things_data.get("upcoming") or [])
    for proj in (things_data.get("projects") or []):
        for task in proj.get("tasks", []):
            # Add project name for context
            t = dict(task)
            t.setdefault("project", proj["title"])
            all_tasks.append(t)

    # Deduplicate by uuid, filter to due today + overdue
    seen = set()
    due_today = []
    overdue = []
    for task in all_tasks:
        dl = task.get("deadline")
        if not dl or task.get("uuid") in seen:
            continue
        seen.add(task["uuid"])
        try:
            dl_date = datetime.strptime(dl, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if dl_date == today_date:
            due_today.append(task)
        elif dl_date < today_date:
            overdue.append(task)

    total = len(due_today) + len(overdue)

    if total == 0:
        return (
            '<div class="card due-today-card draggable-card" data-card-id="due-today">'
            '<span class="card-drag-handle" title="Drag to reorder">&#x2807;</span>'
            '<h3>Due Today</h3>'
            '<p class="empty-state">Nothing due today</p>'
            '</div>'
        )

    badge = f' <span class="due-soon-badge">{total}</span>'

    lines = [
        '<div class="card due-today-card draggable-card" data-card-id="due-today">',
        '<span class="card-drag-handle" title="Drag to reorder">&#x2807;</span>',
        f'<h3>Due Today{badge}</h3>',
    ]

    # Overdue section first
    if overdue:
        lines.append('<div class="due-bucket due-bucket-overdue">')
        lines.append(f'<div class="due-bucket-label">Overdue'
                     f'<span class="due-bucket-count">{len(overdue)}</span></div>')
        lines.append('<ul class="task-list">')
        for task in overdue:
            lines.append(build_task_li(task, auth_token))
        lines.append('</ul></div>')

    # Due today section
    if due_today:
        lines.append('<div class="due-bucket due-bucket-today">')
        lines.append(f'<div class="due-bucket-label">Today'
                     f'<span class="due-bucket-count">{len(due_today)}</span></div>')
        lines.append('<ul class="task-list">')
        for task in due_today:
            lines.append(build_task_li(task, auth_token))
        lines.append('</ul></div>')

    lines.append('</div>')
    return "\n".join(lines)
