"""
Animal Module — Step 1.
Gemini generates today's animal video concept + Stable Diffusion prompt.
Style rotates daily: realistic → cartoon → photorealistic → anime → mixed
"""
import json
import random
from datetime import date
import google.generativeai as genai
from modules.shared.config_loader import cfg
from modules.shared.logger import log

genai.configure(api_key=cfg.GEMINI_API_KEY)
_model = genai.GenerativeModel(cfg.GEMINI_MODEL)

# Daily style rotation (keyed by day-of-week 0=Mon)
STYLE_ROTATION = {
    0: "photorealistic",   # Monday
    1: "cartoon",          # Tuesday
    2: "anime",            # Wednesday
    3: "photorealistic",   # Thursday
    4: "cartoon",          # Friday
    5: "mixed",            # Saturday
    6: "anime",            # Sunday
}

# Animal rotation (keyed by day-of-month % 3)
ANIMAL_ROTATION = {0: "cat", 1: "dog", 2: "mixed"}

DANCE_STYLES = [
    "breakdancing", "ballet", "hiphop", "salsa", "moonwalk",
    "twerking gracefully", "floss dance", "robot dance",
    "traditional Malaysian dance", "disco",
]

BACKGROUNDS = [
    "neon city at night", "tropical beach", "cozy living room",
    "enchanted forest", "outer space", "Japanese cherry blossom garden",
    "Malaysian street market", "colourful confetti rain", "retro diner",
]

_CONCEPT_PROMPT = """You are a creative director for a viral social media animal content page.

Today's parameters:
- Animal: {animal}
- Visual style: {style}
- Dance/action: {dance}
- Background: {background}

Generate a viral animal video concept. Return ONLY valid JSON, no markdown, no explanation:

{{
  "title": "short punchy title (max 6 words)",
  "description": "2-sentence description of the video scene",
  "sd_prompt": "detailed Stable Diffusion image generation prompt, optimized for {style} style, featuring a {animal} {dance} in {background}, cute, high quality, social media viral",
  "sd_negative": "blurry, low quality, ugly, deformed, extra limbs, watermark, text",
  "caption": "viral TikTok/Reels caption with emojis — hook line, 2-line description, 6 hashtags",
  "style": "{style}",
  "animal": "{animal}"
}}
"""


def generate_concept() -> dict:
    """
    Generate today's animal content concept.
    Returns a dict with all fields needed for image generation + assembly.
    """
    today = date.today()
    style  = STYLE_ROTATION[today.weekday()]
    animal = ANIMAL_ROTATION[today.day % 3]
    dance  = random.choice(DANCE_STYLES)
    bg     = random.choice(BACKGROUNDS)

    log.info(f"Today's concept: {animal} | {style} | {dance} | {bg}")

    prompt = _CONCEPT_PROMPT.format(
        animal=animal, style=style, dance=dance, background=bg
    )

    response = _model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        concept = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Gemini returned non-JSON, using fallback concept")
        concept = _fallback_concept(animal, style, dance, bg)

    log.info(f"Concept: {concept.get('title', 'N/A')}")
    return concept


def _fallback_concept(animal: str, style: str, dance: str, bg: str) -> dict:
    return {
        "title": f"Cute {animal} {dance}",
        "description": f"A {style} {animal} doing the {dance} in {bg}.",
        "sd_prompt": (
            f"{style} style {animal} {dance}, {bg}, "
            f"cute, fluffy, expressive eyes, high quality, viral social media"
        ),
        "sd_negative": "blurry, low quality, ugly, deformed, watermark",
        "caption": (
            f"This {animal} just broke the internet 😂🔥\n"
            f"Watch till the end!\n"
            f"#{animal} #cute{animal.capitalize()} #viral #fyp #foryou #trending"
        ),
        "style": style,
        "animal": animal,
    }
