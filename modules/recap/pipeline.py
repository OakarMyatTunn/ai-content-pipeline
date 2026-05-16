"""
Recap pipeline orchestrator.
Called by the file watcher when a new video is dropped into /input/.
"""
from pathlib import Path
from datetime import datetime
from modules.shared.config_loader import cfg
from modules.shared.logger import log
from modules.shared.telegram_bot import send_message, send_approval_request
from modules.recap.transcriber import transcribe
from modules.recap.script_generator import generate_scripts
from modules.recap.tts import generate_all as generate_tts
from modules.recap.video_assembler import build_video


def run(video_path: Path) -> None:
    stem = video_path.stem
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    job_id = f"{stem}_{ts}"
    out_dir = cfg.OUTPUT_RECAP / job_id

    log.info(f"{'='*60}")
    log.info(f"RECAP PIPELINE START: {video_path.name}")
    log.info(f"{'='*60}")
    send_message(f"🎬 Recap pipeline started for:\n<code>{video_path.name}</code>")

    try:
        # ── Step 1: Transcribe ───────────────────────────────────────────────
        log.info("[1/5] Transcribing...")
        result = transcribe(video_path)
        srt       = result["srt"]
        segments  = result["segments"]

        # Save SRT
        out_dir.mkdir(parents=True, exist_ok=True)
        srt_path = out_dir / f"{job_id}.srt"
        srt_path.write_text(srt, encoding="utf-8")
        log.info(f"SRT saved → {srt_path.name}")

        # ── Step 2: Generate Scripts ─────────────────────────────────────────
        log.info("[2/5] Generating scripts...")
        scripts = generate_scripts(srt, stem)
        (out_dir / f"{job_id}_script_en.txt").write_text(scripts["english"], encoding="utf-8")
        (out_dir / f"{job_id}_script_my.txt").write_text(scripts["myanmar"], encoding="utf-8")

        # ── Step 3: Approval Gate ────────────────────────────────────────────
        log.info("[3/5] Awaiting Telegram approval...")
        decision = send_approval_request(
            movie_name=video_path.name,
            script_en=scripts["english"],
            script_my=scripts["myanmar"],
        )

        if decision == "rejected":
            send_message(f"❌ Recap rejected for <code>{video_path.name}</code>. Pipeline stopped.")
            log.info("Recap rejected by user. Stopping.")
            return

        if decision == "regenerate":
            log.info("Regenerating scripts...")
            send_message("🔄 Regenerating scripts...")
            scripts = generate_scripts(srt, stem)
            (out_dir / f"{job_id}_script_en_v2.txt").write_text(scripts["english"], encoding="utf-8")
            (out_dir / f"{job_id}_script_my_v2.txt").write_text(scripts["myanmar"], encoding="utf-8")
            send_message("✅ New scripts generated. Proceeding to voiceover.")

        # ── Step 4: TTS ──────────────────────────────────────────────────────
        log.info("[4/5] Generating voiceovers...")
        audio = generate_tts(scripts, out_dir, job_id)

        # ── Step 5: Assemble Videos ──────────────────────────────────────────
        log.info("[5/5] Assembling videos...")
        all_outputs = []

        for lang in ["english", "myanmar"]:
            log.info(f"  Building {lang} version...")
            outputs = build_video(
                source_video=video_path,
                audio_path=audio[lang],
                segments=segments,
                scripts=scripts,
                lang=lang,
                out_dir=out_dir,
                stem=job_id,
            )
            all_outputs.append((lang, outputs))

        # ── Done ─────────────────────────────────────────────────────────────
        summary = f"✅ <b>Recap Complete!</b>\nJob: <code>{job_id}</code>\n\n"
        for lang, outputs in all_outputs:
            summary += f"<b>{lang.upper()}</b>\n"
            for platform, path in outputs.items():
                size_mb = path.stat().st_size / 1024 / 1024
                summary += f"  • {platform}: {path.name} ({size_mb:.1f} MB)\n"
        summary += f"\n📂 Folder: <code>{out_dir}</code>"

        send_message(summary)
        log.info(f"RECAP PIPELINE COMPLETE: {job_id}")

    except Exception as e:
        log.exception(f"Pipeline error: {e}")
        send_message(f"❌ <b>Pipeline Error</b>\n<code>{str(e)}</code>")
        raise
