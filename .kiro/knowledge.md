# TaskMind - Project Knowledge Base

## Overview
TaskMind is a lightweight, privacy-first activity tracker and automatic timesheet generator built for Linux (Ubuntu 18.04+). Created by Rishap Gandhi.

**GitHub:** https://github.com/rishapgandhi/taskmind
**Version:** v1.0.2
**License:** MIT

## Project Location
- Source code: /var/www/html/test/task_remembering_app/taskmind/
- Project plan: /var/www/html/test/task_remembering_app/project_plan.md
- Social content: /var/www/html/permit/other/test/taskmind/

## Architecture
- Language: Python 3.6+
- Database: SQLite + FTS5 at ~/.local/share/taskmind/taskmind.db
- Config: YAML at ~/.config/taskmind/config.yaml and projects.yaml
- Dashboard: FastAPI + vanilla JS SPA at localhost:7890
- Daemon: Background process with systemd, PID file
- Window tracking: GNOME Wayland via Window Calls extension D-Bus API, X11 via xdotool
- Audio: PulseAudio combined null sink (mic + monitor), parecord
- Scheduler: APScheduler for daily recap notifications

## Key Technical Details

### Wayland Window Tracking
- Uses window-calls@domandoman.xyz GNOME extension
- D-Bus: org.gnome.Shell.Extensions.Windows.List + GetTitle
- Requires logout/login after install to activate
- _get_all_windows_wayland() scans ALL windows (for meeting detection)
- get_active_window() gets only focused window (for activity tracking)

### Audio Recording
- Combined source: PulseAudio null sink taskmind_combined mixing mic + monitor
- Created via module-null-sink + module-loopback
- Cross-process start/stop via PID file
- No ffmpeg dependency - pure PulseAudio
- Auto-records when meeting window detected (any window, not just focused)

### Meeting Auto-Detection
- Daemon checks ALL open windows every 10s
- Keywords: Meet -, Zoom Meeting, Microsoft Teams, meet.google.com, Huddle
- Auto-starts recording + notification on detect
- Auto-stops when meeting window disappears

### Dashboard (localhost:7890)
- Tabs: Today, Weekly, Monthly, Timesheet, Search, Recordings, Settings
- Weekly/Monthly have prev/next navigation with offset parameter
- Recordings page has audio player + date navigation
- Recording indicator + Start/Stop button in nav
- Timezone fix: uses local date not UTC

### Project Classification
- Rule-based YAML matchers in projects.yaml
- Matcher types: window_title, app_name, git_branch, directory
- Interactive setup: taskmind setup, add-project, remove-project

## All CLI Commands
- taskmind start / stop / status
- taskmind today / yesterday / week / recap
- taskmind timesheet (--export csv|json, --date)
- taskmind dashboard
- taskmind search "query"
- taskmind record / stop-recording / recordings
- taskmind git-watch [/path]
- taskmind export --to csv|json|clockify|toggl|jira
- taskmind setup / add-project / remove-project / projects
- taskmind backup / import-data / uninstall (--purge)
- taskmind config / install-extension

## GitHub Setup
- Repo: public, MIT license
- Features: Issues, Discussions, Wiki, Projects enabled
- 8 releases (v0.1.0 through v1.0.2)
- Wiki: 6 pages
- Discussions: 6 announcements

## User Context
- User: Rishap Gandhi (rishapgandhi on GitHub)
- Company: Auriga IT Consulting Pvt Ltd
- Machine: Ubuntu 22.04, GNOME 42.9, Wayland, 16GB RAM
- Main work project: ESG Vault / Permit Vault
- google_mcp repo: /var/www/html/mcp_server/google_mcp
- Drive folder for presentations: 1qkdGb6FQ6IlAKlria2oJilv51IRQTAPz

## Known Issues / Future Work
- Transcription needs whisper.cpp or openai-whisper installed
- macOS/Windows: stubs ready but not implemented
- Browser extension for richer tab tracking (planned)
- Calendar integration (planned)
- Team dashboard (planned)

## Development Principles (CRITICAL)

1. **Minimal resources** — must work on 4GB RAM, no GPU, <100MB RAM usage
2. **No external tools** — only use what's pre-installed on Ubuntu (parecord, pactl, xdotool, xprintidle, notify-send, git, python3). Do NOT add ffmpeg, docker, node, or any tool that requires separate installation unless explicitly decided by user.
3. **Pre-installed dependencies only** — PulseAudio utils (ships with Ubuntu), Python stdlib, and pip packages only. No system packages beyond what install.sh already installs (xdotool, xprintidle, libnotify-bin, wmctrl).
4. **Lightweight always** — every feature must justify its resource cost. No background processes that idle at >50MB.
5. **Works offline** — zero cloud dependency, zero network calls, zero telemetry.
6. **Easy setup** — one command install, interactive wizard, no config file editing required.
7. **Cross-platform ready** — abstract OS-specific code, but Linux first. Don't break Linux to add other platforms.
