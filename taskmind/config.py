"""Configuration loader with defaults."""
import os
import yaml

DEFAULT_CONFIG = {
    "general": {
        "tracking_interval_seconds": 10,
        "idle_threshold_minutes": 5,
        "work_start_hour": 9,
        "work_end_hour": 18,
        "recap_time": "17:30",
    },
    "timesheet": {
        "minimum_block_minutes": 5,
        "round_to_minutes": 15,
        "include_idle_as_break": True,
    },
    "tracking": {
        "blacklisted_apps": [],
        "blacklisted_titles": [],
    },
    "dashboard": {
        "host": "127.0.0.1",
        "port": 7890,
    },
    "notifications": {
        "enabled": True,
        "daily_recap": True,
    },
}

DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "taskmind")
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "taskmind")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.yaml")
PROJECTS_FILE = os.path.join(CONFIG_DIR, "projects.yaml")
DB_PATH = os.path.join(DATA_DIR, "taskmind.db")
PID_FILE = os.path.join(DATA_DIR, "taskmind.pid")
LOG_FILE = os.path.join(DATA_DIR, "logs", "taskmind.log")


def ensure_dirs():
    """Create required directories."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "logs"), exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    """Load config from YAML file, falling back to defaults."""
    ensure_dirs()
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            user_config = yaml.safe_load(f) or {}
        for section, values in user_config.items():
            if section in config and isinstance(values, dict):
                config[section].update(values)
            else:
                config[section] = values
    return config


def load_projects():
    """Load project matching rules from YAML."""
    if not os.path.exists(PROJECTS_FILE):
        return []
    with open(PROJECTS_FILE, "r") as f:
        data = yaml.safe_load(f) or {}
    return data.get("projects", [])
