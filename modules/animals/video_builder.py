"""
Animal Module — Step 3.
Builds educational narration video:
1. Generate TTS narration audio (Edge TTS — English)
2. Get audio duration via ffprobe
3. Resize frames to 9:16, spread across audio duration
4. Assemble frames into video matching audio length
5. Burn timed word captions (PIL — no fontconfig needed)
6. Mix narration + background music (music at 20% volume)
7. Final export for TikTok/YouTube/Facebook
"""
import asyncio
import json
import subprocess
import random
import tempfile
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from modules.shared.config_loader import cfg
from modules.shared.logger import log
from modules.shared.ffmpeg_utils import ff_cmd, get_ffmpeg


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list, label: str = "") -> None:
    result = subprocess.run(ff_cmd(cmd), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error [{label}]:\n{result.stderr[-800:]}")


def _ffprobe_duration(path: Path) -> float:
    """Get audio/video duration in seconds using ffprobe."""
    ffmpeg = get_ffmpeg()
    ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
    result = subprocess.run(
        [ffprobe, "-v", "quiet", "-print_format", "json",
         "-show_format", str(path)],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        # Fallback: estimate from file size
        return 60.0


def _pick_music(music_dir: Path):
    if not music_dir.exists():
        return None
    tracks = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    return random.choice(tracks) if tracks else None


# ── TTS ───────────────────────────────────────────────────────────────────────

async def _generate_tts(text: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=cfg.EN_TTS_VOICE)
    await communicate.save(str(out_path))


def generate_narration(narration: str, out_path: Path) -> Path:
    log.info("Generating narration audio (Edge TTS)...")
    asyncio.run(_generate_tts(narration, out_path))
    duration = _ffprobe_duration(out_path)
    log.info(f"Narration audio: {duration:.1f}s → {out_path.name}")
    return out_path


# ── Caption frames ────────────────────────────────────────────────────────────

def _get_font(size: int) -> ImageFont.ImageFont:
    """Get best available font — tries Windows system fonts."""
    candidates = [
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _make_subtitle_image(text: str, width: int, font_size: int = 48) -> Image.Image:
    """Render a subtitle line as RGBA PNG — semi-transparent black bar + white text."""
    font = _get_font(font_size)
    # Wrap long lines
    wrapped = textwrap.fill(text, width=28)
    lines = wrapped.split("\n")
    line_h = font_size + 12
    bar_h = line_h * len(lines) + 20
    img = Image.new("RGBA", (width, bar_h), (0, 0, 0, 180))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = max(10, (width - tw) // 2)
        y = 10 + i * line_h
        # Shadow
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 200))
        # Main text
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
    return img


def _build_subtitle_video(
    base_video: Path,
    narration: str,
    audio_duration: float,
    tmp_path: Path,
    width: int,
    height: int,
) -> Path:
    """
    Burns timed subtitles into the video using ffmpeg overlay.
    Splits narration into chunks, times them evenly across audio duration.
    Uses PIL PNG overlay (no fontconfig needed on Windows).
    """
    words = narration.split()
    # ~3 words per subtitle chunk — readable pace
    chunk_size = 3
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    chunk_duration = audio_duration / len(chunks)

    # Build a filter_complex overlay chain
    # Each subtitle is a PNG rendered by PIL, overlaid for its time window
    subtitle_pngs = []
    for i, chunk in enumerate(chunks):
        img = _make_subtitle_image(chunk, width)
        p = tmp_path / f"sub_{i:04d}.png"
        img.save(str(p))
        subtitle_pngs.append((p, i * chunk_duration, (i + 1) * chunk_duration))

    # Build ffmpeg overlay filter — stack all subtitle overlays
    # Input 0 = base video, inputs 1..N = subtitle PNGs
    inputs = ["-i", str(base_video)]
    for p, _, _ in subtitle_pngs:
        inputs += ["-i", str(p)]

    # Build filter_complex
    # Each subtitle overlays at bottom of frame for its time window
    y_pos = height - 160  # position from top
    filter_parts = []
    prev = "[0:v]"
    for idx, (_, t_start, t_end) in enumerate(subtitle_pngs):
        inp_label = f"[{idx+1}:v]"
        out_label = f"[v{idx}]"
        enable = f"enable='between(t,{t_start:.3f},{t_end:.3f})'"
        filter_parts.append(
            f"{prev}{inp_label}overlay=0:{y_pos}:{enable}{out_label}"
        )
        prev = out_label

    filter_complex = ";".join(filter_parts)

    sub_video = tmp_path / "subtitled.mp4"
    cmd = (
        ["ffmpeg", "-y"]
        + inputs
        + ["-filter_complex", filter_complex,
           "-map", prev,
           "-map", "0:a?",
           "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
           "-c:a", "copy",
           str(sub_video)]
    )
    _run(cmd, "subtitles")
    return sub_video


# ── Main builder ──────────────────────────────────────────────────────────────

def build_animal_video(frames: list, concept: dict, out_dir: Path, stem: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    narration = concept.get("narration", concept.get("title", "Amazing animal facts!"))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # ── 1. Generate narration audio ──────────────────────────────────────
        audio_path = tmp_path / "narration.mp3"
        generate_narration(narration, audio_path)
        audio_duration = _ffprobe_duration(audio_path)
        # Add 1 second buffer at end
        video_duration = audio_duration + 1.0
        frame_duration = video_duration / len(frames)

        # ── 2. Resize frames to 9:16 ─────────────────────────────────────────
        resized = []
        for i, frame in enumerate(frames):
            out_frame = tmp_path / f"r_{i:04d}.png"
            _run([
                "ffmpeg", "-y", "-i", str(frame),
                "-vf", (
                    f"scale={cfg.VIDEO_WIDTH}:{cfg.VIDEO_HEIGHT}"
                    f":force_original_aspect_ratio=increase,"
                    f"crop={cfg.VIDEO_WIDTH}:{cfg.VIDEO_HEIGHT},"
                    f"format=rgb24"
                ),
                str(out_frame),
            ], f"resize {i}")
            resized.append(out_frame)

        # ── 3. Build frame concat list ────────────────────────────────────────
        concat_txt = tmp_path / "frames.txt"
        lines = []
        for p in resized:
            lines.append(f"file '{str(p).replace(chr(92), '/')}'")
            lines.append(f"duration {frame_duration:.3f}")
        lines.append(f"file '{str(resized[-1]).replace(chr(92), '/')}'")
        concat_txt.write_text("\n".join(lines), encoding="utf-8")

        # ── 4. Create base video ──────────────────────────────────────────────
        base_video = tmp_path / "base.mp4"
        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-vf", f"fps={cfg.VIDEO_FPS}",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            str(base_video),
        ], "base video")

        # ── 5. Burn subtitles ─────────────────────────────────────────────────
        log.info("Burning timed subtitles...")
        sub_video = _build_subtitle_video(
            base_video, narration, audio_duration,
            tmp_path, cfg.VIDEO_WIDTH, cfg.VIDEO_HEIGHT
        )

        # ── 6. Mix narration + background music ───────────────────────────────
        music_path = _pick_music(cfg.MUSIC_FOLDER)
        final_video = tmp_path / "final.mp4"

        if music_path:
            log.info(f"Mixing narration + music: {music_path.name}")
            _run([
                "ffmpeg", "-y",
                "-i", str(sub_video),
                "-i", str(audio_path),
                "-stream_loop", "-1", "-i", str(music_path),
                "-filter_complex", (
                    # Narration at full volume, music at 20% in background
                    f"[1:a]volume=1.0[narr];"
                    f"[2:a]volume=0.2,atrim=duration={video_duration}[music];"
                    f"[narr][music]amix=inputs=2:duration=first[aout]"
                ),
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(final_video),
            ], "mix audio")
        else:
            # Just narration, no music
            log.warning("No music found — using narration only")
            _run([
                "ffmpeg", "-y",
                "-i", str(sub_video),
                "-i", str(audio_path),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(final_video),
            ], "add narration")

        # ── 7. Final export ───────────────────────────────────────────────────
        out_path = out_dir / f"{stem}.mp4"
        _run([
            "ffmpeg", "-y", "-i", str(final_video),
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out_path),
        ], "final export")

    size_mb = out_path.stat().st_size / 1024 / 1024
    log.info(f"Educational video ready: {out_path.name} ({size_mb:.1f} MB)")
    return out_path
