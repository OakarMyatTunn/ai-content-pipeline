"""
Step 1 of recap pipeline.
- Extracts audio from video using ffmpeg
- Transcribes with Faster-Whisper on GPU (RTX 3050)
- Returns SRT string + list of timed segments
"""
import subprocess
import tempfile
from pathlib import Path
from faster_whisper import WhisperModel
from modules.shared.config_loader import cfg
from modules.shared.logger import log


_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    """Lazy-load — keeps GPU memory free until needed."""
    global _model
    if _model is None:
        log.info(f"Loading Whisper [{cfg.WHISPER_MODEL}] on {cfg.WHISPER_DEVICE}...")
        _model = WhisperModel(
            cfg.WHISPER_MODEL,
            device=cfg.WHISPER_DEVICE,
            compute_type=cfg.WHISPER_COMPUTE_TYPE,
        )
        log.info("Whisper model loaded ✓")
    return _model


def extract_audio(video_path: Path, out_dir: Path) -> Path:
    """Extract mono 16kHz WAV from video using ffmpeg."""
    audio_path = out_dir / (video_path.stem + "_audio.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",                    # no video
        "-acodec", "pcm_s16le",   # WAV
        "-ar", "16000",           # 16kHz (Whisper requirement)
        "-ac", "1",               # mono
        str(audio_path),
    ]
    log.info(f"Extracting audio: {video_path.name} → {audio_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed:\n{result.stderr}")
    log.info(f"Audio extracted ({audio_path.stat().st_size // 1024 // 1024} MB)")
    return audio_path


def transcribe(video_path: Path) -> dict:
    """
    Full transcription pipeline.
    Returns:
        {
          "srt": str,           # full SRT text
          "segments": [...],    # list of {start, end, text}
          "audio_path": Path,
          "language": str,
        }
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        audio_path = extract_audio(video_path, tmp_path)

        model = _get_model()
        log.info("Transcribing audio (this takes 8–15 min for a 2hr movie)...")

        segments_gen, info = model.transcribe(
            str(audio_path),
            beam_size=5,
            vad_filter=True,            # skip silent gaps
            vad_parameters={"min_silence_duration_ms": 500},
        )

        log.info(f"Detected language: {info.language} ({info.language_probability:.1%})")

        segments = []
        for seg in segments_gen:
            segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            })

        srt = _to_srt(segments)
        log.info(f"Transcription complete — {len(segments)} segments")

        return {
            "srt": srt,
            "segments": segments,
            "language": info.language,
        }


def _to_srt(segments: list[dict]) -> str:
    """Convert segment list to SRT format string."""
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_time(seg['start'])} --> {_fmt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def _fmt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds) // 60 % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
