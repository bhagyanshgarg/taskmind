"""Active window tracker using xdotool and xprop (X11)."""
import subprocess


def _run(cmd):
    """Run command and return stdout, empty string on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_active_window():
    """Get active window info. Returns dict with title, app_name, window_class."""
    wid = _run(["xdotool", "getactivewindow"])
    if not wid:
        return {"window_title": "", "app_name": "", "window_class": ""}

    title = _run(["xdotool", "getactivewindow", "getwindowname"])
    # Get WM_CLASS from xprop
    xprop_out = _run(["xprop", "-id", wid, "WM_CLASS"])
    app_name = ""
    window_class = ""
    if "=" in xprop_out:
        # Format: WM_CLASS(STRING) = "instance", "class"
        parts = xprop_out.split("=", 1)[1].strip().replace('"', "").split(",")
        app_name = parts[0].strip() if parts else ""
        window_class = parts[1].strip() if len(parts) > 1 else app_name

    return {
        "window_title": title,
        "app_name": app_name,
        "window_class": window_class,
    }
