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
        click.echo("No projects configured. Edit: {}".format(PROJECTS_FILE))
        return
    click.echo("Configured projects:")
    for p in projs:
        matchers = len(p.get("matchers", []))
        click.echo("  • {} ({} matchers)".format(p["name"], matchers))


@main.command()
def dashboard():
    """Open web dashboard in browser."""
    cfg = load_config()
    port = cfg["dashboard"]["port"]
    url = "http://127.0.0.1:{}".format(port)
    click.echo("Opening dashboard: {}".format(url))
    os.system("xdg-open '{}' 2>/dev/null &".format(url))


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
