"""
URL Video Downloader — yt-dlp wrapper.
Downloads YouTube, Facebook, TikTok, and 1000+ sites.
Saves to /input/queue/ folder then triggers recap pipeline.
"""
import re
import subprocess
import requests
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
    r'https?://drive\.google\.com/(file/d/|open\?id=)',
]

# Google Drive patterns
GDRIVE_PATTERNS = [
    r'https?://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
    r'https?://drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
    r'https?://drive\.google\.com/uc\?.*id=([a-zA-Z0-9_-]+)',
]


def is_supported_url(text: str) -> bool:
    """Check if text contains a supported video URL."""
    text = text.strip()
    return any(re.search(p, text, re.IGNORECASE) for p in URL_PATTERNS)


def is_gdrive_url(text: str) -> bool:
    """Check if URL is a Google Drive link."""
    return any(re.search(p, text, re.IGNORECASE) for p in GDRIVE_PATTERNS)


def extract_gdrive_id(url: str) -> str | None:
    """Extract Google Drive file ID from URL."""
    for pattern in GDRIVE_PATTERNS:
        m = re.search(pattern, url, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


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


def download_gdrive(url: str, progress_callback=None) -> Path:
    """
    Download a file from Google Drive.
    Handles large files (any size) via direct download URL.
    The file must be shared publicly (Anyone with link can view).
    """
    import requests

    file_id = extract_gdrive_id(url)
    if not file_id:
        raise ValueError("Could not extract Google Drive file ID from URL.")

    queue_dir = cfg.INPUT_FOLDER / "queue"
    queue_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Downloading from Google Drive: {file_id}")

    # Use the export/download endpoint
    download_url_base = f"https://drive.google.com/uc?export=download&id={file_id}"

    session = requests.Session()

    # First request — may get a virus scan warning for large files
    response = session.get(download_url_base, stream=True, timeout=30)

    # Handle Google's "large file" confirmation page
    if "text/html" in response.headers.get("Content-Type", ""):
        # Need to confirm download
        import re as _re
        confirm_token = None

        # Try to find confirm token in response
        for k, v in response.cookies.items():
            if k.startswith("download_warning"):
                confirm_token = v
                break

        # Also check response text for newer Google Drive format
        if not confirm_token:
            text = response.text
            m = _re.search(r'confirm=([0-9A-Za-z_]+)', text)
            if m:
                confirm_token = m.group(1)
            # Newer format uses uuid
            m2 = _re.search(r'"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', text)
            if m2 and not confirm_token:
                confirm_token = m2.group(1)

        if confirm_token:
            download_url_confirmed = (
                f"https://drive.google.com/uc?export=download"
                f"&id={file_id}&confirm={confirm_token}"
            )
            response = session.get(download_url_confirmed, stream=True, timeout=30)
        else:
            # Try direct download URL format
            response = session.get(
                f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
                stream=True, timeout=30
            )

    # Get filename from Content-Disposition header
    filename = f"gdrive_{file_id}.mp4"
    cd = response.headers.get("Content-Disposition", "")
    if cd:
        m = re.search(r"filename\*?=([^;\n]+)", cd)
        if m:
            raw = m.group(1).strip().strip('"').strip("'")
            if raw:
                filename = raw
            if not any(filename.lower().endswith(ext) for ext in
                      [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v"]):
                filename += ".mp4"

        out_path = queue_dir / filename
    total_size = int(response.headers.get("Content-Length", 0))
    downloaded = 0
    last_pct = 0

    log.info(f"Saving to: {out_path.name} ({total_size/1024/1024:.0f}MB)")

    with open(out_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = (downloaded / total_size) * 100
                    if pct - last_pct >= 10:
                        last_pct = pct
                        log.info(f"  Download: {pct:.0f}% ({downloaded/1024/1024:.0f}MB)")
                        if progress_callback:
                            progress_callback(pct, f"{pct:.0f}%")

    size_mb = out_path.stat().st_size / 1024 / 1024
    log.info(f"Google Drive download complete: {out_path.name} ({size_mb:.0f}MB)")
    return out_path


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
