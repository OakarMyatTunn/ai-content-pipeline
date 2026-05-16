"""
Shared ffmpeg path detection utility.
Works on Windows (checks PATH + common install locations) and Linux/Mac.
"""
import shutil
from pathlib import Path

_FFMPEG_PATH: str | None = None


def get_ffmpeg() -> str:
    """Return the full path to the ffmpeg executable."""
    global _FFMPEG_PATH
    if _FFMPEG_PATH:
        return _FFMPEG_PATH

    # Check PATH first
    found = shutil.which("ffmpeg")
    if found:
        _FFMPEG_PATH = found
        return _FFMPEG_PATH

    # Common Windows locations
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            _FFMPEG_PATH = c
            return _FFMPEG_PATH

    raise FileNotFoundError(
        "ffmpeg not found in PATH or common locations.\n"
        "Please install: https://github.com/BtbN/FFmpeg-Builds/releases\n"
        "Extract to C:\\ffmpeg and add C:\\ffmpeg\\bin to system PATH,\n"
        "then restart your terminal."
    )


def ff_cmd(cmd: list) -> list:
    """Replace 'ffmpeg' string in command list with actual binary path."""
    ffmpeg = get_ffmpeg()
    return [ffmpeg if c == "ffmpeg" else c for c in cmd]
