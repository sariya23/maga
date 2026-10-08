from datetime import datetime, timezone

from valutatrade_hub.core.currencies import CryptoCurrency, get_currency
from valutatrade_hub.core.utils import RateService, validate_amount


def cached_rates(
    cache: dict, ttl: int, currency=None, top=None, base="USD"
) -> list[dict]:
    pairs = cache.get("pairs", {})
    if not pairs:
        raise ValueError(
            "Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные."
        )
    base = get_currency(base).code
    currency = currency.strip().upper() if currency else None
    if top is not None and top <= 0:
        raise ValueError("--top должен быть положительным целым числом")
    quotes = {
        key.split("_")[0]: entry for key, entry in pairs.items() if key.endswith("_USD")
    }
    quotes["USD"] = {"rate": 1.0, "updated_at": datetime.now(timezone.utc).isoformat()}
    if base not in quotes:
        raise ValueError(f"Курс для '{base}' не найден в кеше.")
    rows = []
    for code in sorted(quotes):
        if code == base or (currency and code != currency):
            continue
        if top is not None and not isinstance(get_currency(code), CryptoCurrency):
            continue
        entry, target = quotes[code], quotes[base]
        timestamps = [
            RateService._timestamp(q["updated_at"])
            for c, q in ((code, entry), (base, target))
            if c != "USD"
        ]
        timestamp = min(timestamps)
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
        rows.append(
            {
                "pair": f"{code}_{base}",
                "rate": validate_amount(
                    validate_amount(entry["rate"]) / validate_amount(target["rate"])
                ),
                "updated_at": timestamp.isoformat(),
                "stale": not 0 <= age < ttl,
            }
        )
    if currency and not rows:
        raise ValueError(f"Курс для '{currency}' не найден в кеше.")
    return (
        sorted(rows, key=lambda row: row["rate"], reverse=True)[:top]
        if top is not None
        else rows
    )
