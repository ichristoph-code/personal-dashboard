"""Things 3 task data via SQLite database with cache fallback."""

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from . import atomic_write_json

THINGS_DB_PATH = Path.home() / "Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-U4LLW/Things Database.thingsdatabase/main.sqlite"

_CACHE_FILE = Path(__file__).parent.parent / ".things_cache.json"
_CACHE_MAX_AGE = 6 * 3600  # 6 hours


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data):
    atomic_write_json(_CACHE_FILE, data)


def _fmt_deadline(deadline):
    if not deadline:
        return None
    d = str(deadline)
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def get_things_tasks(force_refresh=False):
    """Get tasks from Things 3 via SQLite database, with cache fallback.

    Returns:
        {
          "today": [...],
          "upcoming": [...],
          "projects": [ {"uuid", "title", "area", "notes", "tasks": [...]} ]
        }
    """
    cache = _load_cache()
    now = time.time()
    cached = cache.get("tasks")

    if not THINGS_DB_PATH.exists():
        print("  Things 3 database not found.")
        if cached and (now - cached["ts"]) < _CACHE_MAX_AGE:
            print(f"  Using cached Things data ({int((now - cached['ts'])/60)} min old)")
            return cached["data"]
        return {"today": [], "upcoming": [], "projects": [], "areas": {}}

    try:
        with sqlite3.connect(str(THINGS_DB_PATH), timeout=10) as conn:
            c = conn.cursor()

            # ── Today ──
            c.execute('''
                SELECT t.uuid, t.title, t.deadline, t.notes,
                       COALESCE(proj.title, '') AS project_name,
                       COALESCE(direct_area.title, proj_area.title, '(No Area)') AS area_name,
                       COALESCE(direct_area."index", proj_area."index", 999999) AS area_index
                FROM TMTask t
                LEFT JOIN TMArea direct_area ON t.area = direct_area.uuid
                LEFT JOIN TMTask proj ON t.project = proj.uuid AND proj.type = 1
                LEFT JOIN TMArea proj_area ON proj.area = proj_area.uuid
                WHERE t.trashed=0 AND t.status=0 AND t.start=1 AND t.type=0
                      AND t.title != ''
                ORDER BY area_index ASC, t.todayIndex ASC
            ''')
            today = []
            for uuid, title, deadline, notes, project_name, area_name, _ in c.fetchall():
                task = {"title": title, "uuid": uuid, "area": area_name}
                if deadline:
                    task["deadline"] = _fmt_deadline(deadline)
                if project_name:
                    task["project"] = project_name
                if notes:
                    task["notes"] = notes
                today.append(task)

            # ── Upcoming (deadline-based) ──
            today_int = int(datetime.now().strftime('%Y%m%d'))
            c.execute('''
                SELECT t.uuid, t.title, t.deadline, t.notes,
                       COALESCE(proj.title, '') AS project_name,
                       COALESCE(direct_area.title, proj_area.title, '(No Area)') AS area_name,
                       COALESCE(direct_area."index", proj_area."index", 999999) AS area_index
                FROM TMTask t
                LEFT JOIN TMArea direct_area ON t.area = direct_area.uuid
                LEFT JOIN TMTask proj ON t.project = proj.uuid AND proj.type = 1
                LEFT JOIN TMArea proj_area ON proj.area = proj_area.uuid
                WHERE t.trashed=0 AND t.status=0 AND t.type=0
                      AND t.deadline IS NOT NULL AND t.deadline >= ?
                      AND t.title != ''
                ORDER BY area_index ASC, t.deadline ASC
                LIMIT 30
            ''', (today_int,))
            upcoming = []
            for uuid, title, deadline, notes, project_name, area_name, _ in c.fetchall():
                task = {"title": title, "uuid": uuid, "area": area_name}
                if deadline:
                    task["deadline"] = _fmt_deadline(deadline)
                if project_name:
                    task["project"] = project_name
                if notes:
                    task["notes"] = notes
                upcoming.append(task)

            # ── Projects with their open tasks ──
            c.execute('''
                SELECT p.uuid, p.title,
                       COALESCE(a.title, '') AS area_name,
                       COALESCE(a."index", 999999) AS area_index,
                       p.notes
                FROM TMTask p
                LEFT JOIN TMArea a ON p.area = a.uuid
                WHERE p.trashed=0 AND p.status=0 AND p.type=1
                      AND p.title != ''
                ORDER BY area_index ASC, p."index" ASC
            ''')
            project_rows = c.fetchall()

            projects = []
            for puuid, ptitle, parea, _, pnotes in project_rows:
                c.execute('''
                    SELECT t.uuid, t.title, t.deadline, t.notes, t.start
                    FROM TMTask t
                    WHERE t.trashed=0 AND t.status=0 AND t.type=0
                          AND t.project=? AND t.title != ''
                    ORDER BY t."index" ASC
                ''', (puuid,))
                tasks = []
                for uuid, title, deadline, tnotes, start in c.fetchall():
                    task = {"title": title, "uuid": uuid}
                    if deadline:
                        task["deadline"] = _fmt_deadline(deadline)
                    if tnotes:
                        task["notes"] = tnotes
                    task["today"] = (start == 1)
                    tasks.append(task)
                projects.append({
                    "uuid": puuid,
                    "title": ptitle,
                    "area": parea,
                    "notes": pnotes or "",
                    "tasks": tasks,
                })

            # ── Area name → UUID map ──
            c.execute('SELECT uuid, title FROM TMArea')
            areas = {row[1].strip(): row[0] for row in c.fetchall()}

        result = {"today": today, "upcoming": upcoming, "projects": projects, "areas": areas}
        cache["tasks"] = {"ts": now, "data": result}
        _save_cache(cache)
        print(f"  Found {len(today)} Today, {len(upcoming)} upcoming, {len(projects)} projects")
        return result

    except Exception as e:
        print(f"  Things 3 error: {e}")
        if cached and (now - cached["ts"]) < _CACHE_MAX_AGE:
            age_min = int((now - cached["ts"]) / 60)
            print(f"  Using cached Things data ({age_min} min old)")
            return cached["data"]
        return {"today": [], "upcoming": [], "projects": [], "areas": {}}
