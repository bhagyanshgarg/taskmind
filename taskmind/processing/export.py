"""Export integrations - Clockify, Toggl, Jira Tempo, CSV, JSON."""
import os
import json
import csv
import io
from datetime import date
from taskmind.processing.timesheet import generate_timesheet
from taskmind.config import load_config, CONFIG_DIR

INTEGRATIONS_FILE = os.path.join(CONFIG_DIR, "integrations.yaml")


def export_csv(target_date=None, output_path=None):
    """Export timesheet as CSV. Returns CSV string or writes to file."""
    entries = generate_timesheet(target_date)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["date", "project_name", "start_time", "end_time", "duration_minutes", "description"])
    writer.writeheader()
    writer.writerows(entries)
    result = output.getvalue()
    if output_path:
        with open(output_path, "w") as f:
            f.write(result)
    return result


def export_json(target_date=None, output_path=None):
    """Export timesheet as JSON."""
    entries = generate_timesheet(target_date)
    result = json.dumps(entries, indent=2)
    if output_path:
        with open(output_path, "w") as f:
            f.write(result)
    return result


def export_clockify(target_date=None, api_key=None, workspace_id=None):
    """Export to Clockify API."""
    import urllib.request
    import urllib.error

    if not api_key or not workspace_id:
        config = _load_integrations()
        api_key = api_key or config.get("clockify", {}).get("api_key")
        workspace_id = workspace_id or config.get("clockify", {}).get("workspace_id")

    if not api_key or not workspace_id:
        return {"error": "Clockify api_key and workspace_id required. Set in ~/.config/taskmind/integrations.yaml"}

    entries = generate_timesheet(target_date)
    results = []
    for e in entries:
        start_dt = "{}T{}:00Z".format(e["date"], e["start_time"])
        end_dt = "{}T{}:00Z".format(e["date"], e["end_time"])
        payload = json.dumps({
            "start": start_dt,
            "end": end_dt,
            "description": "{} - {}".format(e["project_name"], e.get("description", "")),
        }).encode()

        req = urllib.request.Request(
            "https://api.clockify.me/api/v1/workspaces/{}/time-entries".format(workspace_id),
            data=payload,
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        )
        try:
            resp = urllib.request.urlopen(req)
            results.append({"status": "ok", "entry": e["start_time"]})
        except urllib.error.HTTPError as err:
            results.append({"status": "error", "entry": e["start_time"], "error": str(err)})

    return {"pushed": len([r for r in results if r["status"] == "ok"]), "failed": len([r for r in results if r["status"] == "error"]), "results": results}


def export_toggl(target_date=None, api_token=None, workspace_id=None):
    """Export to Toggl Track API."""
    import urllib.request
    import urllib.error
    import base64

    if not api_token:
        config = _load_integrations()
        api_token = config.get("toggl", {}).get("api_token")
        workspace_id = workspace_id or config.get("toggl", {}).get("workspace_id")

    if not api_token:
        return {"error": "Toggl api_token required. Set in ~/.config/taskmind/integrations.yaml"}

    entries = generate_timesheet(target_date)
    auth = base64.b64encode("{}:api_token".format(api_token).encode()).decode()
    results = []

    for e in entries:
        start_dt = "{}T{}:00+00:00".format(e["date"], e["start_time"])
        payload = json.dumps({
            "description": "{} - {}".format(e["project_name"], e.get("description", "")),
            "start": start_dt,
            "duration": e["duration_minutes"] * 60,
            "created_with": "taskmind",
            "workspace_id": int(workspace_id) if workspace_id else None,
        }).encode()

        req = urllib.request.Request(
            "https://api.track.toggl.com/api/v9/time_entries",
            data=payload,
            headers={"Authorization": "Basic {}".format(auth), "Content-Type": "application/json"},
        )
        try:
            resp = urllib.request.urlopen(req)
            results.append({"status": "ok", "entry": e["start_time"]})
        except urllib.error.HTTPError as err:
            results.append({"status": "error", "entry": e["start_time"], "error": str(err)})

    return {"pushed": len([r for r in results if r["status"] == "ok"]), "failed": len([r for r in results if r["status"] == "error"])}


def export_jira_tempo(target_date=None, api_token=None, account_id=None):
    """Export to Jira Tempo API."""
    import urllib.request
    import urllib.error

    if not api_token:
        config = _load_integrations()
        api_token = config.get("jira_tempo", {}).get("api_token")
        account_id = account_id or config.get("jira_tempo", {}).get("account_id")

    if not api_token or not account_id:
        return {"error": "Jira Tempo api_token and account_id required. Set in ~/.config/taskmind/integrations.yaml"}

    entries = generate_timesheet(target_date)
    results = []

    for e in entries:
        payload = json.dumps({
            "authorAccountId": account_id,
            "startDate": e["date"],
            "startTime": e["start_time"] + ":00",
            "timeSpentSeconds": e["duration_minutes"] * 60,
            "description": "{} - {}".format(e["project_name"], e.get("description", "")),
        }).encode()

        req = urllib.request.Request(
            "https://api.tempo.io/4/worklogs",
            data=payload,
            headers={"Authorization": "Bearer {}".format(api_token), "Content-Type": "application/json"},
        )
        try:
            resp = urllib.request.urlopen(req)
            results.append({"status": "ok"})
        except urllib.error.HTTPError as err:
            results.append({"status": "error", "error": str(err)})

    return {"pushed": len([r for r in results if r["status"] == "ok"]), "failed": len([r for r in results if r["status"] == "error"])}


def _load_integrations():
    """Load integrations config."""
    import yaml
    if not os.path.exists(INTEGRATIONS_FILE):
        return {}
    with open(INTEGRATIONS_FILE, "r") as f:
        return yaml.safe_load(f) or {}
