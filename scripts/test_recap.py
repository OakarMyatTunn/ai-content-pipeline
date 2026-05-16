"""
Test the recap pipeline with a short sample video.

Usage:
    python scripts/test_recap.py "C:/path/to/movie.mp4"

If no path given, shows instructions.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from modules.shared.logger import log
from modules.shared.config_loader import cfg

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n" + "="*55)
        print("  RECAP PIPELINE TEST")
        print("="*55)
        print("\nUsage:")
        print("  python scripts/test_recap.py \"C:/path/to/movie.mp4\"")
        print("\nThe file will be:")
        print("  1. Transcribed with Whisper (GPU)")
        print("  2. Script generated in English + Myanmar (Gemini)")
        print("  3. Sent to Telegram for your approval")
        print("  4. Voiceover generated (Edge TTS + gTTS)")
        print("  5. Video assembled with clips + subtitles")
        print("  6. Output in outputs/recap/ folder")
        print("\nTip: Start with a SHORT video (5-10 min) for the first test.")
        print("="*55 + "\n")
        sys.exit(0)

    video_path = Path(sys.argv[1])

    if not video_path.exists():
        log.error(f"File not found: {video_path}")
        sys.exit(1)

    supported = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".flv"}
    if video_path.suffix.lower() not in supported:
        log.error(f"Unsupported format: {video_path.suffix}")
        log.error(f"Supported: {', '.join(supported)}")
        sys.exit(1)

    size_mb = video_path.stat().st_size / 1024 / 1024
    log.info(f"Input: {video_path.name} ({size_mb:.0f} MB)")
    log.info("Starting recap pipeline...")

    from modules.recap.pipeline import run
    run(video_path)
