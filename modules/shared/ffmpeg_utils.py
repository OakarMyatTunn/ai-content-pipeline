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

    candidates = [
        # XDM (found on this machine)
        r"C:\Program Files (x86)\XDM\ffmpeg.exe",
        # Manual installs
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
    ]

    # PATH check
    found = shutil.which("ffmpeg")
    if found:
        _FFMPEG_PATH = found
        return _FFMPEG_PATH

    # Winget
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidates.append(str(Path(local_app) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"))
        pkg_root = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
        if pkg_root.exists():
            for match in pkg_root.rglob("ffmpeg.exe"):
                candidates.append(str(match))

    # Scoop
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        candidates += [
            str(Path(user_profile) / "scoop" / "shims" / "ffmpeg.exe"),
            str(Path(user_profile) / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe"),
        ]

    # Chocolatey
    candidates.append(r"C:\ProgramData\chocolatey\bin\ffmpeg.exe")

    for c in candidates:
        if Path(c).exists():
            _FFMPEG_PATH = c
            return _FFMPEG_PATH

    raise FileNotFoundError(
        "ffmpeg not found.\n"
        "Run: Get-ChildItem -Path C:\\ -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue\n"
        "Then add that path to FFMPEG_PATH in your .env file."
    )


def ff_cmd(cmd: list) -> list:
    """Replace 'ffmpeg' string in command list with actual binary path."""
    ffmpeg = get_ffmpeg()
    return [ffmpeg if c == "ffmpeg" else c for c in cmd]
