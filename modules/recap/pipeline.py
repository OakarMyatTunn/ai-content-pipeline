"""
Recap pipeline — Telegram-first redesign.

Flow:
1. Receive video path (from Telegram bot download)
2. Transcribe with Faster-Whisper (GPU)
3. Generate EN + Myanmar scripts (Gemini)
4. Send scripts to Telegram → wait for language choice
5. Generate Kokoro voiceover for chosen language(s)
6. Assemble 9:16 video with clips + voiceover + subtitles
7. Send final video(s) directly via Telegram
"""
from pathlib import Path
from datetime import datetime
from modules.shared.config_loader import cfg
from modules.shared.logger import log
from modules.shared.telegram_bot import (
    send_message, send_script_and_get_language, send_video
)
from modules.recap.transcriber import transcribe
from modules.recap.script_generator import generate_scripts
from modules.recap.tts import generate_all as generate_tts
from modules.recap.video_assembler import build_video

# Copyright-safe transformations applied to all clips
COPYRIGHT_NOTE = (
    "This is an AI-generated recap for entertainment purposes only. "
    "All rights belong to the original creators."
)


def run(video_path: Path) -> None:
    stem   = video_path.stem
    ts     = datetime.now().strftime("%Y%m%d_%H%M")
    job_id = f"{stem}_{ts}"
    out_dir = cfg.OUTPUT_RECAP / job_id

    log.info(f"{'='*60}")
    log.info(f"RECAP PIPELINE START: {video_path.name}")
    log.info(f"{'='*60}")

    try:
        # ── Step 1: Transcribe ───────────────────────────────────────────────
        log.info("[1/5] Transcribing...")
        send_message(
            f"🎙️ <b>Transcribing:</b> <code>{video_path.name}</code>\n"
            f"This takes 5–15 minutes for large files..."
        )
        result    = transcribe(video_path)
        srt       = result["srt"]
        segments  = result["segments"]

        # Save SRT
        out_dir.mkdir(parents=True, exist_ok=True)
        srt_path = out_dir / f"{job_id}.srt"
        srt_path.write_text(srt, encoding="utf-8")
        log.info(f"Transcription complete — {len(segments)} segments")

        # ── Step 2: Generate Scripts ─────────────────────────────────────────
        log.info("[2/5] Generating scripts...")
        send_message("✍️ Generating English + Myanmar recap scripts...")
        scripts = generate_scripts(srt, stem)

        # Save scripts
        (out_dir / f"{job_id}_script_en.txt").write_text(
            scripts["english"], encoding="utf-8"
        )
        (out_dir / f"{job_id}_script_my.txt").write_text(
            scripts["myanmar"], encoding="utf-8"
        )

        # ── Step 3: Language Choice ──────────────────────────────────────────
        log.info("[3/5] Awaiting language choice...")
        choice = send_script_and_get_language(
            movie_name=video_path.name,
            script_en=scripts["english"],
            script_my=scripts["myanmar"],
        )

        if choice == "cancel":
            send_message(
                f"❌ Recap cancelled for <code>{video_path.name}</code>."
            )
            log.info("Recap cancelled by user.")
            return

        # Map choice to language list
        languages = {
            "english": ["english"],
            "myanmar": ["myanmar"],
            "both":    ["english", "myanmar"],
        }.get(choice, ["english"])

        # ── Step 4: TTS ──────────────────────────────────────────────────────
        log.info("[4/5] Generating voiceovers...")
        send_message(
            f"🎙️ Generating <b>Kokoro</b> voiceover "
            f"({', '.join(languages)})..."
        )
        audio = generate_tts(scripts, out_dir, job_id, languages=languages)

        # ── Step 5: Assemble + Send Videos ───────────────────────────────────
        log.info("[5/5] Assembling videos...")
        send_message("🎬 Assembling video(s)...")

        for lang in languages:
            if lang not in audio:
                continue
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

            # Send each platform file via Telegram
            platform_labels = {
                "tiktok":   "TikTok",
                "facebook": "Facebook Reels",
                "ytshorts": "YouTube Shorts",
            }
            for platform, path in outputs.items():
                if not path.exists():
                    continue
                size_mb = path.stat().st_size / 1024 / 1024
                label = platform_labels.get(platform, platform)
                lang_flag = "🇬🇧" if lang == "english" else "🇲🇲"
                caption = (
                    f"{lang_flag} <b>{label} — {lang.capitalize()}</b>\n"
                    f"📁 {path.name} ({size_mb:.1f}MB)\n\n"
                    f"📋 <b>Caption:</b>\n"
                    f"<code>{COPYRIGHT_NOTE}</code>"
                )
                log.info(f"  Sending {platform} {lang} ({size_mb:.1f}MB)...")
                send_video(path, caption)

        send_message(
            f"✅ <b>All done!</b> <code>{job_id}</code>\n"
            f"Videos sent above ☝️"
        )
        log.info(f"RECAP COMPLETE: {job_id}")

        # Clean up source file from queue
        try:
            video_path.unlink()
            log.info(f"Queue file removed: {video_path.name}")
        except Exception:
            pass

    except Exception as e:
        log.exception(f"Pipeline error: {e}")
        send_message(
            f"❌ <b>Pipeline Error</b>\n"
            f"<code>{str(e)}</code>\n"
            f"Check logs for details."
        )
        raise
