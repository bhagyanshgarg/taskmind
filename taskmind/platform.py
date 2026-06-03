"""Cross-platform abstraction layer for OS-specific operations.

This module provides a unified interface. Currently Linux-only,
but structured for future macOS/Windows support.
"""
import platform

PLATFORM = platform.system().lower()  # 'linux', 'darwin', 'windows'


def get_active_window():
    """Get active window info (title, app_name, window_class)."""
    if PLATFORM == "linux":
        from taskmind.capture.window_tracker import get_active_window as _get
        return _get()
    elif PLATFORM == "darwin":
        return _get_window_macos()
    elif PLATFORM == "windows":
        return _get_window_windows()
    return {"window_title": "", "app_name": "", "window_class": ""}


def get_idle_seconds():
    """Get seconds since last user input."""
    if PLATFORM == "linux":
        from taskmind.capture.idle_detector import get_idle_ms
        return get_idle_ms() // 1000
    elif PLATFORM == "darwin":
        return _get_idle_macos()
    elif PLATFORM == "windows":
        return _get_idle_windows()
    return 0


def send_notification(title, body):
    """Send desktop notification."""
    if PLATFORM == "linux":
        from taskmind.utils.notifications import notify
        notify(title, body)
    elif PLATFORM == "darwin":
        import subprocess
        subprocess.run(["osascript", "-e", 'display notification "{}" with title "{}"'.format(body, title)], capture_output=True)
    elif PLATFORM == "windows":
        try:
            from plyer import notification
            notification.notify(title=title, message=body, timeout=5)
        except ImportError:
            pass


# --- macOS stubs (to be implemented) ---

def _get_window_macos():
    """macOS: Get active window via NSWorkspace/Accessibility API."""
    # Future: use subprocess calling osascript or pyobjc
    # osascript -e 'tell application "System Events" to get name of first process whose frontmost is true'
    return {"window_title": "", "app_name": "", "window_class": ""}


def _get_idle_macos():
    """macOS: Get idle time via IOKit."""
    # Future: ioreg -c IOHIDSystem | grep HIDIdleTime
    return 0


# --- Windows stubs (to be implemented) ---

def _get_window_windows():
    """Windows: Get active window via win32gui."""
    # Future: import win32gui; hwnd = win32gui.GetForegroundWindow()
    return {"window_title": "", "app_name": "", "window_class": ""}


def _get_idle_windows():
    """Windows: Get idle time via GetLastInputInfo."""
    # Future: import ctypes; ctypes.windll.user32.GetLastInputInfo()
    return 0
