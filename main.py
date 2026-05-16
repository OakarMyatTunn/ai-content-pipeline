"""
AI Content Pipeline — Main Entry Point
=======================================
Starts two services:
  1. File Watcher  → watches /input/ for new video files → triggers recap pipeline
  2. APScheduler   → fires daily at 10:15 AM Malaysia time → triggers animal pipeline
                     Also checks on startup if today's animal run was missed.

Usage:
  python main.py

Keep this running in the background. Use NSSM to run as a Windows Service
(see SETUP.md for instructions).
"""
import time
import sys
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from rich.console import Console

from modules.shared.config_loader import cfg
from modules.shared.logger import log

console = Console()

# Supported video extensions
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".flv"}

# Cooldown — ignore duplicate events within 5 seconds of each file
_processing: set[str] = set()


# ── File Watcher ──────────────────────────────────────────────────────────────

class VideoDropHandler(FileSystemEventHandler):
    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            return
        if str(path) in _processing:
            return

        _processing.add(str(path))
        log.info(f"New video detected: {path.name}")

        # Small delay — wait for file copy to finish before processing
        time.sleep(3)

        try:
            from modules.recap.pipeline import run as recap_run
            recap_run(path)
        except Exception as e:
            log.error(f"Recap pipeline failed: {e}")
        finally:
            _processing.discard(str(path))


# ── Scheduler Jobs ────────────────────────────────────────────────────────────

def run_animal_pipeline():
    try:
        from modules.animals.pipeline import run as animal_run
        animal_run()
    except Exception as e:
        log.error(f"Animal pipeline failed: {e}")


def startup_catchup():
    """
    On startup: check if today's animal pipeline hasn't run yet.
    This handles the case where the machine was off at scheduled time.
    """
    from modules.animals.pipeline import _already_ran_today, run as animal_run
    if not _already_ran_today():
        log.info("Startup catch-up: today's animal pipeline hasn't run — starting now...")
        try:
            animal_run()
        except Exception as e:
            log.error(f"Catch-up animal pipeline failed: {e}")
    else:
        log.info("Startup catch-up: animal pipeline already ran today ✓")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.rule("[bold green]AI Content Pipeline[/bold green]")
    log.info("Starting AI Content Pipeline...")

    # Validate config
    try:
        cfg.validate()
        log.info("Config validated ✓")
    except EnvironmentError as e:
        log.error(str(e))
        sys.exit(1)

    # Ensure folders exist
    for folder in [cfg.INPUT_FOLDER, cfg.OUTPUT_RECAP, cfg.OUTPUT_ANIMALS,
                   cfg.MUSIC_FOLDER, cfg.LOGS_FOLDER]:
        folder.mkdir(parents=True, exist_ok=True)

    # ── Start file watcher ────────────────────────────────────────────────
    handler  = VideoDropHandler()
    observer = Observer()
    observer.schedule(handler, str(cfg.INPUT_FOLDER), recursive=False)
    observer.start()
    log.info(f"Watching for videos in: {cfg.INPUT_FOLDER}")

    # ── Start scheduler ───────────────────────────────────────────────────
    tz = pytz.timezone(cfg.ANIMAL_TZ)
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        run_animal_pipeline,
        CronTrigger(
            hour=cfg.ANIMAL_HOUR,
            minute=cfg.ANIMAL_MINUTE,
            timezone=tz,
        ),
        id="animal_daily",
        name="Daily Animal Content",
        max_instances=1,
        misfire_grace_time=3600,  # run up to 1hr late if missed
    )
    scheduler.start()
    log.info(
        f"Scheduler started — animal pipeline fires daily at "
        f"{cfg.ANIMAL_HOUR:02d}:{cfg.ANIMAL_MINUTE:02d} {cfg.ANIMAL_TZ}"
    )

    # ── Startup catch-up check ────────────────────────────────────────────
    startup_catchup()

    # ── Keep alive ────────────────────────────────────────────────────────
    console.rule("[green]Pipeline running — drop videos into /input/ to start a recap[/green]")
    log.info("Pipeline running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        observer.stop()
        scheduler.shutdown()

    observer.join()
    log.info("Pipeline stopped.")


if __name__ == "__main__":
    main()
