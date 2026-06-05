"""On-demand audio recorder using PulseAudio/PipeWire.
Records system audio (monitor) to capture all meeting participants, not just mic.
Uses PID file for cross-process start/stop."""
import os
import subprocess
import signal
from datetime import datetime
from taskmind.config import DATA_DIR

RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")
REC_PID_FILE = os.path.join(DATA_DIR, "recording.pid")
REC_META_FILE = os.path.join(DATA_DIR, "recording.meta")


def _ensure_dir():
    os.makedirs(RECORDINGS_DIR, exist_ok=True)


def _get_monitor_source():
    """Get the monitor source to capture all system audio (both sides of a call)."""
    try:
        # PipeWire/PulseAudio: find the monitor source
        result = subprocess.run(
            ["pactl", "list", "short", "sources"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                # Monitor sources capture all output audio (both sides of meeting)
                if ".monitor" in line:
                    return line.split("\t")[1]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _get_record_cmd(filepath):
    """Get recording command that captures system audio (all participants)."""
    monitor = _get_monitor_source()

    if monitor:
        # Record from monitor source = captures everything you hear (all meeting participants)
        if _cmd_exists("parecord"):
            return ["parecord", "--file-format=wav", "-d", monitor, filepath]
        elif _cmd_exists("pw-record"):
            return ["pw-record", "--target", monitor, filepath]
    else:
        # Fallback: record mic only
        if _cmd_exists("pw-record"):
            return ["pw-record", "--target", "0", filepath]
        elif _cmd_exists("parecord"):
            return ["parecord", "--file-format=wav", filepath]
        elif _cmd_exists("arecord"):
            return ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", filepath]
    return None


def _cmd_exists(cmd):
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0


def start_recording():
    """Start audio recording (system audio). Returns filepath or None."""
    if is_recording():
        return None

    _ensure_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filepath = os.path.join(RECORDINGS_DIR, "{}.wav".format(timestamp))

    cmd = _get_record_cmd(filepath)
    if not cmd:
        return None

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Save PID and metadata for cross-process stop
    with open(REC_PID_FILE, "w") as f:
        f.write(str(proc.pid))
    with open(REC_META_FILE, "w") as f:
        f.write("{}\n{}".format(filepath, datetime.now().isoformat()))

    return filepath


def stop_recording():
    """Stop audio recording (works cross-process). Returns (filepath, duration_seconds) or None."""
    if not is_recording():
        return None

    try:
        with open(REC_PID_FILE, "r") as f:
            pid = int(f.read().strip())
        with open(REC_META_FILE, "r") as f:
            lines = f.read().strip().split("\n")
            filepath = lines[0]
            started = datetime.fromisoformat(lines[1])
    except (FileNotFoundError, ValueError, IndexError):
        _cleanup()
        return None

    # Kill the recording process
    try:
        os.kill(pid, signal.SIGINT)
        # Wait briefly for clean exit
        import time
        time.sleep(1)
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    except OSError:
        pass

    duration = int((datetime.now() - started).total_seconds())
    _cleanup()
    return (filepath, duration)


def is_recording():
    """Check if currently recording (cross-process safe)."""
    if not os.path.exists(REC_PID_FILE):
        return False
    try:
        with open(REC_PID_FILE, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # Check if process alive
        return True
    except (OSError, ValueError):
        _cleanup()
        return False


def _cleanup():
    """Remove PID and meta files."""
    for f in [REC_PID_FILE, REC_META_FILE]:
        if os.path.exists(f):
            os.remove(f)
