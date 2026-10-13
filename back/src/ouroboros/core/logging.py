import logging
import sys

from loguru import logger

from ouroboros.core.settings import get_settings


class _InterceptHandler(logging.Handler):
    """Redireciona logging stdlib (uvicorn, sqlalchemy, httpx) para o loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    level = get_settings().log_level.upper()
    logger.remove()
    logger.add(sys.stderr, level=level)
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = [_InterceptHandler()]
    logging.getLogger("httpx").setLevel(logging.WARNING)
