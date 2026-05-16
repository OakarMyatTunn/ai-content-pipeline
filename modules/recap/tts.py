"""
Step 3 of recap pipeline.
Text-to-speech for English (Edge TTS) and Myanmar (gTTS).
Both run fully locally/offline — no paid API.
"""
import asyncio
from pathlib import Path
import edge_tts
from gtts import gTTS
from modules.shared.config_loader import cfg
from modules.shared.logger import log


async def _edge_tts(text: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=cfg.EN_TTS_VOICE)
    await communicate.save(str(out_path))


def generate_english_audio(script: str, out_path: Path) -> Path:
    """Generate English MP3 using Microsoft Edge TTS (free, natural voice)."""
    log.info(f"Generating English TTS → {out_path.name}")
    asyncio.run(_edge_tts(script, out_path))
    log.info(f"English audio saved ({out_path.stat().st_size // 1024} KB)")
    return out_path


def generate_myanmar_audio(script: str, out_path: Path) -> Path:
    """Generate Myanmar/Burmese MP3 using gTTS."""
    log.info(f"Generating Myanmar TTS → {out_path.name}")
    tts = gTTS(text=script, lang=cfg.MY_TTS_LANG, slow=False)
    tts.save(str(out_path))
    log.info(f"Myanmar audio saved ({out_path.stat().st_size // 1024} KB)")
    return out_path


def generate_all(scripts: dict, out_dir: Path, stem: str) -> dict:
    """
    Generate both audio files.
    Returns: {"english": Path, "myanmar": Path}
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    en_path = out_dir / f"{stem}_en.mp3"
    my_path = out_dir / f"{stem}_my.mp3"

    generate_english_audio(scripts["english"], en_path)
    generate_myanmar_audio(scripts["myanmar"], my_path)

    return {"english": en_path, "myanmar": my_path}
