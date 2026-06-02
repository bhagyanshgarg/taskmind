"""Rule-based project classifier using YAML matchers."""
from taskmind.config import load_projects


def classify(window_title, app_name, window_class=""):
    """Classify an activity into a project name based on rules. Returns project name or 'Unclassified'."""
    projects = load_projects()
    title_lower = (window_title or "").lower()
    app_lower = (app_name or "").lower()
    class_lower = (window_class or "").lower()

    for project in projects:
        for matcher in project.get("matchers", []):
            if _matches(matcher, title_lower, app_lower, class_lower):
                return project["name"]
    return "Unclassified"


def _matches(matcher, title_lower, app_lower, class_lower):
    """Check if a single matcher rule matches the current window."""
    mtype = matcher.get("type", "")

    if mtype == "window_title":
        keywords = matcher.get("contains", [])
        return any(k.lower() in title_lower for k in keywords)

    elif mtype == "app_name":
        apps = matcher.get("equals", [])
        app_match = any(a.lower() == app_lower or a.lower() == class_lower for a in apps)
        # If window_title_contains is also specified, both must match
        title_filter = matcher.get("window_title_contains", [])
        if title_filter:
            return app_match and any(k.lower() in title_lower for k in title_filter)
        return app_match

    elif mtype == "git_branch":
        # Window title often shows branch in terminals/IDEs
        keywords = matcher.get("contains", [])
        return any(k.lower() in title_lower for k in keywords)

    elif mtype == "directory":
        keywords = matcher.get("contains", [])
        return any(k.lower() in title_lower for k in keywords)

    return False
