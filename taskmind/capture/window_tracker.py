"""Active window tracker — supports X11 (xdotool) and GNOME Wayland (Window Calls extension).

On Wayland (GNOME 42+), requires the 'Window Calls' extension:
  Install: taskmind install-extension
  Then log out and back in (or restart GNOME Shell on X11).
"""
import subprocess
import json
import os
import re


def _run(cmd):
    """Run command and return stdout, empty string on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _get_window_wayland():
    """Get focused window via Window Calls GNOME extension D-Bus API."""
    try:
        result = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
             "--object-path", "/org/gnome/Shell/Extensions/Windows",
             "--method", "org.gnome.Shell.Extensions.Windows.GetFocused"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and "Error" not in result.stdout:
            match = re.search(r"\('(.+)',\)", result.stdout, re.DOTALL)
            if match:
                info = json.loads(match.group(1))
                return {
                    "window_title": info.get("title", ""),
                    "app_name": info.get("wm_class", ""),
                    "window_class": info.get("wm_class_instance", info.get("wm_class", "")),
                }
    except Exception:
        pass
    return None


def _get_window_x11():
    """Get focused window via xdotool + xprop (X11/XWayland)."""
    wid = _run(["xdotool", "getactivewindow"])
    if not wid:
        return None

    title = _run(["xdotool", "getactivewindow", "getwindowname"])
    if not title:
        return None

    xprop_out = _run(["xprop", "-id", wid, "WM_CLASS"])
    app_name = ""
    window_class = ""
    if "=" in xprop_out:
        parts = xprop_out.split("=", 1)[1].strip().replace('"', "").split(",")
        app_name = parts[0].strip() if parts else ""
        window_class = parts[1].strip() if len(parts) > 1 else app_name

    return {
        "window_title": title,
        "app_name": app_name,
        "window_class": window_class,
    }


def _get_window_wmctrl():
    """Fallback: get any visible window from wmctrl (limited on Wayland)."""
    output = _run(["wmctrl", "-l"])
    if not output:
        return None
    # Get the last line (most recently raised window)
    lines = [l for l in output.strip().split("\n") if l.strip()]
    if not lines:
        return None
    # Format: 0x01800007  0  hostname Title here
    parts = lines[-1].split(None, 3)
    title = parts[3] if len(parts) > 3 else ""
    if title:
        return {"window_title": title, "app_name": "", "window_class": ""}
    return None


def get_active_window():
    """Get active window info. Tries Wayland first, then X11, then wmctrl fallback."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "")

    if session_type == "wayland":
        # Try Window Calls extension first (best for GNOME Wayland)
        result = _get_window_wayland()
        if result:
            return result
        # Fall through to X11 (for XWayland apps)

    # Try xdotool (works on X11, partially on XWayland)
    result = _get_window_x11()
    if result:
        return result

    # Last resort: wmctrl
    result = _get_window_wmctrl()
    if result:
        return result

    return {"window_title": "", "app_name": "", "window_class": ""}
