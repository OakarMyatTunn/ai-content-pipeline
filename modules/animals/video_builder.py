"""
Animal Module — Step 3.
Stitches SD frames into a 9:16 viral video with music and caption overlay.
"""
import subprocess
import random
import tempfile
from pathlib import Path
from modules.shared.config_loader import cfg
from modules.shared.logger import log
from modules.shared.ffmpeg_utils import ff_cmd, get_ffmpeg


def _run(cmd: list, label: str = "") -> None:
    result = subprocess.run(ff_cmd(cmd), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error [{label}]: {result.stderr[-600:]}")


def _pick_music(music_dir: Path):
    if not music_dir.exists():
        return None
    tracks = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    return random.choice(tracks) if tracks else None


def build_animal_video(frames, concept, out_dir, stem):
    out_dir.mkdir(parents=True, exist_ok=True)
    total_duration = cfg.ANIMAL_DURATION
    frame_duration = total_duration / len(frames)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # 1. Resize frames to exact 9:16
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

        # 2. Build concat list with durations
        concat_txt = tmp_path / "frames.txt"
        lines = []
        for p in resized:
            lines.append(f"file '{str(p).replace(chr(92), '/')}'")
            lines.append(f"duration {frame_duration:.3f}")
        lines.append(f"file '{str(resized[-1]).replace(chr(92), '/')}'")
        concat_txt.write_text("\n".join(lines), encoding="utf-8")

        # 3. Create base video from frames
        base_video = tmp_path / "base.mp4"
        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-vf", f"fps={cfg.VIDEO_FPS}",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            str(base_video),
        ], "base video")

        # 4. Add caption overlay using PIL (no fontconfig needed on Windows)
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        title = concept.get("title", "Cute Animal")
        # Create a caption PNG overlay
        caption_img = tmp_path / "caption.png"
        img = Image.new("RGBA", (cfg.VIDEO_WIDTH, 120), (0, 0, 0, 160))
        draw = ImageDraw.Draw(img)
        # Use default PIL font (always available)
        try:
            font = ImageFont.truetype("arial.ttf", 52)
        except Exception:
            font = ImageFont.load_default()
        # Center the text
        bbox = draw.textbbox((0, 0), title, font=font)
        text_w = bbox[2] - bbox[0]
        text_x = max(0, (cfg.VIDEO_WIDTH - text_w) // 2)
        draw.text((text_x, 30), title, font=font, fill=(255, 255, 255, 255))
        img.save(str(caption_img))

        captioned = tmp_path / "captioned.mp4"
        _run([
            "ffmpeg", "-y",
            "-i", str(base_video),
            "-i", str(caption_img),
            "-filter_complex",
            f"[0:v][1:v]overlay=0:H-120",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(captioned),
        ], "caption")

        # 5. Mix in background music
        music_path = _pick_music(cfg.MUSIC_FOLDER)
        final_video = tmp_path / "final.mp4"

        if music_path:
            log.info(f"Adding music: {music_path.name}")
            _run([
                "ffmpeg", "-y",
                "-i", str(captioned),
                "-stream_loop", "-1", "-i", str(music_path),
                "-filter_complex", (
                    f"[1:a]volume=0.4,atrim=duration={total_duration}[music];"
                    f"[music]afade=t=out:st={total_duration - 2}:d=2[faded]"
                ),
                "-map", "0:v", "-map", "[faded]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                str(final_video),
            ], "music")
        else:
            log.warning("No music — exporting without audio")
            final_video = captioned

        # 6. Final export
        out_path = out_dir / f"{stem}.mp4"
        _run([
            "ffmpeg", "-y", "-i", str(final_video),
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            str(out_path),
        ], "final export")

    size_mb = out_path.stat().st_size / 1024 / 1024
    log.info(f"Animal video ready: {out_path.name} ({size_mb:.1f} MB)")
    return out_path
