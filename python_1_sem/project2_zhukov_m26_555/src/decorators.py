import time
from functools import wraps


def handle_db_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as error:
            print(f"Ошибка: ключ {error} не найден.")
            return None
        except ValueError as error:
            print(f"Ошибка: {error}")
            return None
        except FileNotFoundError as error:
            print(f"Ошибка: файл не найден: {error}")
            return None

    return wrapper


def confirm_action(action_name):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            answer = input(
                f'Вы уверены, что хотите выполнить '
                f'"{action_name}"? [y/n]: '
            )

            if answer.lower() != "y":
                print("Операция отменена.")
                return None

            return func(*args, **kwargs)

        return wrapper

    return decorator


def log_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.monotonic()

        result = func(*args, **kwargs)

        end_time = time.monotonic()
        execution_time = end_time - start_time

        print(
            f"Функция {func.__name__} выполнилась "
            f"за {execution_time:.3f} секунд"
        )

        return result

    return wrapper


def create_cacher():
    cache = {}

    def cache_result(key, value_func):
        if key in cache:
            return cache[key]

        result = value_func()
        cache[key] = result

        return result

    return cache_result