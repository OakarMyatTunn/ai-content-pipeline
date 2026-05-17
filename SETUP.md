# AI Content Pipeline — Setup Guide
**Windows 11 · RTX 3050 4GB · 24GB RAM**

Follow these steps in order. Takes about 30–45 minutes total.

---

## Step 1 — Install Python 3.11

1. Go to https://www.python.org/downloads/release/python-3119/
2. Download **Windows installer (64-bit)**
3. Run installer — **TICK "Add Python to PATH"** before clicking Install
4. Open Command Prompt and verify:
   ```
   python --version
   ```
   Should show `Python 3.11.x`

---

## Step 2 — Install Git

1. Download from https://git-scm.com/download/win
2. Install with default settings
3. Verify: `git --version`

---

## Step 3 — Install ffmpeg

1. Download from https://github.com/BtbN/FFmpeg-Builds/releases
   - Pick: `ffmpeg-master-latest-win64-gpl.zip`
2. Extract to `C:\ffmpeg`
3. Add to PATH:
   - Search "Environment Variables" in Start Menu
   - Edit System Environment Variables → Environment Variables
   - Under System Variables → Path → Edit → New → add `C:\ffmpeg\bin`
4. Verify: open NEW Command Prompt → `ffmpeg -version`

---

## Step 4 — Install CUDA Toolkit (for GPU acceleration)

1. Go to https://developer.nvidia.com/cuda-downloads
2. Select: Windows → x86_64 → 11 → exe (local)
3. Download and install CUDA 12.x
4. Verify: `nvcc --version`

---

## Step 5 — Clone the Repo

```cmd
cd C:\
git clone https://github.com/YOUR_USERNAME/ai-content-pipeline.git
cd ai-content-pipeline
```

---

## Step 6 — Create Virtual Environment

```cmd
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` in your prompt. **Always activate before running scripts.**

---

## Step 7 — Install PyTorch with CUDA

This must be done BEFORE installing the other requirements.

```cmd
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121
```

Verify GPU is detected:
```cmd
python -c "import torch; print(torch.cuda.is_available())"
```
Should print `True`. If it prints `False`, check your CUDA installation.

---

## Step 8 — Install All Dependencies

```cmd
pip install -r requirements.txt
```

## Step 8b — Install Kokoro TTS (human-like voice)

```cmd
pip install kokoro soundfile
```

Then install the espeak backend (required by Kokoro on Windows):
1. Download: https://github.com/espeak-ng/espeak-ng/releases
2. Install `espeak-ng-X.X.X-x64.msi`
3. Restart your terminal

Verify Kokoro works:
```cmd
python -c "from kokoro import KPipeline; p = KPipeline(lang_code='a'); print('Kokoro OK')"
```

If Kokoro fails, the pipeline automatically falls back to gTTS — so it will still work.

This takes 5–10 minutes. Ignore any yellow warnings.

---

## Step 9 — Configure .env

```cmd
copy config\config.env.template .env
notepad .env
```

Fill in these three values (minimum required):

```
GEMINI_API_KEY=    ← from https://aistudio.google.com/app/apikey
TELEGRAM_BOT_TOKEN=  ← from @BotFather on Telegram
TELEGRAM_CHAT_ID=    ← see instructions below
```

### Getting your Telegram Chat ID:
1. Message @BotFather → /newbot → follow prompts → copy token
2. Start a chat with your new bot (search its name, click Start)
3. Visit this URL in browser (replace YOUR_TOKEN):
   `https://api.telegram.org/botYOUR_TOKEN/getUpdates`
4. Send any message to your bot, refresh the URL
5. Find `"chat":{"id":XXXXXXXXX}` — that number is your CHAT_ID

---

## Step 10 — Download the SD Model

The Stable Diffusion 1.5 model (~4GB) downloads automatically on first run.
To pre-download manually:

```cmd
python -c "
from diffusers import StableDiffusionPipeline
import torch
pipe = StableDiffusionPipeline.from_pretrained('runwayml/stable-diffusion-v1-5', torch_dtype=torch.float16)
print('Model downloaded successfully!')
"
```

This will download to your HuggingFace cache (~4GB). Takes 5–15 minutes.

---

## Step 11 — Download Music Tracks

```cmd
python scripts/download_music.py
```

Or manually add any .mp3 files to the `/music/` folder.

---

## Step 12 — Test Telegram Bot

```cmd
python scripts/test_telegram.py
```

You should receive a message on Telegram. If not, check your .env values.

---

## Step 13 — Test Animal Pipeline

```cmd
python scripts/test_animal_pipeline.py
```

This generates one animal video. Check `/outputs/animals/` when done (~5–10 min).

---

## Step 14 — Run the Full Pipeline

```cmd
python main.py
```

You'll see coloured console output. The pipeline is now running:
- Drop any video file into `/input/` → recap pipeline starts automatically
- Animal pipeline fires daily at 10:15 AM Malaysia time

---

## Step 15 — Run as Windows Startup Task (Optional but Recommended)

So the pipeline starts automatically when you boot your PC:

### Option A: Windows Task Scheduler (simple)
1. Search "Task Scheduler" in Start Menu
2. Create Basic Task → Name: "AI Content Pipeline"
3. Trigger: **When I log on**
4. Action: Start a Program
   - Program: `C:\ai-content-pipeline\venv\Scripts\python.exe`
   - Arguments: `main.py`
   - Start in: `C:\ai-content-pipeline`
5. Finish → right-click → Run (to test)

### Option B: NSSM Windows Service (more robust)
1. Download NSSM from https://nssm.cc/download
2. Extract `nssm.exe` to `C:\Windows\System32`
3. Open Command Prompt as Administrator:
   ```cmd
   nssm install AIPipeline
   ```
4. In the GUI:
   - Path: `C:\ai-content-pipeline\venv\Scripts\python.exe`
   - Startup directory: `C:\ai-content-pipeline`
   - Arguments: `main.py`
5. Click Install Service
6. Start it: `nssm start AIPipeline`

---

## Folder Structure

```
ai-content-pipeline/
├── main.py                    ← START HERE
├── requirements.txt
├── .env                       ← YOUR SECRETS (never commit)
├── config/
│   └── config.env.template    ← Copy this to .env
├── modules/
│   ├── recap/                 ← Movie recap pipeline
│   ├── animals/               ← Daily animal content pipeline
│   └── shared/                ← Config, logging, Telegram
├── scripts/                   ← Test and utility scripts
├── input/                     ← DROP VIDEOS HERE
├── outputs/
│   ├── recap/                 ← Recap videos output here
│   └── animals/               ← Animal videos output here
├── models/                    ← SD models (auto-downloaded)
├── music/                     ← Add .mp3 files here
└── logs/                      ← Pipeline logs
```

---

## Common Issues

| Problem | Fix |
|---|---|
| `torch.cuda.is_available()` returns False | Reinstall CUDA toolkit, then reinstall PyTorch with CUDA wheel |
| Whisper out of memory | Change `WHISPER_MODEL=small` in .env |
| SD out of memory | Set `SD_LOW_VRAM_MODE=true` in .env |
| Telegram bot not responding | Check BOT_TOKEN and CHAT_ID, make sure you messaged the bot first |
| ffmpeg not found | Make sure `C:\ffmpeg\bin` is in system PATH, use NEW cmd window |
| `ModuleNotFoundError` | Make sure venv is activated: `venv\Scripts\activate` |

---

## Updating the Pipeline

```cmd
cd C:\ai-content-pipeline
git pull
venv\Scripts\activate
pip install -r requirements.txt
```
