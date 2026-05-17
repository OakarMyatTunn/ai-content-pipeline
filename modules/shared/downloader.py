"""
URL Video Downloader — yt-dlp wrapper.
Downloads YouTube, Facebook, TikTok, and 1000+ sites.
Saves to /input/queue/ folder then triggers recap pipeline.
"""
import re
import subprocess
from pathlib import Path
from modules.shared.config_loader import cfg
from modules.shared.logger import log
from modules.shared.ffmpeg_utils import get_ffmpeg


# Supported URL patterns
URL_PATTERNS = [
    r'https?://(www\.)?youtube\.com/watch\?v=',
    r'https?://youtu\.be/',
    r'https?://(www\.)?youtube\.com/shorts/',
    r'https?://(www\.)?facebook\.com/.*video',
    r'https?://fb\.watch/',
    r'https?://(www\.)?tiktok\.com/',
    r'https?://(vm\.)?tiktok\.com/',
    r'https?://(www\.)?instagram\.com/(p|reel|tv)/',
    r'https?://(www\.)?twitter\.com/.*/video',
    r'https?://x\.com/.*/video',
    r'https?://(www\.)?vimeo\.com/',
]


def is_supported_url(text: str) -> bool:
    """Check if text contains a supported video URL."""
    text = text.strip()
    return any(re.search(p, text, re.IGNORECASE) for p in URL_PATTERNS)


def get_video_info(url: str) -> dict:
    """Get video title and duration without downloading."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            import json
            info = json.loads(result.stdout)
            return {
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
                "filesize": info.get("filesize_approx", 0),
            }
    except Exception as e:
        log.warning(f"Could not get video info: {e}")
    return {"title": "Unknown", "duration": 0, "uploader": "", "filesize": 0}


def download_url(url: str, progress_callback=None) -> Path:
    """
    Download video from URL to /input/queue/.
    Returns path to downloaded file.
    progress_callback: optional function(percent, speed, eta) called during download.
    """
    queue_dir = cfg.INPUT_FOLDER / "queue"
    queue_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = get_ffmpeg()

    log.info(f"Downloading: {url}")

    # yt-dlp command — best quality MP4 under 2GB, max 1080p
    cmd = [
        "yt-dlp",
        "--ffmpeg-location", str(Path(ffmpeg_path).parent),
        "--format", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
        "--merge-output-format", "mp4",
        "--output", str(queue_dir / "%(title).80B.%(ext)s"),
        "--no-playlist",           # single video only
        "--no-overwrites",
        "--restrict-filenames",    # safe filenames on Windows
        "--max-filesize", "2G",    # reject files over 2GB
        "--newline",               # progress on separate lines
        url,
    ]

    # Track the output filename
    downloaded_path = None
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )

    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        log.info(f"  yt-dlp: {line}")

        # Extract download progress
        if "[download]" in line and "%" in line:
            try:
                pct_str = line.split("%")[0].split()[-1]
                pct = float(pct_str)
                if progress_callback:
                    progress_callback(pct, line)
            except Exception:
                pass

        # Extract destination filename
        if "[download] Destination:" in line:
            downloaded_path = Path(line.split("Destination:")[-1].strip())
        if "[Merger] Merging formats into" in line:
            # After merge, the file is the merged output
            try:
                downloaded_path = Path(line.split('"')[1])
            except Exception:
                pass

    process.wait()

    if process.returncode != 0:
        raise RuntimeError(
            f"Download failed (exit {process.returncode}). "
            "Video may be age-restricted, private, or unavailable in your region."
        )

    # Find the most recently created MP4 in queue if path not captured
    if downloaded_path is None or not downloaded_path.exists():
        mp4s = sorted(queue_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if mp4s:
            downloaded_path = mp4s[-1]
        else:
            raise RuntimeError("Download completed but output file not found.")

    size_mb = downloaded_path.stat().st_size / 1024 / 1024
    log.info(f"Downloaded: {downloaded_path.name} ({size_mb:.0f}MB)")
    return downloaded_path
