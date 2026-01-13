"""Structured logging configuration shared across services."""

from __future__ import annotations

import logging
import os

import structlog


def configure_logging(
    log_level: str | int | None = None,
) -> structlog.stdlib.BoundLogger:
    """Configure structlog JSON logging and return a bound logger."""
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(level=log_level)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )
    return structlog.get_logger()
