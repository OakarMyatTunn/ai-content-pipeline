# 🎬🐾 AI Content Pipeline

Automated content creation system running locally on Windows.

## Two Modules

| Module | Trigger | Output |
|---|---|---|
| 🎬 **Movie Recap** | Drop video into `/input/` | 6 videos (EN + Myanmar × 3 platforms) |
| 🐾 **Animal Content** | Daily at 10:15 AM auto | 2–3 viral animal videos |

## Stack (all free)
- **Transcription**: Faster-Whisper (GPU, RTX 3050)
- **Scripts / Concepts**: Gemini 1.5 Flash (free API)
- **Image Generation**: Stable Diffusion 1.5 (local GPU)
- **Voiceover**: Edge TTS (English) + gTTS (Myanmar)
- **Video Assembly**: ffmpeg
- **Notifications**: Telegram Bot
- **Scheduler**: APScheduler (Python)

## Quick Start

```cmd
git clone https://github.com/YOUR_USERNAME/ai-content-pipeline.git
cd ai-content-pipeline
python -m venv venv && venv\Scripts\activate
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
copy config\config.env.template .env
# Edit .env with your API keys
python main.py
```

See **[SETUP.md](SETUP.md)** for the complete step-by-step guide.
