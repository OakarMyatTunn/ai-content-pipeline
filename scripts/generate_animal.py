"""
Generate an educational animal facts video for a specific animal.

Usage:
    python scripts/generate_animal.py "snow leopard"
    python scripts/generate_animal.py "axolotl"
    python scripts/generate_animal.py "mantis shrimp"

If no animal is given, it will prompt you to type one.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from modules.shared.logger import log
from modules.animals.pipeline import run_for_animal

if __name__ == "__main__":
    if len(sys.argv) > 1:
        animal = " ".join(sys.argv[1:]).strip()
    else:
        animal = input("Enter animal name: ").strip()

    if not animal:
        print("No animal provided. Exiting.")
        sys.exit(1)

    log.info(f"Generating educational video for: {animal}")
    run_for_animal(animal)
    log.info("Done! Check outputs/animals/ folder and your Telegram.")
