"""
Animal content pipeline orchestrator.
Called by APScheduler daily at 10:15 AM Malaysia time.
Also called on startup if today's job hasn't run yet (catch-up).
"""
import json
from pathlib import Path
from datetime import date, datetime
from modules.shared.config_loader import cfg
from modules.shared.logger import log
from modules.shared.telegram_bot import send_message, send_daily_summary
from modules.animals.concept_generator import generate_concept
from modules.animals.image_generator import generate_frames, unload_pipeline
from modules.animals.video_builder import build_animal_video

# Number of videos to generate per day (can vary by day)
from datetime import date as _date
VIDEOS_PER_DAY = {0: 2, 1: 2, 2: 2, 3: 2, 4: 3, 5: 3, 6: 3}  # Mon–Sun

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
    """
    Run the daily animal content pipeline.
    Skips if already ran today (unless force=True).
    """
    if not force and _already_ran_today():
        log.info("Animal pipeline already ran today — skipping.")
        return

    today = date.today()
    n_videos = VIDEOS_PER_DAY.get(today.weekday(), 2)
    ts = datetime.now().strftime("%Y%m%d")

    log.info(f"{'='*60}")
    log.info(f"ANIMAL PIPELINE START — {today} — {n_videos} videos")
    log.info(f"{'='*60}")
    send_message(f"🐾 <b>Daily animal pipeline starting</b>\nGenerating <b>{n_videos}</b> videos today...")

    generated = []

    try:
        for i in range(n_videos):
            log.info(f"\n── Video {i+1}/{n_videos} ──")
            stem = f"animal_{ts}_{i+1:02d}"
            out_dir = cfg.OUTPUT_ANIMALS / ts

            # Step 1: Generate concept
            concept = generate_concept()

            # Step 2: Generate frames
            frame_dir = out_dir / f"frames_{i+1:02d}"
            frames = generate_frames(concept, frame_dir)

            # Step 3: Build video
            video_path = build_animal_video(frames, concept, out_dir, stem)

            generated.append({
                "path": video_path,
                "caption": concept.get("caption", ""),
                "style": concept.get("style", "mixed"),
                "title": concept.get("title", ""),
                "animal": concept.get("animal", ""),
            })

            log.info(f"Video {i+1} complete: {video_path.name}")

        # Unload SD from GPU when all done — free VRAM for recap if needed
        unload_pipeline()

        # Mark today's run complete
        _mark_ran()

        # Send Telegram summary
        send_daily_summary(generated)
        log.info(f"ANIMAL PIPELINE COMPLETE — {len(generated)} videos")

    except Exception as e:
        log.exception(f"Animal pipeline error: {e}")
        send_message(f"❌ <b>Animal pipeline error</b>\n<code>{str(e)}</code>")
        raise
