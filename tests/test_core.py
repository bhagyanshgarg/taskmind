"""Basic tests for TaskMind core modules."""
import sys
import os
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_config_defaults():
    from taskmind.config import DEFAULT_CONFIG
    assert "general" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["general"]["tracking_interval_seconds"] == 10
    assert DEFAULT_CONFIG["general"]["idle_threshold_minutes"] == 5
    print("✓ test_config_defaults")


def test_classifier():
    from taskmind.processing.classifier import classify
    # Without projects.yaml, everything is Unclassified
    # But we can test the function runs
    result = classify("test window", "test-app", "TestClass")
    assert isinstance(result, str)
    print("✓ test_classifier")


def test_timesheet_empty():
    from taskmind.processing.timesheet import generate_timesheet
    entries = generate_timesheet("1999-01-01")
    assert entries == []
    print("✓ test_timesheet_empty")


def test_recap_empty():
    from taskmind.processing.recap import generate_recap
    result = generate_recap("1999-01-01")
    assert "No activity" in result
    print("✓ test_recap_empty")


def test_weekly_recap():
    from taskmind.processing.recap import generate_weekly_recap
    result = generate_weekly_recap("1999-01-01")
    assert "No activity" in result or "Weekly Recap" in result
    print("✓ test_weekly_recap")


def test_database_init():
    from taskmind.database import init_db, get_db, DB_PATH
    init_db()
    conn = get_db()
    # Check tables exist
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t["name"] for t in tables]
    assert "activities" in table_names
    assert "timesheet_entries" in table_names
    assert "recordings" in table_names
    assert "git_events" in table_names
    conn.close()
    print("✓ test_database_init")


def test_database_insert_query():
    from taskmind.database import init_db, insert_activity, get_total_tracked_today
    init_db()
    # Total should be a number
    total = get_total_tracked_today()
    assert isinstance(total, int)
    print("✓ test_database_insert_query")


def test_audio_recorder_not_recording():
    from taskmind.capture.audio_recorder import is_recording
    assert is_recording() is False
    print("✓ test_audio_recorder_not_recording")


def test_platform_layer():
    from taskmind.platform import PLATFORM, get_active_window, get_idle_seconds
    assert PLATFORM in ("linux", "darwin", "windows")
    result = get_active_window()
    assert "window_title" in result
    assert "app_name" in result
    print("✓ test_platform_layer")


def test_export_csv():
    from taskmind.processing.export import export_csv
    result = export_csv("1999-01-01")
    assert "date,project_name" in result
    print("✓ test_export_csv")


if __name__ == "__main__":
    test_config_defaults()
    test_classifier()
    test_timesheet_empty()
    test_recap_empty()
    test_weekly_recap()
    test_database_init()
    test_database_insert_query()
    test_audio_recorder_not_recording()
    test_platform_layer()
    test_export_csv()
    print("\n✅ All tests passed!")
