"""
Step 4 of recap pipeline.
- Selects key scenes using Whisper timestamps
- Clips scenes (3-4 sec cuts) with ffmpeg
- Crops to 9:16 (1080x1920)
- Overlays voiceover audio
- Burns subtitles via PIL overlay (no fontconfig — Windows compatible)
- Applies light copyright mitigation filters
- Exports for TikTok / Facebook / YouTube Shorts
"""
import subprocess
import tempfile
import random
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from modules.shared.ffmpeg_utils import ff_cmd
from modules.shared.config_loader import cfg
from modules.shared.logger import log

PLATFORMS = {
    "tiktok":   {"suffix": "_tiktok.mp4",   "crf": "23", "preset": "fast"},
    "facebook": {"suffix": "_facebook.mp4", "crf": "23", "preset": "fast"},
    "ytshorts": {"suffix": "_ytshorts.mp4", "crf": "22", "preset": "fast"},
}


def _run_ffmpeg(cmd: list, label: str = "") -> None:
    log.info(f"ffmpeg {label}...")
    result = subprocess.run(ff_cmd(cmd), capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"ffmpeg failed: {result.stderr[-600:]}")
        raise RuntimeError(f"ffmpeg error in {label}")


def _get_font(size: int) -> ImageFont.ImageFont:
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


