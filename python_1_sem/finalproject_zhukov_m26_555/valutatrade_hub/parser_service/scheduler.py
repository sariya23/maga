import logging
import math
from threading import Event


def run_scheduler(updater, interval: float = 3600, stop: Event | None = None) -> None:
    """Update immediately, then wait interval seconds; Event allows clean shutdown."""
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("Интервал обновления должен быть положительным")
    stop = stop or Event()
    while not stop.is_set():
        try:
            updater.run_update()
        except (ValueError, OSError) as exc:
            logging.getLogger("valutatrade.parser").error(
                "Scheduled update failed: %s", exc
            )
        if stop.wait(interval):
            break
