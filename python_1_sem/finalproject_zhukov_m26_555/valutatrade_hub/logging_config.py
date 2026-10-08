import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import RLock

from valutatrade_hub.infra.settings import SettingsLoader

_LOCK = RLock()


class ActionFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat(),
            "level": record.levelname,
            **record.action_context,
        }
        return json.dumps(payload, ensure_ascii=False, allow_nan=False)


def configure_logging() -> logging.Logger:
    """JSON Lines, INFO по умолчанию; 1 MiB на файл и 3 архивных файла."""
    settings = SettingsLoader()
    path = Path(settings.get("LOG_DIR")) / settings.get("LOG_FILE")
    signature = (
        str(path),
        settings.get("LOG_MAX_BYTES"),
        settings.get("LOG_BACKUP_COUNT"),
    )
    with _LOCK:
        logger = logging.getLogger("valutatrade.actions")
        logger.setLevel(settings.get("LOG_LEVEL"))
        logger.propagate = False
        if getattr(logger, "_config_signature", None) != signature:
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                path,
                maxBytes=signature[1],
                backupCount=signature[2],
                encoding="utf-8",
            )
            handler.setFormatter(ActionFormatter())
            for old_handler in logger.handlers[:]:
                logger.removeHandler(old_handler)
                old_handler.close()
            logger.addHandler(handler)
            logger._config_signature = signature
        return logger


def configure_parser_logging() -> logging.Logger:
    settings = SettingsLoader()
    path = Path(settings.get("LOG_DIR")) / "parser.log"
    with _LOCK:
        logger = logging.getLogger("valutatrade.parser")
        logger.setLevel(settings.get("LOG_LEVEL"))
        logger.propagate = False
        if getattr(logger, "_parser_path", None) != str(path):
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                path,
                maxBytes=settings.get("LOG_MAX_BYTES"),
                backupCount=settings.get("LOG_BACKUP_COUNT"),
                encoding="utf-8",
            )
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            import time

            formatter.converter = time.gmtime
            handler.setFormatter(formatter)
            for old in logger.handlers[:]:
                logger.removeHandler(old)
                old.close()
            logger.addHandler(handler)
            logger._parser_path = str(path)
        return logger
