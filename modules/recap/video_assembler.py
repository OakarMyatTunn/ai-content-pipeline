"""
Step 4 of recap pipeline.
- Selects key scenes using Whisper timestamps
- Clips scenes (3–4 sec cuts) with ffmpeg
- Crops to 9:16 (1080×1920)
- Overlays voiceover audio
- Burns styled subtitles
- Applies light copyright mitigation filters
- Exports for TikTok / Facebook / YouTube Shorts
"""
import subprocess
from modules.shared.ffmpeg_utils import ff_cmd
import tempfile
import random
from pathlib import Path
from modules.shared.config_loader import cfg
from modules.shared.logger import log

# Platform export profiles
PLATFORMS = {
    "tiktok":    {"suffix": "_tiktok.mp4",    "crf": "23", "preset": "fast"},
    "facebook":  {"suffix": "_facebook.mp4",  "crf": "23", "preset": "fast"},
    "ytshorts":  {"suffix": "_ytshorts.mp4",  "crf": "22", "preset": "fast"},
}

# Subtitle style (ASS override string)
SUBTITLE_STYLE = (
    "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,Outline=2,Shadow=1,"
    "Alignment=2,MarginV=60"
)


def select_key_segments(segments: list[dict], max_duration: int = 180) -> list[dict]:
    """
    Pick engaging segments up to max_duration seconds total.
    Strategy: first 10s (hook), spread across middle, last 10s (cliffhanger).
    Clips are capped at 4 seconds each to help with Content ID avoidance.
    """
    MAX_CLIP = 4.0
    selected = []
    total = 0.0

    # Always include opening hook (first ~10 seconds of content)
    for seg in segments[:5]:
        dur = min(seg["end"] - seg["start"], MAX_CLIP)
        selected.append({**seg, "clip_duration": dur})
        total += dur
        if total >= 10:
            break

    # Sample from middle
    mid = segments[len(segments) // 4 : 3 * len(segments) // 4]
    step = max(1, len(mid) // 20)
    for seg in mid[::step]:
        if total >= max_duration - 15:
            break
        dur = min(seg["end"] - seg["start"], MAX_CLIP)
        selected.append({**seg, "clip_duration": dur})
        total += dur

    # Always include ending
    for seg in segments[-5:]:
        dur = min(seg["end"] - seg["start"], MAX_CLIP)
        selected.append({**seg, "clip_duration": dur})
        total += dur

    log.info(f"Selected {len(selected)} clips → ~{total:.0f}s total")
    return selected


def _run_ffmpeg(cmd: list, label: str = "") -> None:
    log.info(f"ffmpeg {label}...")
    result = subprocess.run(ff_cmd(cmd), capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"ffmpeg failed: {result.stderr[-500:]}")
        raise RuntimeError(f"ffmpeg error in {label}")


def build_video(
    source_video: Path,
    audio_path: Path,
    segments: list[dict],
    scripts: dict,        # {"english": str, "myanmar": str}
    lang: str,            # "english" or "myanmar"
    out_dir: Path,
    stem: str,
) -> dict[str, Path]:
    """
    Assemble the full recap video for one language.
    Returns: {"tiktok": Path, "facebook": Path, "ytshorts": Path}
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = select_key_segments(segments)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        clip_paths = []

        # ── 1. Extract individual clips ─────────────────────────────────────
        for i, seg in enumerate(selected):
            clip_out = tmp_path / f"clip_{i:04d}.mp4"
            # Slight random zoom (1.02–1.06×) for copyright mitigation
            zoom = round(random.uniform(1.02, 1.06), 3)
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-ss", str(seg["start"]),
                "-i", str(source_video),
                "-t", str(seg["clip_duration"]),
                "-vf", (
                    f"scale={cfg.VIDEO_WIDTH*2}:{cfg.VIDEO_HEIGHT*2},"
                    f"zoompan=z={zoom}:d=1:s={cfg.VIDEO_WIDTH}x{cfg.VIDEO_HEIGHT},"
                    f"crop={cfg.VIDEO_WIDTH}:{cfg.VIDEO_HEIGHT},"   # 9:16 crop
                    f"eq=saturation=1.1:contrast=1.05"              # slight grade
                ),
                "-an",      # no audio in clip (we overlay voiceover later)
                "-c:v", "libx264", "-preset", "ultrafast",
                str(clip_out),
            ], f"clip {i+1}/{len(selected)}")
            clip_paths.append(clip_out)

        # ── 2. Concatenate clips ─────────────────────────────────────────────
        concat_list = tmp_path / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p}'" for p in clip_paths), encoding="utf-8"
        )
        raw_video = tmp_path / "raw_concat.mp4"
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(raw_video),
        ], "concat")

        # ── 3. Generate SRT for voiceover subtitles ──────────────────────────
        script_text = scripts[lang]
        srt_path = tmp_path / f"subs_{lang}.srt"
        _write_simple_srt(script_text, srt_path)

        # ── 4. Overlay voiceover + burn subtitles ────────────────────────────
        mixed_video = tmp_path / f"mixed_{lang}.mp4"
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(raw_video),
            "-i", str(audio_path),
            "-vf", f"subtitles={srt_path}:force_style='{SUBTITLE_STYLE}'",
            "-c:v", "libx264",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",       # trim to whichever track ends first
            str(mixed_video),
        ], "mix voiceover + subtitles")

        # ── 5. Export per platform ───────────────────────────────────────────
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
                "-movflags", "+faststart",   # web-friendly
                str(out_path),
            ], f"export {platform}")
            outputs[platform] = out_path
            log.info(f"✓ {platform}: {out_path.name}")

    return outputs


def _write_simple_srt(script: str, path: Path) -> None:
    """
    Split script into ~8-word subtitle chunks and write SRT.
    Timing is approximate (evenly distributed) — good enough for recap style.
    """
    words = script.split()
    chunk_size = 8
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

    # Estimate ~0.5s per word
    time_per_chunk = chunk_size * 0.5
    lines = []
    for i, chunk in enumerate(chunks):
        start = i * time_per_chunk
        end = start + time_per_chunk
        lines.append(str(i + 1))
        lines.append(f"{_fmt(start)} --> {_fmt(end)}")
        lines.append(chunk)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _fmt(s: float) -> str:
    ms = int((s % 1) * 1000)
    sec = int(s) % 60
    m = int(s) // 60 % 60
    h = int(s) // 3600
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
