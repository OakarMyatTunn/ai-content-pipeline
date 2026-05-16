"""
Downloads a starter pack of royalty-free music from Mixkit.
Run once during setup: python scripts/download_music.py
Tracks are saved to /music/ folder.
No API key required. Mixkit is free with no attribution required.
"""
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

# Use a browser User-Agent — CDNs block bare Python urllib by default
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")]
urllib.request.install_opener(_opener)

from modules.shared.config_loader import cfg
from modules.shared.logger import log

# Curated royalty-free tracks — Mixkit (free, no attribution required)
# Source: https://mixkit.co/free-stock-music/
TRACKS = [
    {
        "name": "happy_upbeat_01.mp3",
        "url": "https://assets.mixkit.co/music/preview/mixkit-happy-feet-extra-198.mp3",
    },
    {
        "name": "fun_bounce_02.mp3",
        "url": "https://assets.mixkit.co/music/preview/mixkit-fun-and-happy-3.mp3",
    },
    {
        "name": "cute_cartoon_03.mp3",
        "url": "https://assets.mixkit.co/music/preview/mixkit-little-cute-animal-74.mp3",
    },
    {
        "name": "playful_pop_04.mp3",
        "url": "https://assets.mixkit.co/music/preview/mixkit-playful-cat-333.mp3",
    },
    {
        "name": "upbeat_kids_05.mp3",
        "url": "https://assets.mixkit.co/music/preview/mixkit-games-worldbeat-466.mp3",
    },
]

if __name__ == "__main__":
    music_dir = cfg.MUSIC_FOLDER
    music_dir.mkdir(exist_ok=True)

    log.info(f"Downloading {len(TRACKS)} music tracks to {music_dir}...")
    success = 0
    for track in TRACKS:
        out = music_dir / track["name"]
        if out.exists():
            log.info(f"  Already exists: {track['name']}")
            success += 1
            continue
        try:
            log.info(f"  Downloading: {track['name']}...")
            urllib.request.urlretrieve(track["url"], out)
            size_kb = out.stat().st_size // 1024
            log.info(f"  Saved: {track['name']} ({size_kb} KB)")
            success += 1
        except Exception as e:
            log.warning(f"  Failed: {track['name']} -- {e}")

    existing = list(music_dir.glob("*.mp3"))
    log.info(f"Music library: {len(existing)} track(s) in {music_dir}")

    if len(existing) == 0:
        log.warning("All downloads failed. Add .mp3 files manually to /music/ folder.")
        log.warning("Free sources: https://mixkit.co/free-stock-music/")
        log.warning("              https://pixabay.com/music/")
    else:
        log.info("Done! You can add more .mp3 files to /music/ manually anytime.")
