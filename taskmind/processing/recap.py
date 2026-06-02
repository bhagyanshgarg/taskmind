"""Daily recap generator - template-based summary of the day."""
from datetime import date
from taskmind.database import get_project_summary, get_activities_for_date


def generate_recap(target_date=None):
    """Generate a text recap of the day's activities."""
    if target_date is None:
        target_date = date.today().isoformat()

    summary = get_project_summary(target_date)
    activities = get_activities_for_date(target_date)

    if not activities:
        return "No activity recorded for {}.".format(target_date)

    total_seconds = sum(s["total_seconds"] for s in summary)
    idle_seconds = sum(a["duration_seconds"] for a in activities if a["is_idle"])
    total_h, total_m = divmod(total_seconds // 60, 60)
    idle_h, idle_m = divmod(idle_seconds // 60, 60)

    lines = []
    lines.append("📋 Daily Recap – {}".format(target_date))
    lines.append("")
    lines.append("Total tracked: {}h {}m | Idle: {}h {}m".format(total_h, total_m, idle_h, idle_m))
    lines.append("")
    lines.append("Projects:")

    for proj in summary:
        h, m = divmod(proj["total_seconds"] // 60, 60)
        name = proj["project_name"] or "Unclassified"
        lines.append("  • {}: {}h {}m ({} samples)".format(name, h, m, proj["count"]))

    return "\n".join(lines)
