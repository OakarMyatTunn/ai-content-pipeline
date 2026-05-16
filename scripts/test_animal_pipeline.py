"""
Manually trigger one animal video generation (for testing).
Run: python scripts/test_animal_pipeline.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from modules.shared.config_loader import cfg
from modules.shared.logger import log
from modules.animals.pipeline import run

if __name__ == "__main__":
    log.info("Running animal pipeline test (1 video, force=True)...")
    run(force=True)
    log.info("Done! Check outputs/animals/ folder.")
