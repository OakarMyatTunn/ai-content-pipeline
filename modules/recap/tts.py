"""
Step 3 of recap pipeline.
Text-to-speech for English and Myanmar (Burmese).
Primary: gTTS (Google TTS) — works globally, no region blocks
Fallback: edge-tts if gTTS fails
Both free, no API key needed.
"""
import asyncio
import subprocess
from pathlib import Path
from gtts import gTTS
from modules.shared.config_loader import cfg
from modules.shared.logger import log


def _gtts_audio(text: str, lang: str, out_path: Path) -> Path:
    """Generate audio using Google TTS — works in all regions."""
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(str(out_path))
    return out_path


async def _edge_tts_async(text: str, out_path: Path) -> None:
    """Edge TTS fallback — may be blocked in some regions."""
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=cfg.EN_TTS_VOICE)
    await communicate.save(str(out_path))


def generate_english_audio(script: str, out_path: Path) -> Path:
    """Generate English MP3 — tries gTTS first, edge-tts as fallback."""
    log.info(f"Generating English TTS → {out_path.name}")
    try:
        # Primary: gTTS (reliable, no region blocks)
        _gtts_audio(script, "en", out_path)
        log.info(f"English audio (gTTS) saved ({out_path.stat().st_size // 1024} KB)")
        return out_path
    except Exception as e:
        log.warning(f"gTTS failed ({e}), trying Edge TTS...")
        try:
            asyncio.run(_edge_tts_async(script, out_path))
            log.info(f"English audio (edge-tts) saved ({out_path.stat().st_size // 1024} KB)")
            return out_path
        except Exception as e2:
            raise RuntimeError(f"Both TTS engines failed. gTTS: {e} | Edge TTS: {e2}")


def generate_myanmar_audio(script: str, out_path: Path) -> Path:
    """Generate Myanmar/Burmese MP3 using gTTS."""
    log.info(f"Generating Myanmar TTS → {out_path.name}")
    _gtts_audio(script, cfg.MY_TTS_LANG, out_path)
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
