"""Active window tracker — supports X11 (xdotool) and GNOME Wayland (Window Calls extension).

On Wayland (GNOME 42+), requires the 'Window Calls' extension:
  Install: taskmind install-extension
  Then log out and back in (or restart GNOME Shell on X11).
"""
import subprocess
import json
import os


def _run(cmd):
    """Run command and return stdout, empty string on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _get_all_windows_wayland():
    """Get all open windows via Window Calls extension. Returns list of {title, wm_class}."""
    try:
        result = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
             "--object-path", "/org/gnome/Shell/Extensions/Windows",
             "--method", "org.gnome.Shell.Extensions.Windows.List"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0 or "Error" in result.stdout:
            return []

        raw = result.stdout.strip()
        start = raw.index("'") + 1
        end = raw.rindex("'")
        windows = json.loads(raw[start:end])

        # Get titles for all windows
        all_wins = []
        for w in windows:
            wid = w["id"]
            title_result = subprocess.run(
                ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
                 "--object-path", "/org/gnome/Shell/Extensions/Windows",
                 "--method", "org.gnome.Shell.Extensions.Windows.GetTitle",
                 str(wid)],
                capture_output=True, text=True, timeout=2,
            )
            title = ""
            if title_result.returncode == 0:
                t = title_result.stdout.strip()
                if t.startswith("('") and t.endswith("',)"):
                    title = t[2:-3]
            all_wins.append({
                "window_title": title,
                "app_name": w.get("wm_class", ""),
                "focused": w.get("focus", False),
            })
        return all_wins
    except Exception:
        return []


def has_meeting_window(keywords):
    """Check if ANY open window matches meeting keywords (not just focused)."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "")
    if session_type == "wayland":
        windows = _get_all_windows_wayland()
        for w in windows:
            title = (w.get("window_title") or "").lower()
            if any(kw.lower() in title for kw in keywords):
                return True
    return False


def _get_window_wayland():
    """Get focused window via Window Calls GNOME extension D-Bus API."""
    try:
        # Get window list to find focused window ID and wm_class
        result = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
             "--object-path", "/org/gnome/Shell/Extensions/Windows",
             "--method", "org.gnome.Shell.Extensions.Windows.List"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0 or "Error" in result.stdout:
            return None

        raw = result.stdout.strip()
        start = raw.index("'") + 1
        end = raw.rindex("'")
        windows = json.loads(raw[start:end])

        # Find focused window
        focused = None
        for w in windows:
            if w.get("focus"):
                focused = w
                break
        if not focused:
            return None

        # Get title via GetTitle method
        wid = focused["id"]
        title_result = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
             "--object-path", "/org/gnome/Shell/Extensions/Windows",
             "--method", "org.gnome.Shell.Extensions.Windows.GetTitle",
             str(wid)],
            capture_output=True, text=True, timeout=2,
        )
        title = ""
        if title_result.returncode == 0:
            t = title_result.stdout.strip()
            if t.startswith("('") and t.endswith("',)"):
                title = t[2:-3]

        return {
            "window_title": title,
            "app_name": focused.get("wm_class", ""),
            "window_class": focused.get("wm_class_instance", focused.get("wm_class", "")),
        }
    except Exception:
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


def get_active_window():
    """Get active window info. Tries Wayland first, then X11."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "")

    if session_type == "wayland":
        result = _get_window_wayland()
        if result:
            return result

    result = _get_window_x11()
    if result:
        return result

    return {"window_title": "", "app_name": "", "window_class": ""}
