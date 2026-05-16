"""
Shared ffmpeg path detection utility.
Works on Windows (checks PATH + all common install locations) and Linux/Mac.
"""
import shutil
import subprocess
from pathlib import Path

_FFMPEG_PATH: str | None = None


def get_ffmpeg() -> str:
    global _FFMPEG_PATH
    if _FFMPEG_PATH:
        return _FFMPEG_PATH

    # 1. Check PATH
    found = shutil.which("ffmpeg")
    if found:
        _FFMPEG_PATH = found
        return _FFMPEG_PATH

    # 2. Common Windows locations (manual installs)
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
    ]

    # 3. Winget installs to LocalAppData\Microsoft\WinGet\Links or Packages
    import os
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidates += [
            str(Path(local_app) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"),
            str(Path(local_app) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-7.1-full_build" / "bin" / "ffmpeg.exe"),
        ]
        # Glob for any ffmpeg under WinGet Packages
        pkg_root = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
        if pkg_root.exists():
            for match in pkg_root.rglob("ffmpeg.exe"):
                candidates.append(str(match))

    # 4. Scoop
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        candidates += [
            str(Path(user_profile) / "scoop" / "shims" / "ffmpeg.exe"),
            str(Path(user_profile) / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe"),
        ]

    # 5. Chocolatey
    candidates += [
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
    ]

    for c in candidates:
        if Path(c).exists():
            _FFMPEG_PATH = c
            return _FFMPEG_PATH

    # 6. Last resort — search common drives
    for drive in ["C:", "D:"]:
        for match in Path(drive + "\\").rglob("ffmpeg.exe") if Path(drive + "\\").exists() else []:
            _FFMPEG_PATH = str(match)
            return _FFMPEG_PATH

    raise FileNotFoundError(
        "ffmpeg not found. Run this in your terminal to locate it:\n"
        "  Get-ChildItem -Path C:\\ -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue\n"
        "Then add that folder to your system PATH."
    )


def ff_cmd(cmd: list) -> list:
    """Replace 'ffmpeg' string in command list with actual binary path."""
    ffmpeg = get_ffmpeg()
    return [ffmpeg if c == "ffmpeg" else c for c in cmd]
