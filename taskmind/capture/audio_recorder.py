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
    """Record mic + system audio. Works on minimal Linux (no ffmpeg, no GPU, 4-8GB RAM).
    
    Strategy:
    1. Best: parecord from a combined source (mic + monitor via PulseAudio null sink)
    2. Good: parecord from monitor (others) — your voice still goes through Meet
    3. Fallback: parecord from mic only
    """
    monitor = _get_monitor_source()
    mic = _get_default_mic()

    if _cmd_exists("parecord"):
        if monitor and mic:
            # Create a virtual combined sink that mixes mic + monitor
            # This uses PulseAudio's module-null-sink + module-loopback (no ffmpeg needed)
            _setup_combined_source(monitor, mic)
            combined = "taskmind_combined.monitor"
            # Check if combined source exists
            result = subprocess.run(["pactl", "list", "short", "sources"],
                                    capture_output=True, text=True, timeout=3)
            if combined in result.stdout:
                return ["parecord", "--file-format=wav", "-d", combined, filepath]
            # Fallback to monitor only
            return ["parecord", "--file-format=wav", "-d", monitor, filepath]
        elif monitor:
            return ["parecord", "--file-format=wav", "-d", monitor, filepath]
        else:
            return ["parecord", "--file-format=wav", filepath]
    elif _cmd_exists("pw-record"):
        if monitor:
            return ["pw-record", "--target", monitor, filepath]
        return ["pw-record", "--target", "0", filepath]
    elif _cmd_exists("arecord"):
        return ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", filepath]
    return None


def _get_default_mic():
    """Get default microphone source."""
    try:
        result = subprocess.run(["pactl", "get-default-source"],
                                capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _setup_combined_source(monitor, mic):
    """Create a PulseAudio null sink that combines mic + system audio. Lightweight, no ffmpeg."""
    try:
        # Check if already exists
        result = subprocess.run(["pactl", "list", "short", "sinks"],
                                capture_output=True, text=True, timeout=3)
        if "taskmind_combined" in result.stdout:
            return  # Already set up

        # Create null sink
        subprocess.run(["pactl", "load-module", "module-null-sink",
                        "sink_name=taskmind_combined", "sink_properties=device.description=TaskMind_Recording"],
                       capture_output=True, timeout=3)
        # Loopback mic into it
        subprocess.run(["pactl", "load-module", "module-loopback",
                        "source=" + mic, "sink=taskmind_combined", "latency_msec=1"],
                       capture_output=True, timeout=3)
        # Loopback monitor into it
        subprocess.run(["pactl", "load-module", "module-loopback",
                        "source=" + monitor, "sink=taskmind_combined", "latency_msec=1"],
                       capture_output=True, timeout=3)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


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
