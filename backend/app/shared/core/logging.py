import logging
from logging.config import dictConfig


def configure_logging() -> None:
    """
    Configure application-wide logging once during startup.
    Safe to call repeatedly; second invocation becomes a no-op.
    """
    if logging.getLogger().handlers:
        return

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {"handlers": ["console"], "level": "INFO"},
        }
    )
