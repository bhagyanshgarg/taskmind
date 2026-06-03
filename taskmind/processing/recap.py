"""Daily and weekly recap generator - template-based summaries."""
from datetime import date, timedelta
from taskmind.database import get_project_summary, get_activities_for_date, get_db


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


def generate_weekly_recap(end_date=None):
    """Generate aggregated weekly recap (last 7 days)."""
    if end_date is None:
        end_date = date.today()
    elif isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    start_date = end_date - timedelta(days=6)

    conn = get_db()
    rows = conn.execute(
        "SELECT project_name, SUM(duration_seconds) as total_seconds, COUNT(*) as count "
        "FROM activities WHERE timestamp >= ? AND timestamp < ? AND is_idle=0 "
        "GROUP BY project_name ORDER BY total_seconds DESC",
        (start_date.isoformat(), (end_date + timedelta(days=1)).isoformat()),
    ).fetchall()

    total_by_day = conn.execute(
        "SELECT substr(timestamp,1,10) as day, SUM(duration_seconds) as total "
        "FROM activities WHERE timestamp >= ? AND timestamp < ? AND is_idle=0 "
        "GROUP BY day ORDER BY day",
        (start_date.isoformat(), (end_date + timedelta(days=1)).isoformat()),
    ).fetchall()
    conn.close()

    if not rows:
        return "No activity recorded for the week {}/{}.".format(start_date, end_date)

    total_seconds = sum(r["total_seconds"] for r in rows)
    total_h, total_m = divmod(total_seconds // 60, 60)
    avg_per_day = total_seconds // 7

    lines = []
    lines.append("📊 Weekly Recap – {} to {}".format(start_date.isoformat(), end_date.isoformat()))
    lines.append("")
    lines.append("Total: {}h {}m | Avg/day: {}h {}m".format(
        total_h, total_m, avg_per_day // 3600, (avg_per_day % 3600) // 60))
    lines.append("")
    lines.append("Projects:")
    for r in rows:
        h, m = divmod(r["total_seconds"] // 60, 60)
        name = r["project_name"] or "Unclassified"
        pct = round(r["total_seconds"] / total_seconds * 100) if total_seconds > 0 else 0
        lines.append("  • {}: {}h {}m ({}%)".format(name, h, m, pct))

    lines.append("")
    lines.append("Daily breakdown:")
    for d in total_by_day:
        dh, dm = divmod(d["total"] // 60, 60)
        lines.append("  {} — {}h {}m".format(d["day"], dh, dm))

    return "\n".join(lines)