def _make_subtitle_png(text: str, width: int, font_size: int = 38) -> Image.Image:
    """Render subtitle text as RGBA PNG — semi-transparent bar + white text."""
    font = _get_font(font_size)
    wrapped = textwrap.fill(text, width=32)
    lines = wrapped.split("\n")
    line_h = font_size + 10
    bar_h = line_h * len(lines) + 20
    img = Image.new("RGBA", (width, bar_h), (0, 0, 0, 170))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = max(10, (width - tw) // 2)
        y = 10 + i * line_h
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
    return img


def _burn_subtitles_pil(
    raw_video: Path,
    audio_path: Path,
    script: str,
    tmp_path: Path,
    lang: str,
) -> Path:
    """
    Burn timed subtitles using PIL PNG overlays — no fontconfig needed.
    Splits script into 8-word chunks, times evenly, overlays each chunk.
    """
    words = script.split()
    chunk_size = 8
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    time_per_chunk = chunk_size * 0.45  # ~0.45s per word

    # Generate subtitle PNGs
    subtitle_data = []
    for i, chunk in enumerate(chunks):
        img = _make_subtitle_png(chunk, cfg.VIDEO_WIDTH)
        p = tmp_path / f"sub_{lang}_{i:04d}.png"
        img.save(str(p))
        t_start = i * time_per_chunk
        t_end = t_start + time_per_chunk
        subtitle_data.append((p, t_start, t_end))

    # Build ffmpeg overlay filter chain
    inputs = ["-i", str(raw_video), "-i", str(audio_path)]
    for p, _, _ in subtitle_data:
        inputs += ["-i", str(p)]

    y_pos = cfg.VIDEO_HEIGHT - 180
    filter_parts = []
    prev = "[0:v]"
    for idx, (_, t_start, t_end) in enumerate(subtitle_data):
        inp = f"[{idx+2}:v]"  # +2 because inputs 0=video, 1=audio
        out = f"[sv{idx}]"
        enable = f"enable='between(t,{t_start:.2f},{t_end:.2f})'"
        filter_parts.append(f"{prev}{inp}overlay=0:{y_pos}:{enable}{out}")
        prev = out

    filter_complex = ";".join(filter_parts)
    mixed_video = tmp_path / f"mixed_{lang}.mp4"

    _run_ffmpeg(
        ["ffmpeg", "-y"]
        + inputs
        + [
            "-filter_complex", filter_complex,
            "-map", prev,
            "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(mixed_video),
        ],
        f"mix voiceover + subtitles ({lang})"
    )
    return mixed_video


def select_key_segments(segments: list[dict], max_duration: int = 180,
                        video_path: Path = None) -> list[dict]:
    """
    Select key segments for clipping.
    If no dialogue segments (music videos etc), falls back to
    evenly-spaced clips across the full video duration.
    """
    MAX_CLIP = 4.0
    selected = []
    total = 0.0

    if segments:
        for seg in segments[:5]:
            dur = min(seg["end"] - seg["start"], MAX_CLIP)
            selected.append({**seg, "clip_duration": dur})
            total += dur
            if total >= 10:
                break

        mid = segments[len(segments) // 4: 3 * len(segments) // 4]
        step = max(1, len(mid) // 20)
        for seg in mid[::step]:
            if total >= max_duration - 15:
                break
            dur = min(seg["end"] - seg["start"], MAX_CLIP)
            selected.append({**seg, "clip_duration": dur})
            total += dur

        for seg in segments[-5:]:
            dur = min(seg["end"] - seg["start"], MAX_CLIP)
            selected.append({**seg, "clip_duration": dur})
            total += dur

    # Fallback: no segments or very few — use evenly spaced clips
    if len(selected) < 5 and video_path and video_path.exists():
        log.warning("Few/no dialogue segments — using evenly spaced clips")
        # Get video duration via ffprobe
        import subprocess, json
        from modules.shared.ffmpeg_utils import get_ffmpeg
        ffmpeg = get_ffmpeg()
        ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
        try:
            r = subprocess.run(
                [ffprobe, "-v", "quiet", "-print_format", "json",
                 "-show_format", str(video_path)],
                capture_output=True, text=True
            )
            vid_dur = float(json.loads(r.stdout)["format"]["duration"])
        except Exception:
            vid_dur = 300.0  # assume 5 min if detection fails

        n_clips = min(40, int(max_duration / MAX_CLIP))
        interval = vid_dur / (n_clips + 1)
        selected = []
        for i in range(n_clips):
            t_start = interval * (i + 1)
            selected.append({
                "start": t_start,
                "end": t_start + MAX_CLIP,
                "text": "",
                "clip_duration": MAX_CLIP,
            })
        total = n_clips * MAX_CLIP

    log.info(f"Selected {len(selected)} clips → ~{total:.0f}s total")
    return selected


def build_video(
    source_video: Path,
    audio_path: Path,
    segments: list[dict],
    scripts: dict,
    lang: str,
    out_dir: Path,
    stem: str,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = select_key_segments(segments, video_path=source_video)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        clip_paths = []

        # ── 1. Extract clips ──────────────────────────────────────────────────
        for i, seg in enumerate(selected):
            clip_out = tmp_path / f"clip_{i:04d}.mp4"
            zoom = round(random.uniform(1.02, 1.06), 3)
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-ss", str(seg["start"]),
                "-i", str(source_video),
                "-t", str(seg["clip_duration"]),
                "-vf", (
                    f"scale={cfg.VIDEO_WIDTH*2}:{cfg.VIDEO_HEIGHT*2},"
                    f"zoompan=z={zoom}:d=1:s={cfg.VIDEO_WIDTH}x{cfg.VIDEO_HEIGHT},"
                    f"crop={cfg.VIDEO_WIDTH}:{cfg.VIDEO_HEIGHT},"
                    f"eq=saturation=1.1:contrast=1.05"
                ),
                "-an",
                "-c:v", "libx264", "-preset", "ultrafast",
                str(clip_out),
            ], f"clip {i+1}/{len(selected)}")
            clip_paths.append(clip_out)

        # ── 2. Concatenate ────────────────────────────────────────────────────
        concat_list = tmp_path / "concat.txt"
        # Use forward slashes in paths — ffmpeg concat requires this on Windows
        concat_list.write_text(
            "\n".join(f"file '{str(p).replace(chr(92), '/')}'" for p in clip_paths),
            encoding="utf-8"
        )
        raw_video = tmp_path / "raw_concat.mp4"
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(raw_video),
        ], "concat")

        # ── 3. Burn subtitles + mix audio (PIL — no fontconfig) ───────────────
        mixed_video = _burn_subtitles_pil(
            raw_video, audio_path, scripts[lang], tmp_path, lang
        )

        # ── 4. Export per platform ────────────────────────────────────────────
        outputs = {}
        for platform, profile in PLATFORMS.items():
            out_path = out_dir / f"{stem}_{lang}{profile['suffix']}"
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-i", str(mixed_video),
                "-c:v", "libx264",
                "-crf", profile["crf"],
                "-preset", profile["preset"],
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(out_path),
            ], f"export {platform}")
            outputs[platform] = out_path
            log.info(f"✓ {platform}: {out_path.name}")

    return outputs


def _fmt(s: float) -> str:
    ms = int((s % 1) * 1000)
    sec = int(s) % 60
    m = int(s) // 60 % 60
    h = int(s) // 3600
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
