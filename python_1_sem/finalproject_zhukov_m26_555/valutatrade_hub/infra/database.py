import json
import os
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import ClassVar

from valutatrade_hub.core.exceptions import StorageError
from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Единый менеджер JSON и блокировка операций внутри процесса."""

    _instance: ClassVar["DatabaseManager | None"] = None
    _lock: ClassVar[RLock] = RLock()

    def __new__(cls):

        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def _path(self, name: str, data_dir: str | Path | None) -> Path:
        if name not in ("users", "portfolios", "rates"):
            raise StorageError(f"Неизвестное хранилище '{name}'")
        settings = SettingsLoader()
        directory = (
            Path(data_dir) if data_dir is not None else Path(settings.get("DATA_DIR"))
        )
        return directory / settings.get(f"{name.upper()}_FILE")

    def read(self, name: str, data_dir: str | Path | None = None) -> list | dict:
        with self._lock:
            path = self._path(name, data_dir)
            expected_type = dict if name == "rates" else list
            try:
                text = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                return expected_type()
            except OSError as exc:
                raise StorageError(f"Не удалось прочитать {path.name}: {exc}") from exc
            if not text.strip():
                return expected_type()
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise StorageError(f"Повреждён файл {path.name}: {exc.msg}") from exc
            if not isinstance(data, expected_type):
                raise StorageError(f"Неверный формат файла {path.name}")
            return data

    def write(
        self, name: str, data: list | dict, data_dir: str | Path | None = None
    ) -> None:
        with self._lock:
            path = self._path(name, data_dir)
            expected_type = dict if name == "rates" else list
            if not isinstance(data, expected_type):
                raise StorageError(f"Неверный формат данных для {path.name}")
            temporary_path = None
            try:
                text = (
                    json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=path.parent,
                    delete=False,
                ) as stream:
                    temporary_path = Path(stream.name)
                    stream.write(text)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_path, path)
            except (OSError, TypeError, ValueError) as exc:
                raise StorageError(f"Не удалось сохранить {path.name}: {exc}") from exc
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)

    @contextmanager
    def transaction(self, *names: str, data_dir: str | Path | None = None):
        """Чтение → изменение копий → запись под одной блокировкой.

        При обычной ошибке записи уже записанные документы восстанавливаются.
        Это не межпроцессная или устойчивая к аварийному завершению транзакция.
        """
        with self._lock:
            original = {name: self.read(name, data_dir) for name in names}
            working = deepcopy(original)
            yield working
            changed = [name for name in names if working[name] != original[name]]
            # Проверяем сериализацию всех документов до первой записи.
            try:
                for name in changed:
                    json.dumps(working[name], allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise StorageError(
                    f"Данные не могут быть сохранены в JSON: {exc}"
                ) from exc
            committed = []
            try:
                for name in changed:
                    self.write(name, working[name], data_dir)
                    committed.append(name)
            except StorageError:
                for name in reversed(committed):
                    self.write(name, original[name], data_dir)
                raise


class JsonStorage:
    """Привязка каталога к общему менеджеру без смены путей чужих сессий."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        directory = (
            data_dir if data_dir is not None else SettingsLoader().get("DATA_DIR")
        )
        self.data_dir = Path(directory).resolve()
        self.manager = DatabaseManager()

    def read(self, name: str) -> list | dict:
        return self.manager.read(name, self.data_dir)

    def write(self, name: str, data: list | dict) -> None:
        self.manager.write(name, data, self.data_dir)

    def transaction(self, *names: str):
        return self.manager.transaction(*names, data_dir=self.data_dir)
