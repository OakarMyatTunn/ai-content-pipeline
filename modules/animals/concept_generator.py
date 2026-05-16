"""
Animal Module — Step 1.
Generates educational animal fact content:
- 5 interesting facts about the animal (narration script)
- Stable Diffusion prompt for each fact's illustration
- TikTok/YouTube caption with hashtags
Fixed animal anatomy by using precise SD prompts.
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

# Animals that generate well in DreamShaper — specific enough to avoid anatomy errors
ANIMALS = [
    ("orange tabby cat",     "cat"),
    ("golden retriever dog", "dog"),
    ("red fox",              "fox"),
    ("barn owl",             "owl"),
    ("giant panda",          "panda"),
    ("bottlenose dolphin",   "dolphin"),
    ("snow leopard",         "leopard"),
    ("capybara",             "capybara"),
    ("arctic fox",           "fox"),
    ("emperor penguin",      "penguin"),
    ("red panda",            "red panda"),
    ("meerkat",              "meerkat"),
]

# Rotate animals by day of month
def _get_today_animal():
    return ANIMALS[date.today().day % len(ANIMALS)]

_PROMPT = """You are a creator of viral educational animal facts videos for TikTok and YouTube Shorts.

Today's animal: {animal_name}

Create content for a 60-second educational narration video. Return ONLY valid JSON:

{{
  "animal": "{animal_name}",
  "hook": "One attention-grabbing opening sentence (max 15 words) starting with a surprising fact",
  "facts": [
    "Fact 1 — surprising and specific (max 20 words)",
    "Fact 2 — behaviour or ability fact (max 20 words)",
    "Fact 3 — size, speed, or record fact (max 20 words)",
    "Fact 4 — social or family life fact (max 20 words)",
    "Fact 5 — conservation or unique trait fact (max 20 words)"
  ],
  "closing": "Engaging closing sentence asking viewers to follow for more (max 15 words)",
  "sd_prompt": "chibi cartoon illustration, cute {animal_name}, sitting and looking at camera, big expressive eyes, soft rounded body, four legs clearly visible, symmetrical, clean white background, vibrant colors, smooth cell shading, thick outlines, kawaii style, masterpiece, best quality, high detail",
  "sd_negative": "six legs, extra limbs, deformed, ugly, blurry, realistic photo, human, text, watermark, bad anatomy, mutation, extra fingers, fused limbs, missing limbs, asymmetrical",
  "title": "5 Amazing Facts About {animal_name}s That Will Blow Your Mind 🤯",
  "caption": "Did you know this about {animal_name}s? 🐾\\nFollow for daily animal facts! 🌿\\n#animalfacts #{tag} #didyouknow #learnontiktok #animals #wildlife #fyp #viral"
}}
"""


def generate_concept() -> dict:
    animal_name, tag = _get_today_animal()
    log.info(f"Today's animal: {animal_name}")

    prompt = _PROMPT.format(animal_name=animal_name, tag=tag)
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
        log.warning("Gemini returned non-JSON — using fallback")
        concept = _fallback(animal_name, tag)

    # Build full narration script from parts
    facts = concept.get("facts", [])
    concept["narration"] = (
        concept.get("hook", "") + " " +
        " ".join(facts) + " " +
        concept.get("closing", "")
    ).strip()

    log.info(f"Animal: {animal_name} | Facts: {len(facts)}")
    return concept


def _fallback(animal_name, tag):
    return {
        "animal": animal_name,
        "hook": f"You won't believe what {animal_name}s can do!",
        "facts": [
            f"{animal_name}s are fascinating creatures found around the world.",
            f"They have unique adaptations that help them survive in the wild.",
            f"Their diet consists of carefully selected foods for their needs.",
            f"They live in social groups and communicate in complex ways.",
            f"Conservation efforts are helping protect their populations.",
        ],
        "closing": "Follow for more amazing animal facts every day!",
        "sd_prompt": (
            f"chibi cartoon illustration, cute {animal_name}, sitting and looking at camera, "
            f"big expressive eyes, soft rounded body, four legs clearly visible, symmetrical, "
            f"clean white background, vibrant colors, smooth cell shading, thick outlines, "
            f"kawaii style, masterpiece, best quality"
        ),
        "sd_negative": (
            "six legs, extra limbs, deformed, ugly, blurry, realistic photo, human, "
            "text, watermark, bad anatomy, mutation, fused limbs, missing limbs"
        ),
        "title": f"5 Amazing Facts About {animal_name}s!",
        "caption": (
            f"Did you know this about {animal_name}s? 🐾\n"
            f"Follow for daily animal facts! 🌿\n"
            f"#animalfacts #{tag} #didyouknow #learnontiktok #animals #wildlife #fyp #viral"
        ),
        "narration": (
            f"You won't believe what {animal_name}s can do! "
            f"{animal_name}s are fascinating creatures found around the world. "
            "They have unique adaptations that help them survive in the wild. "
            "Their diet consists of carefully selected foods for their needs. "
            "They live in social groups and communicate in complex ways. "
            "Conservation efforts are helping protect their populations. "
            "Follow for more amazing animal facts every day!"
        ),
    }
