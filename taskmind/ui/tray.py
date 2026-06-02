"""System tray icon using pystray."""
import threading
from PIL import Image, ImageDraw
from taskmind.database import get_total_tracked_today, get_project_summary


def _create_icon_image(color="green"):
    """Create a simple colored circle icon."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = {"green": "#4CAF50", "red": "#F44336", "gray": "#9E9E9E"}
    draw.ellipse([8, 8, 56, 56], fill=colors.get(color, "#4CAF50"))
    draw.text((22, 20), "T", fill="white")
    return img


def run_tray(daemon_start_cb=None, daemon_stop_cb=None):
    """Run system tray icon. Blocks the calling thread."""
    try:
        import pystray
        from pystray import MenuItem as Item
    except ImportError:
        print("pystray not installed. Skipping tray icon.")
        return

    def get_status(item):
        total = get_total_tracked_today()
        h, m = divmod(total // 60, 60)
        return "Today: {}h {}m".format(h, m)

    def on_dashboard(icon, item):
        import os
        os.system("xdg-open 'http://127.0.0.1:7890' 2>/dev/null &")

    def on_quit(icon, item):
        icon.stop()
        if daemon_stop_cb:
            daemon_stop_cb()

    icon = pystray.Icon(
        "taskmind",
        _create_icon_image("green"),
        "TaskMind",
        menu=pystray.Menu(
            Item("TaskMind (Tracking)", None, enabled=False),
            Item(get_status, None, enabled=False),
            pystray.Menu.SEPARATOR,
            Item("Open Dashboard", on_dashboard),
            pystray.Menu.SEPARATOR,
            Item("Quit", on_quit),
        ),
    )
    icon.run()
