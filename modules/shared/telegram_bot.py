"""
Telegram Bot — Complete redesign for Telegram-first recap workflow.

Flow:
1. User sends video file → bot downloads to queue
2. Bot transcribes → generates EN + Myanmar scripts
3. Bot sends both scripts → asks user to choose language
4. User replies: "english" / "myanmar" / "both"
5. Bot generates Kokoro voiceover + assembles video
6. Bot sends final video(s) directly in chat
"""
import asyncio
import os
import time
from pathlib import Path
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, MessageHandler, CommandHandler,
                          CallbackQueryHandler, ContextTypes, filters)
from modules.shared.config_loader import cfg
from modules.shared.logger import log

# Max file size Telegram bots can receive: 2GB
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024

# ── Simple one-shot send ──────────────────────────────────────────────────────

async def _send_text(text: str, parse_mode: str = "HTML") -> None:
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(write_timeout=60, read_timeout=60)
    bot = Bot(token=cfg.TELEGRAM_BOT_TOKEN, request=request)
    async with bot:
        for chunk in _split(text, 4000):
            await bot.send_message(
                chat_id=cfg.TELEGRAM_CHAT_ID, text=chunk, parse_mode=parse_mode
            )

def send_message(text: str) -> None:
    """Send text message — safe to call from any thread."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(_send_text(text), loop)
            future.result(timeout=60)
        else:
            loop.run_until_complete(_send_text(text))
    except RuntimeError:
        asyncio.run(_send_text(text))


# ── Send video file ───────────────────────────────────────────────────────────

async def _send_video_file(video_path: Path, caption: str = "") -> None:
    from telegram.request import HTTPXRequest
    # Large files need much longer write timeout (default is 20s — too short)
    request = HTTPXRequest(write_timeout=300, read_timeout=300, connect_timeout=30)
    bot = Bot(token=cfg.TELEGRAM_BOT_TOKEN, request=request)
    size_mb = video_path.stat().st_size / 1024 / 1024

    async with bot:
        if size_mb > 50:
            log.info(f"Video {size_mb:.0f}MB > 50MB — sending as document")
            with open(video_path, "rb") as f:
                await bot.send_document(
                    chat_id=cfg.TELEGRAM_CHAT_ID,
                    document=f,
                    caption=caption[:1024],
                    parse_mode="HTML",
                    write_timeout=300,
                    read_timeout=300,
                )
        else:
            with open(video_path, "rb") as f:
                await bot.send_video(
                    chat_id=cfg.TELEGRAM_CHAT_ID,
                    video=f,
                    caption=caption[:1024],
                    parse_mode="HTML",
                    supports_streaming=True,
                    write_timeout=300,
                    read_timeout=300,
                )

def send_video(video_path: Path, caption: str = "") -> None:
    """Send video — safe to call from any thread."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context — schedule as coroutine
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                _send_video_file(video_path, caption), loop
            )
            future.result(timeout=360)
        else:
            loop.run_until_complete(_send_video_file(video_path, caption))
    except RuntimeError:
        # No event loop — create one
        asyncio.run(_send_video_file(video_path, caption))


# ── Language choice gate (blocking) ──────────────────────────────────────────

def send_script_and_get_language(
    movie_name: str,
    script_en: str,
    script_my: str,
) -> str:
    """
    Sends both scripts to Telegram.
    Waits for user to reply with language choice.
    Returns: "english" | "myanmar" | "both"
    """
    result: list[str] = []

    async def _run() -> None:
        app = Application.builder().token(cfg.TELEGRAM_BOT_TOKEN).build()
        bot = app.bot

        # Send EN script preview
        preview_en = script_en[:1000] + ("..." if len(script_en) > 1000 else "")
        await bot.send_message(
            chat_id=cfg.TELEGRAM_CHAT_ID,
            text=(
                f"🎬 <b>Recap Ready — {movie_name}</b>\n\n"
                f"<b>── English Script ──</b>\n{preview_en}"
            ),
            parse_mode="HTML",
        )

        # Send Myanmar script preview
        preview_my = script_my[:1000] + ("..." if len(script_my) > 1000 else "")
        await bot.send_message(
            chat_id=cfg.TELEGRAM_CHAT_ID,
            text=(
                f"<b>── Myanmar Script ──</b>\n{preview_my}\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Reply with your choice:\n"
                f"👉 <code>english</code>\n"
                f"👉 <code>myanmar</code>\n"
                f"👉 <code>both</code>\n"
                f"👉 <code>cancel</code>"
            ),
            parse_mode="HTML",
        )

        # Wait for reply
        async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if str(update.message.chat_id) != str(cfg.TELEGRAM_CHAT_ID):
                return
            text = update.message.text.strip().lower()
            if text in ["english", "myanmar", "both", "cancel"]:
                result.append(text)
                await update.message.reply_text(
                    f"✅ Got it — <b>{text}</b>. Processing now...",
                    parse_mode="HTML"
                )
                await app.stop()

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

        async with app:
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            # Wait up to 30 minutes for reply
            for _ in range(30 * 60):
                if result:
                    break
                await asyncio.sleep(1)
            await app.updater.stop()

    asyncio.run(_run())
    choice = result[0] if result else "cancel"
    log.info(f"Language choice: {choice}")
    return choice


