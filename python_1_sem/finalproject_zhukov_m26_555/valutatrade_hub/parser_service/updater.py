import logging

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import utc_timestamp

logger = logging.getLogger("valutatrade.parser")


class RatesUpdater:
    """Последовательный сбор котировок с изоляцией отказов источников."""

    def __init__(self, clients, storage) -> None:
        self.clients = list(clients)
        self.storage = storage

    def run_update(self) -> dict:
        """Сохранить успешные замеры и вернуть число обновлений и ошибки."""
        logger.info("Starting rates update")
        records, errors = [], []
        for client in self.clients:
            logger.info("Fetching from %s", client.source)
            try:
                rates = client.fetch_rates()
                received = utc_timestamp()
                for pair, rate in rates.items():
                    source, target = pair.split("_")
                    details = client.metadata.get(pair, {})
                    timestamp = details.get("timestamp", received)
                    records.append(
                        {
                            "id": f"{pair}_{timestamp}",
                            "from_currency": source,
                            "to_currency": target,
                            "rate": rate,
                            "timestamp": timestamp,
                            "source": client.source,
                            "meta": details.get("meta", {}),
                        }
                    )
                logger.info("%s OK (%d rates)", client.source, len(rates))
            except ApiRequestError as exc:
                errors.append(str(exc))
                logger.error("Failed to fetch from %s: %s", client.source, exc)
        if not records:
            logger.error("Update failed: no rates received")
            raise ApiRequestError("; ".join(errors) or "источники не вернули курсы")
        refreshed = utc_timestamp()
        logger.info(
            "Writing %d measurements to %s", len(records), self.storage.rates_path
        )
        try:
            count = self.storage.save(records, refreshed)
        except (ValueError, OSError):
            logger.error("Failed to save rates")
            raise
        logger.info("Update completed: %d rates updated, %d errors", count, len(errors))
        return {"updated": count, "last_refresh": refreshed, "errors": errors}
