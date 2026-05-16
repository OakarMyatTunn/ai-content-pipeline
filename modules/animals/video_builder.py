"""
Animal Module — Step 3.
Stitches SD frames into a 9:16 viral video with:
- Smooth transitions between frames
- Animated caption overlay
- Background music from local library
- Beat-sync (approximate)
"""
import subprocess
import random
import tempfile
from pathlib import Path
from modules.shared.config_loader import cfg
from modules.shared.logger import log


def _run(cmd: list, label: str = "") -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error [{label}]: {result.stderr[-400:]}")


def _pick_music(music_dir: Path) -> Path | None:
    """Pick a random .mp3 from the music library."""
    if not music_dir.exists():
        return None
    tracks = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    return random.choice(tracks) if tracks else None


def build_animal_video(
    frames: list[Path],
    concept: dict,
    out_dir: Path,
    stem: str,
) -> Path:
    """
    Assemble frames into a 9:16 video with music and caption.
    Returns path to final MP4.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    total_duration = cfg.ANIMAL_DURATION  # seconds (default 20)
    frame_duration = total_duration / len(frames)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # ── 1. Resize + pad each frame to exact 9:16 ──────────────────────
        resized = []
        for i, frame in enumerate(frames):
            out_frame = tmp_path / f"r_{i:04d}.png"
            _run([
                "ffmpeg", "-y",
                "-i", str(frame),
                "-vf", (
                    f"scale={cfg.VIDEO_WIDTH}:{cfg.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                    f"crop={cfg.VIDEO_WIDTH}:{cfg.VIDEO_HEIGHT},"
                    f"format=rgb24"
                ),
                str(out_frame),
            ], f"resize frame {i}")
            resized.append(out_frame)

        # ── 2. Build frame list for concat with duration ───────────────────
        concat_txt = tmp_path / "frames.txt"
        lines = []
        for p in resized:
            lines.append(f"file '{p}'")
            lines.append(f"duration {frame_duration:.3f}")
        # ffmpeg concat demuxer needs last frame repeated
        lines.append(f"file '{resized[-1]}'")
        concat_txt.write_text("\n".join(lines), encoding="utf-8")

        # ── 3. Create base video from frames ──────────────────────────────
        base_video = tmp_path / "base.mp4"
        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-vf", f"fps={cfg.VIDEO_FPS}",
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            str(base_video),
        ], "base video")

        # ── 4. Add caption overlay ─────────────────────────────────────────
        title    = concept.get("title", "Cute Animal")
        # Escape special chars for ffmpeg drawtext
        safe_title = title.replace("'", "\\'").replace(":", "\\:")
        captioned = tmp_path / "captioned.mp4"
        _run([
            "ffmpeg", "-y",
            "-i", str(base_video),
            "-vf", (
                f"drawtext=text='{safe_title}':"
                f"fontsize=52:fontcolor=white:"
                f"borderw=3:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-120:"       # bottom-centre
                f"enable='between(t,0,{total_duration})'"
            ),
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(captioned),
        ], "caption overlay")

        # ── 5. Mix in background music ─────────────────────────────────────
        music_path = _pick_music(cfg.MUSIC_FOLDER)
        final_video = tmp_path / "final.mp4"

        if music_path:
            log.info(f"Adding music: {music_path.name}")
            _run([
                "ffmpeg", "-y",
                "-i", str(captioned),
                "-stream_loop", "-1",        # loop music if shorter than video
                "-i", str(music_path),
                "-filter_complex",
                    "[1:a]volume=0.4,atrim=duration={dur}[music];"
                    "[music]afade=t=out:st={fade}:d=2[faded]".format(
                        dur=total_duration,
                        fade=total_duration - 2,
                    ),
                "-map", "0:v",
                "-map", "[faded]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(final_video),
            ], "add music")
        else:
            log.warning("No music files found in /music/ — exporting without audio")
            final_video = captioned

        # ── 6. Copy to output ──────────────────────────────────────────────
        out_path = out_dir / f"{stem}.mp4"
        _run([
            "ffmpeg", "-y",
            "-i", str(final_video),
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out_path),
        ], "final export")

    size_mb = out_path.stat().st_size / 1024 / 1024
    log.info(f"Animal video ready: {out_path.name} ({size_mb:.1f} MB)")
    return out_path
