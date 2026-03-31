"""Structured logging with structlog.

Supports two modes:
- 'rich': Colorful terminal output for CLI
- 'json': Structured JSON for backend services

Integrates structlog with Python's standard logging for consistent
JSON output across application and third-party libraries.
"""
import logging
import sys
from typing import Literal

import structlog
from rich.console import Console

console = Console()


def set_logger_mode(mode: Literal["rich", "json"]) -> None:
    """
    Set the logger mode to 'rich' or 'json'.

    Integrates structlog with Python's standard logging so that
    third-party libraries also output consistent JSON logs.

    Args:
        mode: 'rich' for terminal output, 'json' for structured logging
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if mode == "rich":
        # Configure structlog for rich console output
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        # Standard logging uses console output
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=logging.INFO,
        )
    else:  # json
        # Configure structlog for JSON output (direct to stdout)
        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ExtraAdder(),
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),  # Direct output, not via stdlib
            cache_logger_on_first_use=True,
        )

        # Configure standard library logging to also output JSON
        # This ensures third-party libraries (httpx, asyncpg, etc.) output JSON
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=shared_processors,
                processor=structlog.processors.JSONRenderer(),
            )
        )

        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

        # Reduce noise from third-party libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str = "valiref"):
    """Get a structlog logger instance."""
    return structlog.get_logger(name)


# Default: setup rich mode
set_logger_mode("rich")

# Backwards compatibility
logger = get_logger()
