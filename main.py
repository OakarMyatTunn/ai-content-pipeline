"""
MyannAI Content Pipeline — Main Entry Point
============================================
Runs two services simultaneously:

  1. Recap Bot (Telegram)
     - Receives video files from user via Telegram
     - Runs full recap pipeline per file
     - Sends results back via Telegram

  2. Animal Scheduler (APScheduler)
     - Fires daily at 10:15 AM Malaysia time
     - Generates educational animal content
     - Sends to Telegram automatically

Usage:
  python main.py

Run as Windows Service with NSSM (see SETUP.md).
"""
import sys
import time
import threading
from rich.console import Console

from modules.shared.config_loader import cfg
from modules.shared.logger import log

console = Console()


# ── Animal Scheduler (background thread) ─────────────────────────────────────

def start_animal_scheduler():
    """Run APScheduler in a background thread."""
    import pytz
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    def run_animals():
        try:
            from modules.animals.pipeline import run as animal_run
            animal_run()
        except Exception as e:
            log.error(f"Animal pipeline failed: {e}")

    tz = pytz.timezone(cfg.ANIMAL_TZ)
    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(
        run_animals,
        CronTrigger(hour=cfg.ANIMAL_HOUR, minute=cfg.ANIMAL_MINUTE, timezone=tz),
        id="animal_daily",
        max_instances=1,
        misfire_grace_time=3600,
    )
    log.info(
        f"Animal scheduler: fires daily at "
        f"{cfg.ANIMAL_HOUR:02d}:{cfg.ANIMAL_MINUTE:02d} {cfg.ANIMAL_TZ}"
    )

    # Startup catchup
    try:
        from modules.animals.pipeline import _already_ran_today, run as animal_run
        if not _already_ran_today():
            log.info("Startup catchup: running today's animal pipeline...")
            threading.Thread(target=animal_run, daemon=True).start()
    except Exception as e:
        log.warning(f"Startup catchup failed: {e}")

    scheduler.start()  # blocks


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.rule("[bold cyan]MyannAI Content Pipeline[/bold cyan]")
    log.info("Starting...")

    # Validate config
    try:
        cfg.validate()
        log.info("Config validated ✓")
    except EnvironmentError as e:
        log.error(str(e))
        sys.exit(1)

    # Ensure folders exist
    for folder in [
        cfg.INPUT_FOLDER,
        cfg.INPUT_FOLDER / "queue",
        cfg.OUTPUT_RECAP,
        cfg.OUTPUT_ANIMALS,
        cfg.MUSIC_FOLDER,
        cfg.LOGS_FOLDER,
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    # Start animal scheduler in background thread
    animal_thread = threading.Thread(
        target=start_animal_scheduler, daemon=True, name="AnimalScheduler"
    )
    animal_thread.start()
    log.info("Animal scheduler thread started ✓")

    # Start Telegram recap bot (blocking — runs forever)
    console.rule("[green]Pipeline running — send a video to your Telegram bot[/green]")
    log.info("Starting Telegram recap bot...")

    from modules.shared.telegram_bot import RecapBot
    bot = RecapBot()
    bot.run()  # blocks until Ctrl+C or service stop


if __name__ == "__main__":
    main()
