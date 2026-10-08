import inspect
import math
from functools import wraps

from valutatrade_hub.core.constants import REFERENCE_CURRENCY
from valutatrade_hub.logging_config import configure_logging


def _log_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def log_action(action: str | None = None, *, verbose: bool = False):
    """Логировать разрешённые поля; пароли, соли и хеши не включаются."""

    def decorate(function):
        signature = inspect.signature(function)

        @wraps(function)
        def wrapper(self, *args, **kwargs):
            logger = configure_logging()
            arguments = signature.bind(self, *args, **kwargs).arguments
            user = getattr(self, "_current_user", None)
            context = {
                "action": (action or function.__name__).upper(),
                "username": arguments.get("username", user.username if user else None),
                "user_id": (
                    user.user_id if user and "username" not in arguments else None
                ),
                "currency_code": arguments.get(
                    "currency", arguments.get("from_currency")
                ),
                "amount": _log_value(arguments.get("amount")),
                "rate": None,
                "base": (
                    arguments.get("to_currency", REFERENCE_CURRENCY)
                    if "currency" in arguments or "from_currency" in arguments
                    else None
                ),
            }
            try:
                result = function(self, *args, **kwargs)
            except Exception as exc:
                context.update(
                    result="ERROR",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                logger.info("%s", context["action"], extra={"action_context": context})
                raise
            context.update(result="OK", error_type=None, error_message=None)
            if isinstance(result, dict):
                for key in ("username", "user_id", "currency_code", "rate"):
                    if key in result:
                        context[key] = result[key]
                if verbose:
                    context.update(
                        {
                            key: result[key]
                            for key in ("before", "after")
                            if key in result
                        }
                    )
            logger.info("%s", context["action"], extra={"action_context": context})
            return result

        return wrapper

    return decorate
