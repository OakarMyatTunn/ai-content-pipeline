"""
Quick test — sends a test message to your Telegram bot.
Run AFTER filling in .env:
    python scripts/test_telegram.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from modules.shared.config_loader import cfg
from modules.shared.telegram_bot import send_message

if __name__ == "__main__":
    try:
        cfg.validate()
        send_message(
            "✅ <b>Pipeline test successful!</b>\n"
            "Your Telegram bot is connected and working.\n"
            "Drop a video into <code>/input/</code> to start a recap."
        )
        print("✓ Message sent! Check your Telegram.")
    except Exception as e:
        print(f"✗ Error: {e}")
