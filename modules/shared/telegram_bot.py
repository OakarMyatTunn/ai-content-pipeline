"""
Telegram bot helper.
- send_message()        : plain notification
- send_approval_request(): sends script with Approve/Reject buttons
                           blocks until user responds (used by recap module)
- send_daily_summary()  : sends animal content summary with video paths
"""
import asyncio
from pathlib import Path
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from modules.shared.config_loader import cfg
from modules.shared.logger import log


# ── Simple one-shot send ──────────────────────────────────────────────────────

async def _send(text: str, parse_mode: str = "HTML") -> None:
    bot = Bot(token=cfg.TELEGRAM_BOT_TOKEN)
    # Telegram message limit is 4096 chars — split if needed
    for chunk in _split(text, 4000):
        await bot.send_message(
            chat_id=cfg.TELEGRAM_CHAT_ID,
            text=chunk,
            parse_mode=parse_mode,
        )


def send_message(text: str) -> None:
    asyncio.run(_send(text))


# ── Approval gate (blocking) ──────────────────────────────────────────────────

def send_approval_request(
    movie_name: str,
    script_en: str,
    script_my: str,
) -> str:
    """
    Sends both scripts to Telegram with Approve / Reject / Regenerate buttons.
    BLOCKS until the user taps a button.
    Returns: "approved" | "rejected" | "regenerate"
    """
    result: list[str] = []  # mutable container for async result

    async def _run() -> None:
        app = Application.builder().token(cfg.TELEGRAM_BOT_TOKEN).build()

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data="approved"),
                InlineKeyboardButton("🔄 Regenerate", callback_data="regenerate"),
            ],
            [InlineKeyboardButton("❌ Reject (stop)", callback_data="rejected")],
        ])

        bot = app.bot
        preview_en = script_en[:800] + ("..." if len(script_en) > 800 else "")
        preview_my = script_my[:400] + ("..." if len(script_my) > 400 else "")

        msg = (
            f"🎬 <b>New Recap Ready for Approval</b>\n"
            f"📁 File: <code>{movie_name}</code>\n\n"
            f"<b>── English Script Preview ──</b>\n{preview_en}\n\n"
            f"<b>── Myanmar Script Preview ──</b>\n{preview_my}\n\n"
            f"Tap a button to continue:"
        )
        await bot.send_message(
            chat_id=cfg.TELEGRAM_CHAT_ID,
            text=msg,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            query = update.callback_query
            await query.answer()
            result.append(query.data)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                f"Got it — <b>{query.data}</b>. Pipeline continuing..." ,
                parse_mode="HTML",
            )
            await app.stop()

        app.add_handler(CallbackQueryHandler(callback))
        async with app:
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            # Wait until callback fires (max 30 minutes)
            for _ in range(30 * 60):
                if result:
                    break
                await asyncio.sleep(1)
            await app.updater.stop()

    asyncio.run(_run())
    decision = result[0] if result else "rejected"
    log.info(f"Telegram approval decision: {decision}")
    return decision


# ── Daily animal summary ──────────────────────────────────────────────────────

async def _send_animal_summary(videos: list[dict]) -> None:
    """
    videos = [{"path": Path, "caption": str, "style": str}, ...]
    """
    bot = Bot(token=cfg.TELEGRAM_BOT_TOKEN)
    header = (
        f"🐾 <b>Daily Animal Content Ready!</b>\n"
        f"Generated <b>{len(videos)}</b> video(s) today.\n"
        f"Copy captions below and post manually.\n"
        f"{'─' * 30}"
    )
    await bot.send_message(
        chat_id=cfg.TELEGRAM_CHAT_ID, text=header, parse_mode="HTML"
    )

    for i, v in enumerate(videos, 1):
        path = Path(v["path"])
        caption_msg = (
            f"<b>Video {i} — {v.get('style','mixed')}</b>\n\n"
            f"📋 <b>Caption to copy:</b>\n"
            f"<code>{v['caption']}</code>"
        )
        await bot.send_message(
            chat_id=cfg.TELEGRAM_CHAT_ID,
            text=caption_msg,
            parse_mode="HTML",
        )
        # Send the actual video file if under 50MB
        if path.exists() and path.stat().st_size < 50 * 1024 * 1024:
            with open(path, "rb") as f:
                await bot.send_video(
                    chat_id=cfg.TELEGRAM_CHAT_ID,
                    video=f,
                    caption=f"Video {i}",
                )


def send_daily_summary(videos: list[dict]) -> None:
    asyncio.run(_send_animal_summary(videos))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split(text: str, max_len: int) -> list[str]:
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks
