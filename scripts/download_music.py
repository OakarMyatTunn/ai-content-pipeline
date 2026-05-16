"""
Downloads a starter pack of royalty-free music from Free Music Archive.
Run once during setup: python scripts/download_music.py
Tracks are saved to /music/ folder.
"""
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from modules.shared.config_loader import cfg
from modules.shared.logger import log

# Curated royalty-free tracks (CC0/Public Domain from Free Music Archive)
TRACKS = [
    {
        "name": "upbeat_pop_01.mp3",
        "url": "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/WFMU/Broke_For_Free/Directionless_EP/Broke_For_Free_-_01_-_Night_Owl.mp3",
    },
    {
        "name": "happy_bounce_02.mp3",
        "url": "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/ccCommunity/Kai_Engel/Satin/Kai_Engel_-_04_-_Interlude.mp3",
    },
]

if __name__ == "__main__":
    music_dir = cfg.MUSIC_FOLDER
    music_dir.mkdir(exist_ok=True)

    log.info(f"Downloading {len(TRACKS)} music tracks to {music_dir}...")
    for track in TRACKS:
        out = music_dir / track["name"]
        if out.exists():
            log.info(f"  Already exists: {track['name']}")
            continue
        try:
            log.info(f"  Downloading: {track['name']}...")
            urllib.request.urlretrieve(track["url"], out)
            log.info(f"  ✓ Saved: {track['name']}")
        except Exception as e:
            log.warning(f"  ✗ Failed: {track['name']} — {e}")

    existing = list(music_dir.glob("*.mp3"))
    log.info(f"\nMusic library: {len(existing)} track(s) in {music_dir}")
    log.info("You can add more .mp3 files to /music/ manually.")
