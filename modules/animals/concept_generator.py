"""
Animal Module — Step 1.
Gemini generates today's animal video concept + DreamShaper-optimised SD prompt.
Prompts tuned for chubby cartoon animal style (like @cuteandchubbycat TikTok).
Uses google-genai SDK.
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

# Daily style rotation — all tuned for DreamShaper 8 strengths
STYLE_ROTATION = {
    0: "3d cartoon render",
    1: "chibi anime",
    2: "pixar style",
    3: "3d cartoon render",
    4: "chibi anime",
    5: "pixar style",
    6: "3d cartoon render",
}

# Orange/ginger cat heavy rotation — closest to viral TikTok style
ANIMAL_ROTATION = {
    0: "chubby orange cat",
    1: "chubby orange cat",
    2: "fluffy golden retriever puppy",
    3: "chubby orange cat",
    4: "chubby orange cat",
    5: "fluffy corgi puppy",
    6: "chubby orange cat",
}

ACTIONS = [
    "dancing happily",
    "eating a big bowl of food",
    "waving at the camera",
    "sleeping and dreaming",
    "playing with a ball of yarn",
    "jumping excitedly",
    "doing a little spin",
    "sitting and looking cute",
    "stretching and yawning",
    "running playfully",
]

BACKGROUNDS = [
    "cozy living room with warm lighting",
    "magical garden with flowers",
    "kitchen with colourful decorations",
    "beach at sunset",
    "snowy winter scene",
    "rainbow candy land",
    "Japanese cherry blossom park",
    "neon city night",
    "sunny meadow with butterflies",
    "cozy bedroom with fairy lights",
]

_CONCEPT_PROMPT = """You are a creative director for a viral TikTok animal page similar to @cuteandchubbycat.

Today's video concept:
- Animal: {animal}
- Visual style: {style}
- Action: {action}
- Background: {background}

Generate a viral concept. Return ONLY valid JSON, no markdown, no extra text:

{{
  "title": "catchy title max 5 words with emoji",
  "description": "1 sentence describing the cute scene",
  "sd_prompt": "{style}, {animal}, {action}, {background}, chubby cute proportions, big expressive eyes, smooth shading, vibrant saturated colors, thick clean outlines, high quality render, adorable, wholesome, social media viral, masterpiece, best quality",
  "sd_negative": "ugly, deformed, blurry, low quality, realistic photo, human, text, watermark, extra limbs, bad anatomy, dark, scary, violence",
  "caption": "viral TikTok caption — start with a hook emoji, 2 fun lines, 8 trending hashtags including #aicat #cutecat #fyp #viral",
  "style": "{style}",
  "animal": "{animal}"
}}
"""


def generate_concept() -> dict:
    today = date.today()
    style  = STYLE_ROTATION[today.weekday()]
    animal = ANIMAL_ROTATION[today.day % 7]
    action = random.choice(ACTIONS)
    bg     = random.choice(BACKGROUNDS)

    log.info(f"Today's concept: {animal} | {style} | {action}")

    prompt = _CONCEPT_PROMPT.format(
        animal=animal, style=style, action=action, background=bg
    )

    client = _get_client()
    response = client.models.generate_content(
        model=cfg.GEMINI_MODEL,
        contents=prompt,
    )
    raw = response.text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else parts[0]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        concept = json.loads(raw.strip())
    except json.JSONDecodeError:
        log.warning("Gemini returned non-JSON, using fallback concept")
        concept = _fallback_concept(animal, style, action, bg)

    log.info(f"Concept: {concept.get('title', 'N/A')}")
    return concept


def _fallback_concept(animal, style, action, bg):
    return {
        "title": f"🐱 {animal.title()} Moment",
        "description": f"A {style} {animal} {action} in {bg}.",
        "sd_prompt": (
            f"{style}, {animal}, {action}, {bg}, "
            f"chubby cute proportions, big expressive eyes, smooth shading, "
            f"vibrant saturated colors, thick clean outlines, high quality render, "
            f"adorable, wholesome, masterpiece, best quality"
        ),
        "sd_negative": (
            "ugly, deformed, blurry, low quality, realistic photo, human, "
            "text, watermark, extra limbs, bad anatomy, dark, scary"
        ),
        "caption": (
            f"😍 This {animal} just made my day!\n"
            f"So cute I can't handle it 🥹\n"
            f"#aicat #cutecat #fyp #viral #cute #cat #animallover #trending"
        ),
        "style": style,
        "animal": animal,
    }
