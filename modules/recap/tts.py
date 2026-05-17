"""
Recap TTS — Kokoro (primary, human-like, local GPU) + gTTS fallback.

Kokoro-82M: best free open-source TTS, near-human quality.
Runs on CPU or GPU. First run downloads ~300MB model automatically.
Myanmar: gTTS (Kokoro does not support Burmese yet).
"""
import asyncio
import subprocess
import tempfile
from pathlib import Path
from modules.shared.config_loader import cfg
from modules.shared.logger import log

# ── Kokoro English TTS ────────────────────────────────────────────────────────

_kokoro_pipeline = None

def _get_kokoro():
    global _kokoro_pipeline
    if _kokoro_pipeline is not None:
        return _kokoro_pipeline
    try:
        from kokoro import KPipeline
        log.info("Loading Kokoro TTS pipeline...")
        # 'a' = American English, best quality voice
        _kokoro_pipeline = KPipeline(lang_code='a')
        log.info("Kokoro TTS loaded ✓")
        return _kokoro_pipeline
    except Exception as e:
        log.warning(f"Kokoro not available ({e}) — falling back to gTTS")
        return None


def generate_english_audio(script: str, out_path: Path) -> Path:
    """
    Generate English MP3 using Kokoro TTS (human-like, local).
    Falls back to gTTS if Kokoro is not installed.
    """
    log.info(f"Generating English TTS → {out_path.name}")

    pipe = _get_kokoro()
    if pipe is not None:
        try:
            import soundfile as sf
            import numpy as np

            # Kokoro generates audio in chunks
            audio_chunks = []
            # Voice: af_heart = warm American female (most natural)
            generator = pipe(script, voice='af_heart', speed=0.95, split_pattern=r'\n+')
            for i, (gs, ps, audio) in enumerate(generator):
                audio_chunks.append(audio)
                log.info(f"  Kokoro chunk {i+1} generated")

            if audio_chunks:
                full_audio = np.concatenate(audio_chunks)
                # Save as WAV first then convert to MP3 via ffmpeg
                wav_path = out_path.with_suffix('.wav')
                sf.write(str(wav_path), full_audio, 24000)
                # Convert WAV to MP3
                from modules.shared.ffmpeg_utils import ff_cmd
                result = subprocess.run(
                    ff_cmd(["ffmpeg", "-y", "-i", str(wav_path),
                            "-codec:a", "libmp3lame", "-b:a", "192k",
                            str(out_path)]),
                    capture_output=True, text=True
                )
                wav_path.unlink(missing_ok=True)
                if result.returncode == 0:
                    log.info(f"Kokoro English audio saved ({out_path.stat().st_size // 1024} KB)")
                    return out_path
        except Exception as e:
            log.warning(f"Kokoro generation failed ({e}) — falling back to gTTS")

    # Fallback: gTTS
    log.info("Using gTTS fallback for English...")
    from gtts import gTTS
    tts = gTTS(text=script, lang='en', slow=False)
    tts.save(str(out_path))
    log.info(f"gTTS English audio saved ({out_path.stat().st_size // 1024} KB)")
    return out_path


def generate_myanmar_audio(script: str, out_path: Path) -> Path:
    """Generate Myanmar/Burmese MP3 using gTTS."""
    log.info(f"Generating Myanmar TTS → {out_path.name}")
    from gtts import gTTS
    tts = gTTS(text=script, lang=cfg.MY_TTS_LANG, slow=False)
    tts.save(str(out_path))
    log.info(f"Myanmar audio saved ({out_path.stat().st_size // 1024} KB)")
    return out_path


def generate_all(scripts: dict, out_dir: Path, stem: str,
                 languages: list = None) -> dict:
    """
    Generate audio for requested languages only.
    languages: ["english"], ["myanmar"], or ["english", "myanmar"]
    Returns: {"english": Path, "myanmar": Path} for whichever were requested.
    """
    if languages is None:
        languages = ["english", "myanmar"]

    out_dir.mkdir(parents=True, exist_ok=True)
    result = {}

    if "english" in languages:
        en_path = out_dir / f"{stem}_en.mp3"
        generate_english_audio(scripts["english"], en_path)
        result["english"] = en_path

    if "myanmar" in languages:
        my_path = out_dir / f"{stem}_my.mp3"
        generate_myanmar_audio(scripts["myanmar"], my_path)
        result["myanmar"] = my_path

    return result
