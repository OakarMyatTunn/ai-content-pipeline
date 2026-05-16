"""
Animal content pipeline orchestrator.
Called by APScheduler daily at 10:15 AM Malaysia time.
Also called on startup if today's job hasn't run yet (catch-up).
Quota-aware: gemini-2.5-flash has 20 RPD free — each video uses 2 calls.
Max 3 videos/day = 6 calls, well within limits.
"""
import json
import time
from pathlib import Path
from datetime import date, datetime
from modules.shared.config_loader import cfg
from modules.shared.logger import log
from modules.shared.telegram_bot import send_message, send_daily_summary
from modules.animals.concept_generator import generate_concept
from modules.animals.image_generator import generate_frames, unload_pipeline
from modules.animals.video_builder import build_animal_video

# Reduced to stay within 20 RPD quota (2 Gemini calls per video)
VIDEOS_PER_DAY = {0: 2, 1: 2, 2: 2, 3: 2, 4: 3, 5: 3, 6: 3}  # Mon–Sun, max 3

_STATE_FILE = Path(__file__).parents[2] / "logs" / "animal_last_run.json"


def _already_ran_today() -> bool:
    if not _STATE_FILE.exists():
        return False
    try:
        state = json.loads(_STATE_FILE.read_text())
        return state.get("date") == str(date.today())
    except Exception:
        return False


def _mark_ran() -> None:
    _STATE_FILE.parent.mkdir(exist_ok=True)
    _STATE_FILE.write_text(json.dumps({
        "date": str(date.today()),
        "ran_at": datetime.now().isoformat(),
    }))


def run(force: bool = False) -> None:
    if not force and _already_ran_today():
        log.info("Animal pipeline already ran today — skipping.")
        return

    today = date.today()
    n_videos = VIDEOS_PER_DAY.get(today.weekday(), 2)
    ts = datetime.now().strftime("%Y%m%d")

    log.info(f"{'='*60}")
    log.info(f"ANIMAL PIPELINE START — {today} — {n_videos} videos")
    log.info(f"{'='*60}")
    send_message(
        f"🐾 <b>Daily animal pipeline starting</b>\n"
        f"Generating <b>{n_videos}</b> videos today..."
    )

    generated = []

    try:
        for i in range(n_videos):
            log.info(f"\n── Video {i+1}/{n_videos} ──")
            stem = f"animal_{ts}_{i+1:02d}"
            out_dir = cfg.OUTPUT_ANIMALS / ts

            # Step 1: Generate concept (1 Gemini call)
            # Small delay between calls to respect RPM limits
            if i > 0:
                log.info("Waiting 10s between Gemini calls (rate limit safety)...")
                time.sleep(10)

            concept = generate_concept()

            # Step 2: Generate frames (local GPU — no API calls)
            frame_dir = out_dir / f"frames_{i+1:02d}"
            frames = generate_frames(concept, frame_dir)

            # Step 3: Build video (local ffmpeg — no API calls)
            video_path = build_animal_video(frames, concept, out_dir, stem)

            generated.append({
                "path": video_path,
                "caption": concept.get("caption", ""),
                "title": concept.get("title", ""),
                "animal": concept.get("animal", ""),
                "narration": concept.get("narration", "")[:120] + "...",
            })

            log.info(f"Video {i+1} complete: {video_path.name}")

        # Free GPU memory when done
        unload_pipeline()
        _mark_ran()

        # Send Telegram summary
        send_daily_summary(generated)
        log.info(f"ANIMAL PIPELINE COMPLETE — {len(generated)} videos")

    except Exception as e:
        log.exception(f"Animal pipeline error: {e}")
        send_message(f"❌ <b>Animal pipeline error</b>\n<code>{str(e)}</code>")
        raise


def run_for_animal(animal: str) -> None:
    """
    Generate one educational video for a specific animal (manual trigger).
    Called from scripts/generate_animal.py
    """
    from datetime import datetime
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    stem = f"animal_{animal.replace(' ', '_')}_{ts}"
    out_dir = cfg.OUTPUT_ANIMALS / ts

    log.info(f"{'='*60}")
    log.info(f"MANUAL ANIMAL VIDEO: {animal}")
    log.info(f"{'='*60}")
    send_message(f"🐾 <b>Generating video for:</b> <code>{animal}</code>")

    try:
        # Step 1: Generate concept for this specific animal
        concept = generate_concept(animal=animal)

        # Step 2: Generate illustrated frames
        frame_dir = out_dir / "frames"
        frames = generate_frames(concept, frame_dir)

        # Step 3: Build narrated video
        video_path = build_animal_video(frames, concept, out_dir, stem)

        # Free GPU memory
        unload_pipeline()

        # Notify via Telegram
        summary = (
            f"✅ <b>Animal video ready!</b>\n"
            f"🐾 Animal: <code>{animal}</code>\n"
            f"📁 File: <code>{video_path.name}</code>\n\n"
            f"📋 <b>Caption to copy:</b>\n"
            f"<code>{concept.get('caption', '')}</code>"
        )
        send_message(summary)
        log.info(f"MANUAL VIDEO COMPLETE: {video_path.name}")

    except Exception as e:
        log.exception(f"Manual pipeline error: {e}")
        send_message(f"❌ <b>Error generating {animal}</b>\n<code>{str(e)}</code>")
        raise
