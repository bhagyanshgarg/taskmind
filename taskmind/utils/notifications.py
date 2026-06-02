"""Desktop notifications via notify-send."""
import subprocess


def notify(title, body, urgency="normal"):
    """Send a desktop notification. urgency: low, normal, critical."""
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-a", "TaskMind", title, body],
            timeout=5, capture_output=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # notify-send not available
