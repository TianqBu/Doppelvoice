"""loguru 配置。"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <7}</level> | "
               "<cyan>{name}:{line}</cyan> | <level>{message}</level>",
        enqueue=False,
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "doppelvoice_{time:YYYYMMDD}.log",
        level="DEBUG",
        rotation="50 MB",
        retention="7 days",
        encoding="utf-8",
        enqueue=True,
    )
