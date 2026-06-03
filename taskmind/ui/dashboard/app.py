"""FastAPI web dashboard for TaskMind."""
import os
import json
from datetime import date, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from taskmind.database import (
    init_db, get_activities_for_date, get_project_summary,
    get_total_tracked_today, get_timesheet_for_date, search_activities,
    save_timesheet_entries, get_db,
)
from taskmind.processing.timesheet import generate_timesheet
from taskmind.processing.recap import generate_recap
from taskmind.config import load_config, load_projects, PROJECTS_FILE, CONFIG_FILE
from taskmind.daemon import is_daemon_running

app = FastAPI(title="TaskMind Dashboard")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

init_db()


def _read_template(name):
    with open(os.path.join(TEMPLATES_DIR, name), "r") as f:
        return f.read()


# --- Pages ---

@app.get("/", response_class=HTMLResponse)
def home():
    return _read_template("index.html")


@app.get("/timesheet", response_class=HTMLResponse)
def timesheet_page():
    return _read_template("index.html")


@app.get("/search", response_class=HTMLResponse)
def search_page():
    return _read_template("index.html")


@app.get("/settings", response_class=HTMLResponse)
def settings_page():
    return _read_template("index.html")


# --- API ---

@app.get("/api/status")
def api_status():
    total = get_total_tracked_today()
    h, m = divmod(total // 60, 60)
    return {"running": is_daemon_running(), "today_seconds": total, "today_display": f"{h}h {m}m"}


@app.get("/api/summary/{target_date}")
def api_summary(target_date: str):
    summary = get_project_summary(target_date)
    total = sum(s["total_seconds"] for s in summary)
    return {"date": target_date, "total_seconds": total, "projects": summary}


@app.get("/api/timeline/{target_date}")
def api_timeline(target_date: str):
    activities = get_activities_for_date(target_date)
    # Group into 15-min slots for timeline
    slots = {}
    for a in activities:
        if a["is_idle"]:
            continue
        ts = a["timestamp"]
        if len(ts) > 15:
            hour_min = ts[11:16]
            # Round to 15-min slot
            h, m = int(hour_min[:2]), int(hour_min[3:5])
            slot = f"{h:02d}:{(m // 15) * 15:02d}"
            if slot not in slots:
                slots[slot] = {"slot": slot, "project": a["project_name"] or "Unclassified", "count": 0}
            slots[slot]["count"] += 1
            slots[slot]["project"] = a["project_name"] or "Unclassified"
    return {"date": target_date, "timeline": sorted(slots.values(), key=lambda x: x["slot"])}


@app.get("/api/timesheet/{target_date}")
def api_timesheet(target_date: str):
    entries = generate_timesheet(target_date)
    return {"date": target_date, "entries": entries}


@app.get("/api/search")
def api_search(q: str = ""):
    if not q:
        return {"results": []}
    results = search_activities(q)
    return {"results": results[:30]}


@app.get("/api/projects")
def api_projects():
    return {"projects": load_projects()}


@app.post("/api/projects/add")
async def api_add_project(request: Request):
    import yaml
    data = await request.json()
    name = data.get("name", "").strip()
    keywords = data.get("keywords", [])
    if not name or not keywords:
        return JSONResponse({"error": "Name and keywords required"}, 400)

    projects = load_projects()
    projects.append({"name": name, "matchers": [{"type": "window_title", "contains": keywords}]})
    with open(PROJECTS_FILE, "w") as f:
        yaml.dump({"projects": projects}, f, default_flow_style=False, sort_keys=False)
    return {"ok": True}


@app.post("/api/projects/remove")
async def api_remove_project(request: Request):
    import yaml
    data = await request.json()
    index = data.get("index", -1)
    projects = load_projects()
    if 0 <= index < len(projects):
        projects.pop(index)
        with open(PROJECTS_FILE, "w") as f:
            yaml.dump({"projects": projects}, f, default_flow_style=False, sort_keys=False)
        return {"ok": True}
    return JSONResponse({"error": "Invalid index"}, 400)


@app.get("/api/recap/{target_date}")
def api_recap(target_date: str):
    return {"date": target_date, "text": generate_recap(target_date)}


@app.get("/api/recordings")
def api_recordings():
    from taskmind.database import get_recordings
    return {"recordings": get_recordings()}


@app.get("/api/search-transcripts")
def api_search_transcripts(q: str = ""):
    if not q:
        return {"results": []}
    from taskmind.database import search_transcripts
    return {"results": search_transcripts(q)}


def run_dashboard():
    """Start the dashboard server."""
    import uvicorn
    config = load_config()
    host = config["dashboard"]["host"]
    port = config["dashboard"]["port"]
    uvicorn.run(app, host=host, port=port, log_level="error")


if __name__ == "__main__":
    run_dashboard()
