"""Git activity watcher - monitors repos for commits and branch switches."""
import os
import subprocess
from datetime import datetime
from taskmind.database import get_db, init_db
from taskmind.config import load_config


def _run_git(repo_path, args):
    """Run git command in repo, return stdout."""
    try:
        result = subprocess.run(
            ["git"] + args, capture_output=True, text=True, timeout=5, cwd=repo_path
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_current_branch(repo_path):
    """Get current branch name."""
    return _run_git(repo_path, ["branch", "--show-current"])


def get_recent_commits(repo_path, since_minutes=15):
    """Get commits from the last N minutes."""
    since = "--since='{} minutes ago'".format(since_minutes)
    output = _run_git(repo_path, ["log", "--oneline", "--since={} minutes ago".format(since_minutes), "--format=%H|||%s|||%ai"])
    if not output:
        return []
    commits = []
    for line in output.strip().split("\n"):
        parts = line.split("|||")
        if len(parts) == 3:
            commits.append({"hash": parts[0][:8], "message": parts[1], "date": parts[2]})
    return commits


def scan_repos():
    """Scan configured repos for new git activity. Returns list of events."""
    config = load_config()
    repos = config.get("git", {}).get("watch_repos", [])
    if not repos:
        return []

    events = []
    conn = get_db()

    for repo_path in repos:
        repo_path = os.path.expanduser(repo_path)
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            continue

        repo_name = os.path.basename(repo_path)
        branch = get_current_branch(repo_path)
        commits = get_recent_commits(repo_path, since_minutes=15)

        for commit in commits:
            # Check if already logged
            existing = conn.execute(
                "SELECT id FROM git_events WHERE repo_path=? AND message=? AND event_type='commit'",
                (repo_path, commit["message"])
            ).fetchone()
            if existing:
                continue

            ts = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO git_events (timestamp, repo_path, event_type, branch, message, files_changed, project_id) VALUES (?,?,?,?,?,?,?)",
                (ts, repo_path, "commit", branch, commit["message"], 0, None)
            )
            events.append({"repo": repo_name, "branch": branch, "message": commit["message"]})

    conn.commit()
    conn.close()
    return events


def get_git_events_for_date(target_date=None):
    """Get all git events for a date."""
    from datetime import date as d
    if target_date is None:
        target_date = d.today().isoformat()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM git_events WHERE timestamp LIKE ? ORDER BY timestamp",
        (target_date + "%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_git_summary_for_timesheet(target_date=None):
    """Get git commit messages grouped by repo for timesheet enrichment."""
    events = get_git_events_for_date(target_date)
    by_repo = {}
    for e in events:
        repo = os.path.basename(e["repo_path"])
        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append(e["message"])
    return by_repo
