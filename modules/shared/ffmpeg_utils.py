"""
Shared ffmpeg path detection utility.
"""
import shutil
import os
from pathlib import Path

_FFMPEG_PATH: str | None = None

def get_ffmpeg() -> str:
    global _FFMPEG_PATH
    if _FFMPEG_PATH:
        return _FFMPEG_PATH

    # PATH check first
    found = shutil.which("ffmpeg")
    if found:
        _FFMPEG_PATH = found
        return _FFMPEG_PATH

    # Build candidate list
    candidates = [
        # XDM (found on this machine)
        r"C:\Program Files (x86)\XDM\ffmpeg.exe",
        # Manual installs
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
    ]

    # Winget — glob all versions under Packages
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        # Direct Links folder (winget sometimes symlinks here)
        candidates.append(str(Path(local_app) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"))
        # Search all Gyan.FFmpeg package folders (version-agnostic)
        pkg_root = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
        if pkg_root.exists():
            for match in sorted(pkg_root.rglob("ffmpeg.exe"), reverse=True):
                candidates.insert(0, str(match))  # newest version first

    # Scoop
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        candidates += [
            str(Path(user_profile) / "scoop" / "shims" / "ffmpeg.exe"),
            str(Path(user_profile) / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe"),
        ]

    for c in candidates:
        if Path(c).exists():
            _FFMPEG_PATH = c
            return _FFMPEG_PATH

    raise FileNotFoundError(
        "ffmpeg not found.\n"
        "Your ffmpeg is at:\n"
        r"  C:\Users\derek\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin" + "\n"
        "Add that folder to your system PATH, then restart the terminal."
    )


def ff_cmd(cmd: list) -> list:
    ffmpeg = get_ffmpeg()
    return [ffmpeg if c == "ffmpeg" else c for c in cmd]
