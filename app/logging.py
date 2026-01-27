# app/logging.py
"""Structured logging configuration for the License Intelligence System."""

import logging
import sys
from typing import Any

import structlog


def configure_logging(*, debug: bool = False) -> None:
    """Configure structured logging for the application.

    Args:
        debug: If True, set log level to DEBUG. Otherwise INFO.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured logger.

    Args:
        name: Logger name. If None, uses the caller's module name.

    Returns:
        Configured structlog logger.
    """
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger


class LogContext:
    """Context manager for adding temporary context to log messages."""

    def __init__(self, logger: structlog.stdlib.BoundLogger, **context: Any) -> None:
        """Initialize log context.

        Args:
            logger: The logger to bind context to.
            **context: Key-value pairs to add to log context.
        """
        self.logger = logger
        self.context = context
        self._token: Any = None

    def __enter__(self) -> structlog.stdlib.BoundLogger:
        """Enter context and return bound logger."""
        return self.logger.bind(**self.context)

    def __exit__(self, *args: Any) -> None:
        """Exit context."""
        pass
