import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path

from valutatrade_hub.core.currencies import normalize_code
from valutatrade_hub.core.exceptions import StorageError
from valutatrade_hub.core.utils import RateService, validate_amount
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.config import ParserConfig


class RatesStorage:
    """Атомарное сохранение истории и последнего среза котировок."""

    def __init__(self, config: ParserConfig) -> None:
        self.rates_path = Path(config.RATES_FILE_PATH)
        self.history_path = Path(config.HISTORY_FILE_PATH)
        if self.rates_path.resolve() == self.history_path.resolve():
            raise ValueError("Пути кеша и истории должны различаться")

    @staticmethod
    def _read(path: Path, expected: type):
        try:
            text = path.read_text(encoding="utf-8")
            result = json.loads(text) if text.strip() else expected()
            if not isinstance(result, expected):
                raise TypeError("неверный формат")
            return result
        except FileNotFoundError:
            return expected()
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Не удалось прочитать {path.name}: {exc}") from exc

    def read_cache(self) -> dict:
        """Прочитать снимок курсов; вернуть пустой словарь при отсутствии."""
        return self._read(self.rates_path, dict)

    @staticmethod
    def _write(path: Path, data) -> None:
        temporary = None
        try:
            text = (
                json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Не удалось сохранить {path.name}: {exc}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def save(self, records: list[dict], last_refresh: str) -> int:
        # Shared with Core within this process. Each file is replaced atomically.
        """Добавить уникальные замеры и заменить только более свежие котировки."""
        with DatabaseManager._lock:
            cache = self.read_cache()
            history = self._read(self.history_path, list)
            try:
                ids = {row["id"] for row in history}
                pairs = deepcopy(cache.get("pairs", {}))
                if not isinstance(pairs, dict):
                    raise TypeError("pairs должен быть объектом")
                updated = 0
                for record in records:
                    source, target = record["from_currency"], record["to_currency"]
                    if (
                        normalize_code(source) != source
                        or normalize_code(target) != target
                    ):
                        raise ValueError("Коды должны быть в верхнем регистре")
                    validate_amount(record["rate"])
                    timestamp = RateService._timestamp(record["timestamp"])
                    pair = f"{source}_{target}"
                    expected_id = f"{pair}_{record['timestamp']}"
                    if record["id"] != expected_id or not record["source"]:
                        raise ValueError("Неверный id или источник")
                    if record["id"] not in ids:
                        history.append(record)
                        ids.add(record["id"])
                    previous = pairs.get(pair)
                    if previous is None or timestamp > RateService._timestamp(
                        previous["updated_at"]
                    ):
                        pairs[pair] = {
                            "rate": record["rate"],
                            "updated_at": record["timestamp"],
                            "source": record["source"],
                        }
                        updated += 1
                snapshot = {"pairs": pairs, "last_refresh": last_refresh}
                json.dumps(history, allow_nan=False)
                json.dumps(snapshot, allow_nan=False)
            except (KeyError, TypeError, ValueError) as exc:
                raise StorageError(f"Некорректные данные курсов: {exc}") from exc
            # History first: a retry after a crash safely deduplicates measurements.
            self._write(self.history_path, history)
            self._write(self.rates_path, snapshot)
            return updated
