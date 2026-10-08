import json
from pathlib import Path
from threading import RLock
from typing import Any, ClassVar

from valutatrade_hub.core.currencies import get_currency

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SettingsLoader:
    """Одна кешированная конфигурация на процесс, без экземпляра при импорте."""

    _instance: ClassVar["SettingsLoader | None"] = None
    _lock: ClassVar[RLock] = RLock()

    def __new__(cls):
        # __new__ проще метакласса: Singleton нужен только этому классу.
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._path = PROJECT_ROOT / "config.json"
                instance.reload()
                cls._instance = instance
            return cls._instance

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._settings.get(key, default)

    def reload(self, path: str | Path | None = None) -> None:
        """Явно перечитать config.json; при ошибке сохранить прежние настройки."""
        with self._lock:
            config_path = Path(path).resolve() if path is not None else self._path
            settings = {
                "DATA_DIR": "data",
                "USERS_FILE": "users.json",
                "PORTFOLIOS_FILE": "portfolios.json",
                "RATES_FILE": "rates.json",
                "RATES_TTL_SECONDS": 300,
                "DEFAULT_BASE_CURRENCY": "USD",
                "LOG_DIR": "logs",
                "LOG_FILE": "actions.log",
                "LOG_FORMAT": "json",
                "LOG_LEVEL": "INFO",
                "LOG_MAX_BYTES": 1_048_576,
                "LOG_BACKUP_COUNT": 3,
            }
            try:
                raw = config_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                if path is not None:
                    raise
            else:
                overrides = json.loads(raw)
                if not isinstance(overrides, dict):
                    raise TypeError("Конфигурация должна быть JSON-объектом")
                settings.update(overrides)
            for key in ("RATES_TTL_SECONDS", "LOG_MAX_BYTES", "LOG_BACKUP_COUNT"):
                if type(settings[key]) is not int or settings[key] <= 0:
                    raise ValueError(f"{key} должен быть положительным целым числом")
            for key in ("DATA_DIR", "LOG_DIR"):
                value = settings[key]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{key} должен быть непустым путём")
                settings[key] = str((config_path.parent / value).resolve())
            for key in ("USERS_FILE", "PORTFOLIOS_FILE", "RATES_FILE", "LOG_FILE"):
                value = settings[key]
                if not isinstance(value, str) or not value or Path(value).name != value:
                    raise ValueError(f"{key} должен быть именем файла без каталога")
            if (
                len(
                    {
                        settings[key]
                        for key in ("USERS_FILE", "PORTFOLIOS_FILE", "RATES_FILE")
                    }
                )
                != 3
            ):
                raise ValueError("Имена JSON-файлов должны различаться")
            if settings["LOG_FORMAT"] != "json":
                raise ValueError("Поддерживается только LOG_FORMAT=json")
            if settings["LOG_LEVEL"] not in (
                "DEBUG",
                "INFO",
                "WARNING",
                "ERROR",
                "CRITICAL",
            ):
                raise ValueError("Неизвестный LOG_LEVEL")
            base = settings["DEFAULT_BASE_CURRENCY"]
            if not isinstance(base, str) or not base.strip():
                raise ValueError("DEFAULT_BASE_CURRENCY должен быть кодом валюты")
            settings["DEFAULT_BASE_CURRENCY"] = get_currency(base).code
            self._settings = settings
            self._path = config_path
