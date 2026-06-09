"""CLI tool for TaskMind."""
import os
import sys
import signal
import csv
import io
import click
from datetime import date, timedelta
from taskmind.config import load_config, PID_FILE, CONFIG_FILE, PROJECTS_FILE, ensure_dirs
from taskmind.database import (
    init_db, get_project_summary, get_total_tracked_today,
    get_activities_for_date, search_activities, get_timesheet_for_date,
    save_timesheet_entries,
)
from taskmind.processing.timesheet import generate_timesheet
from taskmind.processing.recap import generate_recap
from taskmind.daemon import is_daemon_running


@click.group()
def main():
    """TaskMind - Activity tracker and timesheet generator."""
    ensure_dirs()
    init_db()


@main.command()
def status():
    """Show daemon status and today's tracked hours."""
    running = is_daemon_running()
    total_sec = get_total_tracked_today()
    h, m = divmod(total_sec // 60, 60)

    status_icon = "●" if running else "○"
    status_text = "tracking" if running else "stopped"
    click.echo("{} TaskMind: {} | Today: {}h {}m".format(status_icon, status_text, h, m))

    summary = get_project_summary()
    if summary:
        click.echo("")
        for proj in summary:
            ph, pm = divmod(proj["total_seconds"] // 60, 60)
            name = proj["project_name"] or "Unclassified"
            click.echo("  • {}: {}h {}m".format(name, ph, pm))


@main.command()
def today():
    """Show today's activity recap."""
    click.echo(generate_recap())


@main.command()
def yesterday():
    """Show yesterday's activity recap."""
    d = (date.today() - timedelta(days=1)).isoformat()
    click.echo(generate_recap(d))


@main.command()
@click.option("--date", "-d", "target_date", default=None, help="End date (YYYY-MM-DD)")
def week(target_date):
    """Show this week's aggregated recap."""
    from taskmind.processing.recap import generate_weekly_recap
    click.echo(generate_weekly_recap(target_date))


@main.command()
@click.option("--date", "-d", "target_date", default=None, help="Date (YYYY-MM-DD)")
def recap(target_date):
    """Show daily recap (same as 'today' with optional date)."""
    if target_date is None:
        target_date = date.today().isoformat()
    click.echo(generate_recap(target_date))


@main.command()
@click.option("--date", "-d", "target_date", default=None, help="Date (YYYY-MM-DD)")
@click.option("--export", "-e", "export_fmt", type=click.Choice(["csv", "json"]), help="Export format")
def timesheet(target_date, export_fmt):
    """Generate or show timesheet for a day."""
    if target_date is None:
        target_date = date.today().isoformat()

    entries = generate_timesheet(target_date)
    if not entries:
        click.echo("No activity for {}.".format(target_date))
        return

    if export_fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["date", "project_name", "start_time", "end_time", "duration_minutes", "description"])
        writer.writeheader()
        writer.writerows(entries)
        click.echo(output.getvalue())
    elif export_fmt == "json":
        import json
        click.echo(json.dumps(entries, indent=2))
    else:
        click.echo("📋 Timesheet – {}".format(target_date))
        click.echo("")
        click.echo("{:<8} {:<8} {:<20} {:<6} {}".format("Start", "End", "Project", "Mins", "Description"))
        click.echo("-" * 70)
        total = 0
        for e in entries:
            click.echo("{:<8} {:<8} {:<20} {:<6} {}".format(
                e["start_time"], e["end_time"], e["project_name"][:19],
                e["duration_minutes"], (e["description"] or "")[:30],
            ))
            total += e["duration_minutes"]
        click.echo("-" * 70)
        click.echo("Total: {}h {}m".format(total // 60, total % 60))


@main.command()
@click.argument("query")
def search(query):
    """Search activities by keyword."""
    results = search_activities(query)
    if not results:
        click.echo("No results for '{}'.".format(query))
        return
    for r in results[:20]:
        click.echo("[{}] {} - {} ({})".format(
            r["timestamp"][:16], r["app_name"], r["window_title"][:50], r["project_name"] or "?"
        ))


@main.command()
def record():
    """Start audio recording."""
    from taskmind.capture.audio_recorder import start_recording, is_recording
    from taskmind.database import insert_recording
    from taskmind.utils.notifications import notify
    from datetime import datetime

    if is_recording():
        click.echo("⏺ Already recording. Run 'taskmind stop-recording' to stop.")
        return

    filepath = start_recording()
    if filepath:
        insert_recording(datetime.now().isoformat(), filepath)
        notify("🔴 Recording", "Audio recording started")
        click.echo("🔴 Recording started: {}".format(os.path.basename(filepath)))
        click.echo("   Run 'taskmind stop-recording' to stop.")
    else:
        click.echo("Error: Could not start recording. Install pulseaudio-utils or pipewire.")


@main.command(name="stop-recording")
def stop_recording_cmd():
    """Stop audio recording and transcribe."""
    from taskmind.capture.audio_recorder import stop_recording, is_recording
    from taskmind.database import update_recording
    from taskmind.processing.transcriber import transcribe
    from taskmind.utils.notifications import notify
    from datetime import datetime

    if not is_recording():
        click.echo("No active recording.")
        return

    result = stop_recording()
    if not result:
        click.echo("Error stopping recording.")
        return

    filepath, duration = result
    click.echo("⏹ Recording stopped ({} seconds)".format(duration))
    click.echo("  Transcribing...")

    transcript = transcribe(filepath)
    ended_at = datetime.now().isoformat()
    status = "done" if transcript else "failed"
    update_recording(filepath, ended_at, duration, transcript, status)

    if transcript and not transcript.startswith("["):
        notify("✅ Transcription Done", transcript[:100])
        click.echo("  ✅ Transcript ({} chars):".format(len(transcript)))
        click.echo("  {}".format(transcript[:200]))
    else:
        click.echo("  ⚠ {}".format(transcript))


@main.command()
def recordings():
    """List recent recordings."""
    from taskmind.database import get_recordings

    recs = get_recordings()
    if not recs:
        click.echo("No recordings yet. Run 'taskmind record' to start one.")
        return

    click.echo("Recent recordings:")
    click.echo("")
    for r in recs:
        dur = r.get("duration_seconds") or 0
        status = r.get("status", "?")
        has_transcript = "✓" if r.get("transcript") else "✗"
        click.echo("  [{}] {}s | {} | transcript: {}".format(
            r["started_at"][:16], dur, status, has_transcript
        ))
        if r.get("transcript"):
            click.echo("    {}".format(r["transcript"][:80]))


@main.command()
def start():
    """Start the daemon."""
    if is_daemon_running():
        click.echo("TaskMind is already running.")
        return
    # Fork daemon process
    pid = os.fork()
    if pid > 0:
        click.echo("TaskMind daemon started (PID {}).".format(pid))
        return
    # Child - become session leader and run
    os.setsid()
    from taskmind.daemon import run_daemon
    run_daemon()


@main.command()
def stop():
    """Stop the daemon."""
    if not os.path.exists(PID_FILE):
        click.echo("TaskMind is not running.")
        return
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        click.echo("TaskMind daemon stopped (PID {}).".format(pid))
    except (OSError, ValueError) as e:
        click.echo("Error stopping daemon: {}".format(e))


@main.command(name="git-watch")
@click.argument("repo_path", required=False)
def git_watch(repo_path):
    """Add a git repo to watch, or scan all watched repos now."""
    import yaml
    from taskmind.config import CONFIG_FILE

    config = load_config()
    repos = config.get("git", {}).get("watch_repos", [])

    if repo_path:
        repo_path = os.path.abspath(os.path.expanduser(repo_path))
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            click.echo("Not a git repo: {}".format(repo_path))
            return
        if repo_path not in repos:
            if "git" not in config:
                config["git"] = {"enabled": True, "watch_repos": []}
            config["git"]["watch_repos"].append(repo_path)
            with open(CONFIG_FILE, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            click.echo("✅ Now watching: {}".format(repo_path))
        else:
            click.echo("Already watching: {}".format(repo_path))
    else:
        from taskmind.capture.git_watcher import scan_repos
        events = scan_repos()
        if events:
            click.echo("New git events:")
            for e in events:
                click.echo("  • [{}] {} – {}".format(e["repo"], e["branch"], e["message"]))
        else:
            click.echo("No new git events.")
        if repos:
            click.echo("\nWatched repos:")
            for r in repos:
                click.echo("  • {}".format(r))
        else:
            click.echo("\nNo repos configured. Run: taskmind git-watch /path/to/repo")


@main.command()
@click.option("--to", "target", type=click.Choice(["csv", "json", "clockify", "toggl", "jira"]), required=True)
@click.option("--date", "-d", "target_date", default=None)
@click.option("--output", "-o", "output_path", default=None)
def export(target, target_date, output_path):
    """Export timesheet to CSV, JSON, Clockify, Toggl, or Jira Tempo."""
    from taskmind.processing.export import export_csv, export_json, export_clockify, export_toggl, export_jira_tempo

    if target_date is None:
        target_date = date.today().isoformat()

    if target == "csv":
        result = export_csv(target_date, output_path)
        if output_path:
            click.echo("✅ Exported to {}".format(output_path))
        else:
            click.echo(result)
    elif target == "json":
        result = export_json(target_date, output_path)
        if output_path:
            click.echo("✅ Exported to {}".format(output_path))
        else:
            click.echo(result)
    elif target == "clockify":
        result = export_clockify(target_date)
        if "error" in result:
            click.echo("❌ {}".format(result["error"]))
        else:
            click.echo("✅ Clockify: {} pushed, {} failed".format(result["pushed"], result["failed"]))
    elif target == "toggl":
        result = export_toggl(target_date)
        if "error" in result:
            click.echo("❌ {}".format(result["error"]))
        else:
            click.echo("✅ Toggl: {} pushed, {} failed".format(result["pushed"], result["failed"]))
    elif target == "jira":
        result = export_jira_tempo(target_date)
        if "error" in result:
            click.echo("❌ {}".format(result["error"]))
        else:
            click.echo("✅ Jira Tempo: {} pushed, {} failed".format(result["pushed"], result["failed"]))


@main.command()
def config():
    """Open config file in editor."""
    editor = os.environ.get("EDITOR", "nano")
    if not os.path.exists(CONFIG_FILE):
        # Create from default
        from taskmind.config import DEFAULT_CONFIG
        import yaml
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
    os.execvp(editor, [editor, CONFIG_FILE])


@main.command()
def projects():
    """List configured projects."""
    from taskmind.config import load_projects
    projs = load_projects()
    if not projs:
        click.echo("No projects configured.")
        click.echo("Run: taskmind add-project")
        return
    click.echo("Configured projects:")
    for p in projs:
        matchers = len(p.get("matchers", []))
        click.echo("  • {} ({} rules)".format(p["name"], matchers))


@main.command(name="add-project")
def add_project():
    """Interactively add a new project with matching rules."""
    import yaml
    from taskmind.config import PROJECTS_FILE, ensure_dirs

    ensure_dirs()
    click.echo("➕ Add a New Project")
    click.echo("─" * 40)
    click.echo("")

    name = click.prompt("Project name (e.g. 'Client Website', 'Meetings')")

    # Check for duplicate names
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, "r") as f:
            data = yaml.safe_load(f) or {}
        existing = [p["name"].lower() for p in data.get("projects", [])]
        if name.lower() in existing:
            click.echo("❌ Project '{}' already exists. Use 'taskmind edit-project' to modify it.".format(name))
            return

    click.echo("")
    click.echo("Now let's add rules to detect this project.")
    click.echo("TaskMind matches by window title and app name.")
    click.echo("")
    click.echo("Examples:")
    click.echo("  - 'Gmail' matches any window with Gmail in title")
    click.echo("  - 'zoom' matches the Zoom app")
    click.echo("  - 'my-project' matches VS Code/terminal with that folder")
    click.echo("")

    matchers = []

    # Title keywords
    title_input = click.prompt(
        "Window title keywords (comma-separated, or press Enter to skip)",
        default="", show_default=False
    )
    if title_input.strip():
        keywords = [k.strip() for k in title_input.split(",") if k.strip()]
        matchers.append({"type": "window_title", "contains": keywords})

    # App names
    click.echo("")
    click.echo("Common app names: google-chrome, firefox, gnome-terminal-server,")
    click.echo("  code (VS Code), slack, zoom, teams, discord")
    app_input = click.prompt(
        "App names to match (comma-separated, or press Enter to skip)",
        default="", show_default=False
    )
    if app_input.strip():
        apps = [a.strip() for a in app_input.split(",") if a.strip()]
        matcher = {"type": "app_name", "equals": apps}
        # If title keywords also provided for this app, add filter
        app_title = click.prompt(
            "  Only when title also contains (optional, Enter to skip)",
            default="", show_default=False
        )
        if app_title.strip():
            matcher["window_title_contains"] = [k.strip() for k in app_title.split(",")]
        matchers.append(matcher)

    if not matchers:
        click.echo("No rules added. Project not saved.")
        return

    # Load existing projects and append
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, "r") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    if "projects" not in data:
        data["projects"] = []

    data["projects"].append({"name": name, "matchers": matchers})

    with open(PROJECTS_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    click.echo("")
    click.echo("✅ Project '{}' added!".format(name))
    click.echo("   Rules will apply to new activity from now on.")
    click.echo("")
    click.echo("   Tip: Run 'taskmind projects' to see all projects.")
    click.echo("   Tip: Run 'taskmind add-project' to add more.")


@main.command(name="remove-project")
def remove_project():
    """Remove a project by name."""
    import yaml
    from taskmind.config import PROJECTS_FILE, load_projects

    projs = load_projects()
    if not projs:
        click.echo("No projects configured.")
        return

    click.echo("Current projects:")
    for i, p in enumerate(projs, 1):
        click.echo("  {}. {}".format(i, p["name"]))

    choice = click.prompt("Enter number to remove", type=int)
    if choice < 1 or choice > len(projs):
        click.echo("Invalid choice.")
        return

    removed = projs.pop(choice - 1)

    with open(PROJECTS_FILE, "w") as f:
        yaml.dump({"projects": projs}, f, default_flow_style=False, sort_keys=False)

    click.echo("✅ Removed '{}'.".format(removed["name"]))


@main.command(name="edit-project")
def edit_project():
    """Edit keywords for an existing project."""
    import yaml
    from taskmind.config import PROJECTS_FILE, load_projects

    projs = load_projects()
    if not projs:
        click.echo("No projects configured.")
        return

    click.echo("Select project to edit:")
    for i, p in enumerate(projs, 1):
        keywords = []
        for m in p.get("matchers", []):
            keywords.extend(m.get("contains", []))
            keywords.extend(m.get("equals", []))
        click.echo("  {}. {} [{}]".format(i, p["name"], ", ".join(keywords)))

    choice = click.prompt("Enter number", type=int)
    if choice < 1 or choice > len(projs):
        click.echo("Invalid choice.")
        return

    project = projs[choice - 1]
    title_matcher = next((m for m in project.get("matchers", []) if m.get("type") == "window_title"), None)
    keywords = list(title_matcher.get("contains", [])) if title_matcher else []

    while True:
        click.echo("")
        click.echo("Project: {}".format(project["name"]))
        click.echo("Keywords:")
        if keywords:
            for i, kw in enumerate(keywords, 1):
                click.echo("  {}. {}".format(i, kw))
        else:
            click.echo("  (none)")
        click.echo("")
        click.echo("Actions: [a]dd, [r]emove, [d]one")
        action = click.prompt("Choice", type=click.Choice(["a", "r", "d"]), show_choices=False)

        if action == "a":
            new_kw = click.prompt("  New keyword(s) (comma-separated)")
            for k in new_kw.split(","):
                k = k.strip()
                if k and k not in keywords:
                    keywords.append(k)
        elif action == "r":
            if not keywords:
                click.echo("  No keywords to remove.")
                continue
            num = click.prompt("  Enter number to remove", type=int)
            if 1 <= num <= len(keywords):
                removed = keywords.pop(num - 1)
                click.echo("  Removed '{}'".format(removed))
            else:
                click.echo("  Invalid number.")
        elif action == "d":
            break

    # Save
    if not keywords:
        click.echo("No keywords set. Project unchanged.")
        return

    # Update only the window_title matcher, preserve other matchers
    other_matchers = [m for m in project.get("matchers", []) if m.get("type") != "window_title"]
    project["matchers"] = [{"type": "window_title", "contains": keywords}] + other_matchers

    with open(PROJECTS_FILE, "w") as f:
        yaml.dump({"projects": projs}, f, default_flow_style=False, sort_keys=False)

    click.echo("✅ Updated '{}'.".format(project["name"]))


@main.command(name="setup")
def setup_projects():
    """Interactive first-time setup — add common projects quickly."""
    import yaml
    from taskmind.config import PROJECTS_FILE, ensure_dirs

    ensure_dirs()
    click.echo("🧠 TaskMind — Quick Project Setup")
    click.echo("═" * 40)
    click.echo("")
    click.echo("Let's set up your projects so TaskMind can")
    click.echo("auto-classify your work. You can always add")
    click.echo("more later with 'taskmind add-project'.")
    click.echo("")

    projects = []

    # Offer common presets
    presets = [
        ("Meetings", {"type": "window_title", "contains": ["Zoom Meeting", "Google Meet", "Microsoft Teams", "Huddle"]}),
        ("Communication", {"type": "app_name", "equals": ["slack", "discord", "telegram-desktop"]}),
        ("Email", {"type": "window_title", "contains": ["Gmail", "Outlook", "Mail"]}),
        ("Social Media", {"type": "window_title", "contains": ["Facebook", "Instagram", "LinkedIn", "Twitter", "YouTube"]}),
        ("Code Review", {"type": "window_title", "contains": ["Pull Request", "Merge Request"]}),
    ]

    click.echo("Common categories (y/n for each):")
    click.echo("")
    for name, matcher in presets:
        if click.confirm("  Add '{}'?".format(name), default=True):
            projects.append({"name": name, "matchers": [matcher]})

    # Custom projects
    click.echo("")
    click.echo("─" * 40)
    click.echo("Now add your own projects (your work repos, clients, etc.)")
    click.echo("")

    while True:
        add_more = click.confirm("Add a custom project?", default=True)
        if not add_more:
            break

        name = click.prompt("  Project name")
        keywords = click.prompt("  Keywords to match in window title (comma-separated)")
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if kw_list:
            projects.append({"name": name, "matchers": [{"type": "window_title", "contains": kw_list}]})
            click.echo("  ✓ Added '{}'".format(name))
        click.echo("")

    if not projects:
        click.echo("No projects added. Run 'taskmind setup' again anytime.")
        return

    # Save
    with open(PROJECTS_FILE, "w") as f:
        yaml.dump({"projects": projects}, f, default_flow_style=False, sort_keys=False)

    click.echo("")
    click.echo("═" * 40)
    click.echo("✅ Setup complete! {} projects configured.".format(len(projects)))
    click.echo("")
    click.echo("Commands:")
    click.echo("  taskmind projects       — see all projects")
    click.echo("  taskmind add-project    — add another project")
    click.echo("  taskmind remove-project — remove a project")
    click.echo("  taskmind status         — check tracking")
    click.echo("")


@main.command()
def dashboard():
    """Open web dashboard in browser."""
    cfg = load_config()
    port = cfg["dashboard"]["port"]
    url = "http://127.0.0.1:{}".format(port)
    click.echo("Starting dashboard at {}".format(url))
    click.echo("Press Ctrl+C to stop.")
    # Open browser
    os.system("xdg-open '{}' 2>/dev/null &".format(url))
    # Start server
    from taskmind.ui.dashboard.app import run_dashboard
    run_dashboard()



@main.command()
@click.option("--output", "-o", "output_path", default=None, help="Output directory")
def backup(output_path):
    """Backup all TaskMind data (DB + configs + recordings)."""
    import shutil
    from taskmind.config import DATA_DIR, CONFIG_DIR

    if not output_path:
        output_path = os.path.expanduser("~/taskmind-backup-{}".format(date.today().isoformat()))

    os.makedirs(output_path, exist_ok=True)
    db_src = os.path.join(DATA_DIR, "taskmind.db")
    if os.path.exists(db_src):
        shutil.copy2(db_src, output_path)
    config_dest = os.path.join(output_path, "config")
    if os.path.isdir(CONFIG_DIR):
        shutil.copytree(CONFIG_DIR, config_dest, dirs_exist_ok=True)
    rec_src = os.path.join(DATA_DIR, "recordings")
    if os.path.isdir(rec_src) and os.listdir(rec_src):
        shutil.copytree(rec_src, os.path.join(output_path, "recordings"), dirs_exist_ok=True)
    click.echo("✅ Backup saved to: {}".format(output_path))


@main.command(name="import-data")
@click.argument("backup_path")
def import_data(backup_path):
    """Restore TaskMind data from a backup."""
    import shutil
    from taskmind.config import DATA_DIR, CONFIG_DIR

    backup_path = os.path.expanduser(backup_path)
    if not os.path.isdir(backup_path):
        click.echo("Backup not found: {}".format(backup_path))
        return
    db_file = os.path.join(backup_path, "taskmind.db")
    if os.path.exists(db_file):
        shutil.copy2(db_file, os.path.join(DATA_DIR, "taskmind.db"))
        click.echo("  ✓ Database restored")
    config_src = os.path.join(backup_path, "config")
    if os.path.isdir(config_src):
        shutil.copytree(config_src, CONFIG_DIR, dirs_exist_ok=True)
        click.echo("  ✓ Configs restored")
    click.echo("✅ Import complete.")


@main.command()
@click.option("--purge", is_flag=True, help="Also delete all data")
def uninstall(purge):
    """Uninstall TaskMind (stop service, remove files)."""
    import shutil
    from taskmind.config import DATA_DIR, CONFIG_DIR

    click.echo("Uninstalling TaskMind...")
    os.system("systemctl --user stop taskmind 2>/dev/null")
    os.system("systemctl --user disable taskmind 2>/dev/null")
    service = os.path.expanduser("~/.config/systemd/user/taskmind.service")
    if os.path.exists(service):
        os.remove(service)
    bin_link = os.path.expanduser("~/.local/bin/taskmind")
    if os.path.exists(bin_link):
        os.remove(bin_link)
    venv = os.path.join(DATA_DIR, "venv")
    if os.path.isdir(venv):
        shutil.rmtree(venv)
    if purge:
        if os.path.isdir(DATA_DIR):
            shutil.rmtree(DATA_DIR)
        if os.path.isdir(CONFIG_DIR):
            shutil.rmtree(CONFIG_DIR)
        click.echo("✅ TaskMind fully removed (data deleted).")
    else:
        click.echo("✅ TaskMind uninstalled. Data kept at: {}".format(DATA_DIR))

@main.command(name="install-extension")
def install_extension():
    """Install Window Calls GNOME extension (required for Wayland)."""
    import urllib.request
    import zipfile
    ext_uuid = "window-calls@domandoman.xyz"
    ext_url = "https://extensions.gnome.org/extension-data/window-callsdomandoman.xyz.v11.shell-extension.zip"
    ext_dir = os.path.expanduser("~/.local/share/gnome-shell/extensions/{}".format(ext_uuid))

    click.echo("Downloading Window Calls extension...")
    zip_path = "/tmp/window-calls.zip"
    try:
        urllib.request.urlretrieve(ext_url, zip_path)
    except Exception as e:
        click.echo("Download failed: {}".format(e))
        return

    os.makedirs(ext_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(ext_dir)

    click.echo("Enabling extension...")
    os.system("gnome-extensions enable {} 2>/dev/null".format(ext_uuid))

    click.echo("")
    click.echo("✅ Extension installed!")
    click.echo("")
    click.echo("⚠️  You MUST log out and log back in for it to activate.")
    click.echo("   (On X11, press Alt+F2 → type 'r' → Enter to restart shell)")
    click.echo("")
    click.echo("After re-login, run: taskmind status")


if __name__ == "__main__":
    main()
