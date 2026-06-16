"""Centralized logging configuration.

Logs go to the console and to ``logs/safetynet.log`` (rotating). The audit *trail* is a
separate, structured JSONL stream (see :mod:`safetynet.core.audit`); this module is for
human-readable operational logging only.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

DEFAULT_LOG_DIR = Path("logs")
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_configured = False


def configure_logging(
    level: int | str = logging.INFO,
    log_dir: Path | str = DEFAULT_LOG_DIR,
    *,
    to_file: bool = True,
) -> logging.Logger:
    """Configure the ``safetynet`` logger tree. Idempotent."""
    global _configured
    root = logging.getLogger("safetynet")
    if _configured:
        root.setLevel(level)
        return root

    root.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path / "safetynet.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.propagate = False
    _configured = True
    return root
