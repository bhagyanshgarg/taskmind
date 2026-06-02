"""Idle detection using xprintidle."""
import subprocess


def get_idle_ms():
    """Get milliseconds since last user input. Returns 0 on failure."""
    try:
        result = subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=2)
        return int(result.stdout.strip()) if result.returncode == 0 else 0
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return 0


def is_idle(threshold_minutes=5):
    """Check if user is idle beyond threshold."""
    idle_ms = get_idle_ms()
    return idle_ms > (threshold_minutes * 60 * 1000)