# ── Telegram upload receiver (runs as part of main bot) ──────────────────────

class RecapBot:
    """
    Full Telegram bot that:
    - Receives video files from user
    - Triggers recap pipeline
    - Handles all interaction
    """
    def __init__(self):
        self.app = Application.builder().token(cfg.TELEGRAM_BOT_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help",  self._cmd_help))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        # Video/document uploads
        self.app.add_handler(MessageHandler(filters.VIDEO, self._handle_video))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))
        # URL messages
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🎬 <b>MyannAI Recap Bot</b>\n\n"
            "Send me a video file (up to 2GB) and I'll generate a social media recap.\n\n"
            "📋 <b>Commands:</b>\n"
            "/start — Show this message\n"
            "/help — How to use\n"
            "/status — Check if pipeline is running\n\n"
            "Just send a video to get started! 🚀",
            parse_mode="HTML"
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📖 <b>How to use:</b>\n\n"
            "<b>Option A — YouTube / TikTok / Facebook URL:</b>\n"
            "Paste any public video URL — I'll download it automatically\n\n"
            "<b>Option B — Google Drive link:</b>\n"
            "Upload your video to Google Drive → Share → Anyone with link\n"
            "Then paste the link here — no size limit!\n\n"
            "<b>Option C — Send a file:</b>\n"
            "Send video directly (max 20MB Telegram limit)\n\n"
            "<b>Then:</b>\n"
            "2️⃣ I'll transcribe and generate EN + Myanmar scripts\n"
            "3️⃣ Review both scripts\n"
            "4️⃣ Reply: <code>english</code>, <code>myanmar</code>, or <code>both</code>\n"
            "5️⃣ I send you the final recap video\n\n"
            "⚠️ Files over 2GB: compress with HandBrake (free): https://handbrake.fr",
            parse_mode="HTML"
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        queue_dir = cfg.INPUT_FOLDER / "queue"
        queue_count = len(list(queue_dir.glob("*"))) if queue_dir.exists() else 0
        await update.message.reply_text(
            f"✅ Bot is running\n"
            f"📂 Queue: {queue_count} file(s) pending",
            parse_mode="HTML"
        )

    async def _handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._process_incoming_file(update, context, update.message.video)

    async def _handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        doc = update.message.document
        # Only accept video files sent as documents
        video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.flv'}
        if not any(doc.file_name.lower().endswith(ext) for ext in video_exts):
            await update.message.reply_text(
                "❌ Unsupported file type.\n"
                "Please send a video file: MP4, MKV, AVI, MOV, WMV"
            )
            return
        await self._process_incoming_file(update, context, doc)

    async def _process_incoming_file(self, update, context, file_obj):
        # Check if from authorized user
        if str(update.message.chat_id) != str(cfg.TELEGRAM_CHAT_ID):
            await update.message.reply_text("❌ Unauthorized.")
            return

        # Check file size
        file_size = getattr(file_obj, 'file_size', 0) or 0
        if file_size > MAX_FILE_BYTES:
            size_gb = file_size / 1024 / 1024 / 1024
            await update.message.reply_text(
                f"❌ File too large: {size_gb:.1f}GB\n\n"
                f"Maximum size is 2GB via Telegram.\n"
                f"Compress with HandBrake (free): https://handbrake.fr\n"
                f"Settings: H.264, RF 28, 720p"
            )
            return

        # Get file name
        file_name = getattr(file_obj, 'file_name', None) or "video.mp4"
        size_mb = file_size / 1024 / 1024

        await update.message.reply_text(
            f"✅ <b>Received!</b> {file_name} ({size_mb:.0f}MB)\n\n"
            f"📥 Downloading...",
            parse_mode="HTML"
        )

        try:
            # Download to queue folder
            queue_dir = cfg.INPUT_FOLDER / "queue"
            queue_dir.mkdir(parents=True, exist_ok=True)
            out_path = queue_dir / file_name

            tg_file = await context.bot.get_file(file_obj.file_id)
            await tg_file.download_to_drive(str(out_path))

            await update.message.reply_text(
                f"✅ Downloaded! Starting recap pipeline...\n"
                f"🎙️ Transcribing audio (this takes a few minutes)..."
            )

            # Trigger recap pipeline in background
            import threading
            def run_pipeline():
                from modules.recap.pipeline import run as recap_run
                recap_run(out_path)
            threading.Thread(target=run_pipeline, daemon=True).start()

        except Exception as e:
            log.exception(f"File download error: {e}")
            await update.message.reply_text(f"❌ Download failed: {str(e)}")

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages — check if it's a video URL."""
        if str(update.message.chat_id) != str(cfg.TELEGRAM_CHAT_ID):
            return

        text = update.message.text.strip()

        # Check if it looks like a URL we support
        from modules.shared.downloader import (
            is_supported_url, is_gdrive_url,
            get_video_info, download_url, download_gdrive
        )

        is_gdrive = is_gdrive_url(text)
        is_other = is_supported_url(text)

        if not is_gdrive and not is_other:
            # Not a URL — ignore (could be language reply handled elsewhere)
            return

        import threading
        result_holder = [None]
        error_holder = [None]

        if is_gdrive:
            # Google Drive flow
            await update.message.reply_text(
                "📁 <b>Google Drive link detected!</b>\n"
                "⬇️ Downloading... (large files may take several minutes)",
                parse_mode="HTML"
            )

            last_pct = [0]
            def progress_cb(pct, msg):
                last_pct[0] = pct

            def do_gdrive():
                try:
                    result_holder[0] = download_gdrive(text, progress_cb)
                except Exception as e:
                    error_holder[0] = e

            thread = threading.Thread(target=do_gdrive)
            thread.start()

            while thread.is_alive():
                await asyncio.sleep(10)
                pct = last_pct[0]
                if pct > 0:
                    await update.message.reply_text(
                        f"⬇️ Downloading from Drive... {pct:.0f}%"
                    )
            thread.join()

        else:
            # YouTube / TikTok / other URL flow
            await update.message.reply_text("🔍 Checking video...")
            info = get_video_info(text)
            title = info.get("title", "Unknown")
            duration_min = info.get("duration", 0) // 60

            await update.message.reply_text(
                f"📹 <b>Found:</b> {title}\n"
                f"⏱ Duration: {duration_min} min\n\n"
                f"⬇️ Downloading...",
                parse_mode="HTML"
            )

            last_pct = [0]
            def do_download():
                try:
                    result_holder[0] = download_url(text)
                except Exception as e:
                    error_holder[0] = e

            thread = threading.Thread(target=do_download)
            thread.start()

            while thread.is_alive():
                await asyncio.sleep(8)
                if last_pct[0] > 0:
                    await update.message.reply_text(
                        f"⬇️ Still downloading... {last_pct[0]:.0f}%"
                    )
            thread.join()

        try:
            if error_holder[0]:
                raise error_holder[0]

            video_path = result_holder[0]
            size_mb = video_path.stat().st_size / 1024 / 1024

            await update.message.reply_text(
                f"✅ <b>Downloaded!</b> {video_path.name} ({size_mb:.0f}MB)\n"
                f"🎙️ Starting recap pipeline...",
                parse_mode="HTML"
            )

            def run_pipeline():
                from modules.recap.pipeline import run as recap_run
                recap_run(video_path)

            threading.Thread(target=run_pipeline, daemon=True).start()

        except Exception as e:
            log.exception(f"Download error: {e}")
            source = "Google Drive" if is_gdrive else "URL"
            await update.message.reply_text(
                f"❌ <b>{source} download failed:</b>\n{str(e)}\n\n"
                + (
                    "Make sure the file is shared as <b>Anyone with the link</b> (Viewer)."
                    if is_gdrive else
                    "Check the URL is correct and the video is public."
                ),
                parse_mode="HTML"
            )

    def run(self):
        log.info("Recap bot started — waiting for video files or URLs...")
        self.app.run_polling(drop_pending_updates=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split(text: str, max_len: int) -> list[str]:
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks
