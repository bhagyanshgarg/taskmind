"""Whisper.cpp transcription integration (CPU-only)."""
import os
import subprocess
import shutil
from taskmind.config import DATA_DIR, load_config

MODELS_DIR = os.path.join(DATA_DIR, "models")
WHISPER_BIN = shutil.which("whisper-cpp") or shutil.which("main", path=os.path.join(DATA_DIR, "whisper.cpp"))


def _get_model_path():
    """Get path to whisper model file."""
    config = load_config()
    model_name = config.get("audio", {}).get("whisper_model", "tiny")
    model_file = "ggml-{}.bin".format(model_name)
    return os.path.join(MODELS_DIR, model_file)


def is_whisper_available():
    """Check if whisper.cpp binary and model are available."""
    return WHISPER_BIN is not None or shutil.which("whisper-cpp-wrapper") is not None


def download_model(model_name="tiny"):
    """Download whisper model if not present."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    model_file = os.path.join(MODELS_DIR, "ggml-{}.bin".format(model_name))
    if os.path.exists(model_file):
        return model_file

    url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{}.bin".format(model_name)
    print("Downloading whisper model '{}'...".format(model_name))
    try:
        subprocess.run(["wget", "-q", "-O", model_file, url], check=True, timeout=300)
        return model_file
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(["curl", "-sL", "-o", model_file, url], check=True, timeout=300)
            return model_file
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None


def transcribe(audio_path):
    """Transcribe a WAV file using whisper.cpp. Returns transcript text or None."""
    model_path = _get_model_path()

    if not os.path.exists(model_path):
        model_path = download_model()
        if not model_path:
            return None

    # Try different whisper.cpp binary names
    whisper_bin = None
    for name in ["whisper-cpp", "whisper", "main"]:
        path = shutil.which(name)
        if path:
            whisper_bin = path
            break
    # Check in our data dir
    local_bin = os.path.join(DATA_DIR, "whisper.cpp", "main")
    if not whisper_bin and os.path.exists(local_bin):
        whisper_bin = local_bin

    if not whisper_bin:
        # Fallback: try openai-whisper Python package
        return _transcribe_python(audio_path)

    # Run whisper.cpp
    try:
        result = subprocess.run(
            [whisper_bin, "-m", model_path, "-f", audio_path, "--no-timestamps", "-nt"],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return _transcribe_python(audio_path)


def _transcribe_python(audio_path):
    """Fallback: use openai-whisper Python package if installed."""
    try:
        import whisper
        model = whisper.load_model("tiny")
        result = model.transcribe(audio_path)
        return result.get("text", "").strip()
    except ImportError:
        return "[Transcription unavailable - install whisper.cpp or openai-whisper]"
    except Exception as e:
        return "[Transcription error: {}]".format(e)
