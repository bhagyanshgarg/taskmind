"""Extract browser URL for the active tab by matching window title against browser history."""
import os
import sqlite3
import shutil
import tempfile
import glob

# Known browser wm_class values
BROWSER_WM_CLASSES = [
    "google-chrome", "chromium", "chromium-browser", "brave-browser",
    "firefox", "firefox-esr", "vivaldi", "opera", "microsoft-edge",
]

# Browser name suffixes in window titles
BROWSER_TITLE_SUFFIXES = [
    " - Google Chrome", " - Chromium", " - Brave", " - Vivaldi",
    " - Opera", " - Microsoft Edge", " – Mozilla Firefox",
    " — Mozilla Firefox",
]

# Chrome-based history DB paths
CHROME_HISTORY_PATHS = [
    "~/.config/google-chrome/Default/History",
    "~/.config/chromium/Default/History",
    "~/.config/BraveSoftware/Brave-Browser/Default/History",
    "~/.config/vivaldi/Default/History",
    "~/.config/microsoft-edge/Default/History",
]

# Firefox places DB paths
FIREFOX_PROFILE_DIRS = [
    "~/.mozilla/firefox",
]


def is_browser(app_name, window_class=""):
    """Check if the window belongs to a known browser."""
    check = (app_name or "").lower()
    check2 = (window_class or "").lower()
    return any(b in check or b in check2 for b in BROWSER_WM_CLASSES)


def get_browser_url(window_title, app_name, window_class=""):
    """Get the URL for the active browser tab by matching title against history."""
    if not is_browser(app_name, window_class):
        return ""

    page_title = _strip_browser_suffix(window_title)
    if not page_title or len(page_title) < 3:
        return ""

    # Try Chrome-based browsers first
    url = _get_url_from_chrome_history(page_title)
    if url:
        return url

    # Try Firefox
    url = _get_url_from_firefox_history(page_title)
    return url or ""


def _strip_browser_suffix(title):
    """Remove browser name suffix from window title."""
    for suffix in BROWSER_TITLE_SUFFIXES:
        if title.endswith(suffix):
            return title[:-len(suffix)]
    return title


def _get_url_from_chrome_history(page_title):
    """Find URL matching page title in Chrome-based browser history."""
    for path_pattern in CHROME_HISTORY_PATHS:
        history_path = os.path.expanduser(path_pattern)
        if not os.path.exists(history_path):
            continue
        try:
            tmp = tempfile.mktemp(suffix='.db')
            shutil.copy2(history_path, tmp)
            conn = sqlite3.connect(tmp, timeout=2)
            # Exact title match first (most reliable)
            row = conn.execute(
                "SELECT url FROM urls WHERE title = ? ORDER BY last_visit_time DESC LIMIT 1",
                (page_title,),
            ).fetchone()
            if not row:
                # Partial match as fallback
                row = conn.execute(
                    "SELECT url FROM urls WHERE title LIKE ? ORDER BY last_visit_time DESC LIMIT 1",
                    (page_title + '%',),
                ).fetchone()
            conn.close()
            os.unlink(tmp)
            if row:
                return row[0]
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
    return None


def _get_url_from_firefox_history(page_title):
    """Find URL matching page title in Firefox history."""
    for profile_dir in FIREFOX_PROFILE_DIRS:
        profile_dir = os.path.expanduser(profile_dir)
        if not os.path.isdir(profile_dir):
            continue
        # Find the default profile's places.sqlite
        places_files = glob.glob(os.path.join(profile_dir, "*.default*/places.sqlite"))
        places_files += glob.glob(os.path.join(profile_dir, "*.default-release*/places.sqlite"))
        for places_path in places_files:
            try:
                tmp = tempfile.mktemp(suffix='.db')
                shutil.copy2(places_path, tmp)
                conn = sqlite3.connect(tmp, timeout=2)
                row = conn.execute(
                    "SELECT url FROM moz_places WHERE title = ? ORDER BY last_visit_date DESC LIMIT 1",
                    (page_title,),
                ).fetchone()
                if not row:
                    row = conn.execute(
                        "SELECT url FROM moz_places WHERE title LIKE ? ORDER BY last_visit_date DESC LIMIT 1",
                        (page_title + '%',),
                    ).fetchone()
                conn.close()
                os.unlink(tmp)
                if row:
                    return row[0]
            except Exception:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass
    return None
