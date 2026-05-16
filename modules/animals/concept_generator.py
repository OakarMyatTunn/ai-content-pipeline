"""
Animal Module — Step 1.
Gemini generates today's animal video concept + Stable Diffusion prompt.
Style rotates daily: realistic → cartoon → photorealistic → anime → mixed
Uses google-genai SDK (new, replaces deprecated google-generativeai)
"""
import json
import random
from datetime import date
from google import genai
from modules.shared.config_loader import cfg
from modules.shared.logger import log

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=cfg.GEMINI_API_KEY)
    return _client

STYLE_ROTATION = {
    0: "photorealistic",
    1: "cartoon",
    2: "anime",
    3: "photorealistic",
    4: "cartoon",
    5: "mixed",
    6: "anime",
}

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
    today = date.today()
    style  = STYLE_ROTATION[today.weekday()]
    animal = ANIMAL_ROTATION[today.day % 3]
    dance  = random.choice(DANCE_STYLES)
    bg     = random.choice(BACKGROUNDS)

    log.info(f"Today's concept: {animal} | {style} | {dance} | {bg}")

    prompt = _CONCEPT_PROMPT.format(
        animal=animal, style=style, dance=dance, background=bg
    )

    client = _get_client()
    response = client.models.generate_content(
        model=cfg.GEMINI_MODEL,
        contents=prompt,
    )
    raw = response.text.strip()

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


def _fallback_concept(animal, style, dance, bg):
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
