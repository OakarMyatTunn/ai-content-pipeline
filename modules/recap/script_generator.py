"""
Step 2 of recap pipeline.
Sends SRT transcript to Gemini.
Generates two scripts: English and Myanmar (Burmese).
Uses google-genai SDK (replaces deprecated google-generativeai)
"""
from google import genai
from modules.shared.config_loader import cfg
from modules.shared.logger import log

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=cfg.GEMINI_API_KEY)
    return _client

_EN_PROMPT = """You are a viral social media video scriptwriter specialising in movie recaps.

Given the following movie transcript (SRT format), write a compelling recap script for a 
short-form vertical video (TikTok / YouTube Shorts / Facebook Reels).

RULES:
- Hook in the FIRST sentence — make it impossible to scroll past
- Total script: 250-350 words (fits a 2-3 minute voiceover)
- 3-act structure: setup, conflict, resolution/cliffhanger
- Conversational tone — like a friend telling a story at lunch
- End with a curiosity hook
- DO NOT include stage directions, timestamps, or formatting tags
- Output ONLY the script text, nothing else

TRANSCRIPT:
{srt}
"""

_MY_PROMPT = """သင်သည် မြန်မာဘာသာဖြင့် ဗီဒီယိုရှင်းလင်းချက် ရေးသားသူဖြစ်သည်။

အောက်ပါ ရုပ်ရှင် transcript (SRT ပုံစံ) ကို အသုံးပြု၍ TikTok / YouTube Shorts / Facebook Reels 
အတွက် ဗီဒီယိုများကို ဆွဲဆောင်မှုရှိသော မြန်မာဘာသာ recap script တစ်ခု ရေးပါ။

စည်းမျဉ်းများ:
- ပထမဆုံးဝါကျတွင် ဖိတ်ခေါ်မှုရှိပါစေ
- Script စုစုပေါင်း: မြန်မာဘာသာ ၂၀၀-၃၀၀ ကြားပါဝင်ရမည်
- သုံးပိုင်းဖွဲ့စည်းမှု: မိတ်ဆက်, ဇာတ်ကွက်, အဖြေ
- Script ကိုသာ ထုတ်ပေးပါ

TRANSCRIPT:
{srt}
"""


def generate_scripts(srt: str, movie_name: str = "") -> dict:
    srt_trimmed = srt[:80_000] if len(srt) > 80_000 else srt
    client = _get_client()

    log.info("Generating English recap script via Gemini...")
    en_response = client.models.generate_content(
        model=cfg.GEMINI_MODEL,
        contents=_EN_PROMPT.format(srt=srt_trimmed),
    )
    script_en = en_response.text.strip()
    log.info(f"English script: {len(script_en.split())} words")

    log.info("Generating Myanmar recap script via Gemini...")
    my_response = client.models.generate_content(
        model=cfg.GEMINI_MODEL,
        contents=_MY_PROMPT.format(srt=srt_trimmed),
    )
    script_my = my_response.text.strip()
    log.info(f"Myanmar script: {len(script_my)} characters")

    return {"english": script_en, "myanmar": script_my}
