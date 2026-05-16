"""
Shared logger. Rich console output + rotating file log.
Usage: from modules.shared.logger import log
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from rich.logging import RichHandler
from rich.console import Console

console = Console()

def get_logger(name: str = "pipeline") -> logging.Logger:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    logs_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    # Rich console handler (pretty, coloured)
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        markup=True,
        show_time=True,
    )
    rich_handler.setLevel(logging.INFO)

    # File handler (full debug, rotating 10MB × 5 files)
    file_handler = RotatingFileHandler(
        logs_dir / f"{name}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    logger.addHandler(rich_handler)
    logger.addHandler(file_handler)
    return logger


log = get_logger("pipeline")
