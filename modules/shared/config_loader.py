"""
Shared config loader — reads .env from project root.
Import this in every module: from modules.shared.config_loader import cfg
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (works regardless of where script is run from)
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)


class Config:
    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Paths (resolved to absolute)
    _base = Path(__file__).resolve().parents[2]
    INPUT_FOLDER: Path       = _base / os.getenv("INPUT_FOLDER", "input")
    OUTPUT_RECAP: Path       = _base / os.getenv("OUTPUT_RECAP_FOLDER", "outputs/recap")
    OUTPUT_ANIMALS: Path     = _base / os.getenv("OUTPUT_ANIMALS_FOLDER", "outputs/animals")
    MODELS_FOLDER: Path      = _base / os.getenv("MODELS_FOLDER", "models")
    MUSIC_FOLDER: Path       = _base / os.getenv("MUSIC_FOLDER", "music")
    LOGS_FOLDER: Path        = _base / os.getenv("LOGS_FOLDER", "logs")

    # Whisper
    WHISPER_MODEL: str        = os.getenv("WHISPER_MODEL", "medium")
    WHISPER_DEVICE: str       = os.getenv("WHISPER_DEVICE", "cuda")
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

    # Stable Diffusion
    SD_MODEL: str             = os.getenv("SD_MODEL", "runwayml/stable-diffusion-v1-5")
    SD_DEVICE: str            = os.getenv("SD_DEVICE", "cuda")
    SD_STEPS: int             = int(os.getenv("SD_INFERENCE_STEPS", 30))
    SD_GUIDANCE: float        = float(os.getenv("SD_GUIDANCE_SCALE", 7.5))
    SD_WIDTH: int             = int(os.getenv("SD_IMAGE_WIDTH", 576))
    SD_HEIGHT: int            = int(os.getenv("SD_IMAGE_HEIGHT", 1024))
    SD_FRAMES: int            = int(os.getenv("SD_FRAMES_PER_VIDEO", 10))
    SD_LOW_VRAM: bool         = os.getenv("SD_LOW_VRAM_MODE", "false").lower() == "true"

    # Schedule
    ANIMAL_HOUR: int          = int(os.getenv("ANIMAL_CRON_HOUR", 10))
    ANIMAL_MINUTE: int        = int(os.getenv("ANIMAL_CRON_MINUTE", 15))
    ANIMAL_TZ: str            = os.getenv("ANIMAL_CRON_TIMEZONE", "Asia/Kuala_Lumpur")

    # Video
    VIDEO_WIDTH: int          = int(os.getenv("VIDEO_WIDTH", 1080))
    VIDEO_HEIGHT: int         = int(os.getenv("VIDEO_HEIGHT", 1920))
    VIDEO_FPS: int            = int(os.getenv("VIDEO_FPS", 30))
    VIDEO_BITRATE: str        = os.getenv("VIDEO_BITRATE", "4000k")
    ANIMAL_DURATION: int      = int(os.getenv("ANIMAL_VIDEO_DURATION", 20))

    # Gemini
    GEMINI_MODEL: str         = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # TTS
    EN_TTS_VOICE: str         = os.getenv("EN_TTS_VOICE", "en-US-JennyNeural")
    MY_TTS_LANG: str          = os.getenv("MY_TTS_LANG", "my")

    def validate(self):
        """Call on startup to catch missing secrets early."""
        missing = []
        if not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not self.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.TELEGRAM_CHAT_ID:
            missing.append("TELEGRAM_CHAT_ID")
        if missing:
            raise EnvironmentError(
                f"Missing required .env values: {', '.join(missing)}\n"
                f"Copy config/config.env.template to .env and fill in your values."
            )
        return True


cfg = Config()
