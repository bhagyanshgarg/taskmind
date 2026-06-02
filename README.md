# TaskMind

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/) [![Ubuntu 18.04+](https://img.shields.io/badge/Ubuntu-18.04+-orange.svg)](https://ubuntu.com/)

**Lightweight, privacy-first activity tracker and automatic timesheet generator.** Passively tracks your workday and tells you exactly what you did — so you never forget to fill your timesheet again.

Zero cloud dependency. All data stays local. <100MB RAM.

## Why This Exists

- You forget what you worked on all day → timesheets are inaccurate
- Context switches make it impossible to recall tasks at EOD
- Meeting notes get lost; action items are forgotten
- No single tool captures the full picture of a workday

TaskMind fixes this by passively tracking your active windows, classifying them into projects, and auto-generating timesheets.

## Features

| Feature | Description |
|---------|-------------|
| **Passive Tracking** | Logs active window every 10s — zero effort |
| **Auto Timesheet** | Groups activities into project time blocks |
| **Project Rules** | YAML-based classifier (window title, app, git branch) |
| **Daily Recap** | End-of-day summary of what you accomplished |
| **Full-Text Search** | Search across all captured activity |
| **CSV/JSON Export** | Export timesheets for Jira, Clockify, Toggl |
| **System Tray** | Always-visible status icon |
| **CLI** | `taskmind status`, `taskmind today`, `taskmind timesheet` |

## Quick Start

### 1. Install

```bash
git clone https://github.com/rishapgandhi/taskmind.git
cd taskmind
bash install.sh
```

### 2. Configure Projects

Edit `~/.config/taskmind/projects.yaml`:

```yaml
projects:
  - name: "My Project"
    matchers:
      - type: window_title
        contains: ["my-project", "PROJ-"]
      - type: app_name
        equals: ["zoom"]
```

### 3. Start Tracking

```bash
taskmind start
```

### 4. Check Your Day

```bash
taskmind status      # Quick overview
taskmind today       # Full daily recap
taskmind timesheet   # Auto-generated timesheet
taskmind timesheet --export csv > timesheet.csv
```

## CLI Commands

```
taskmind start       Start the tracking daemon
taskmind stop        Stop the tracking daemon
taskmind status      Show status and today's hours
taskmind today       Show today's activity recap
taskmind yesterday   Show yesterday's recap
taskmind timesheet   Generate timesheet (--export csv|json)
taskmind search      Full-text search across activities
taskmind projects    List configured projects
taskmind config      Open config in $EDITOR
taskmind dashboard   Open web dashboard
```

## System Requirements

- Ubuntu 18.04+ (or any Debian-based Linux with X11)
- Python 3.6+
- `xdotool`, `xprintidle`, `libnotify-bin` (installed automatically)

## Project Structure

```
taskmind/
├── pyproject.toml
├── setup.py
├── install.sh
├── configs/
│   ├── config.default.yaml
│   └── projects.example.yaml
└── taskmind/
    ├── cli.py              # CLI commands
    ├── config.py           # YAML config loader
    ├── daemon.py           # Background tracking daemon
    ├── database.py         # SQLite + FTS5
    ├── capture/
    │   ├── window_tracker.py   # xdotool/xprop
    │   └── idle_detector.py    # xprintidle
    ├── processing/
    │   ├── classifier.py       # Rule-based project matching
    │   ├── timesheet.py        # Timesheet generation
    │   └── recap.py            # Daily recap
    ├── ui/
    │   └── tray.py             # System tray icon
    └── utils/
        └── notifications.py    # Desktop notifications
```

## Privacy & Security

| Aspect | Implementation |
|--------|---------------|
| Data storage | All local (`~/.local/share/taskmind/`) |
| Network | Zero — no cloud, no telemetry |
| Tracking | Window titles only, never screenshots |
| Blacklist | Exclude sensitive apps in config |
| Delete | `rm ~/.local/share/taskmind/taskmind.db` |

## Resource Usage

| State | CPU | RAM |
|-------|-----|-----|
| Tracking | <1% | ~80MB |
| Idle | 0% | ~80MB |
| Peak | <2% | ~100MB |

## Contributing

PRs welcome. Keep it minimal and lightweight.

## License

[MIT](LICENSE) — use commercially, fork, modify, redistribute freely.
