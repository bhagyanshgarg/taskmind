"""On-demand audio recorder using PulseAudio/PipeWire/ALSA."""
import os
import subprocess
import signal
import time
from datetime import datetime
from taskmind.config import DATA_DIR, load_config

RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")
_recording_process = None
_recording_file = None
_recording_start = None


def _ensure_dir():
    os.makedirs(RECORDINGS_DIR, exist_ok=True)


def _get_record_cmd(filepath):
    """Get the best available recording command."""
    # Try PipeWire first, then PulseAudio, then ALSA
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
    """Start audio recording. Returns filepath or None on error."""
    global _recording_process, _recording_file, _recording_start

    if _recording_process and _recording_process.poll() is None:
        return None  # Already recording

    _ensure_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    _recording_file = os.path.join(RECORDINGS_DIR, "{}.wav".format(timestamp))
    _recording_start = datetime.now()

    cmd = _get_record_cmd(_recording_file)
    if not cmd:
        return None

    _recording_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return _recording_file


def stop_recording():
    """Stop audio recording. Returns (filepath, duration_seconds) or None."""
    global _recording_process, _recording_file, _recording_start

    if not _recording_process or _recording_process.poll() is not None:
        return None

    _recording_process.send_signal(signal.SIGINT)
    try:
        _recording_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _recording_process.kill()

    duration = int((datetime.now() - _recording_start).total_seconds())
    result = (_recording_file, duration)

    _recording_process = None
    _recording_file = None
    _recording_start = None
    return result


def is_recording():
    """Check if currently recording."""
    return _recording_process is not None and _recording_process.poll() is None


def get_recording_file():
    """Get current recording file path."""
    return _recording_file
