import time


def handle_db_errors(func):
    """Перехватить ошибки базы данных и вывести сообщение."""

    def wrapper(*args, **kwargs):
        """Выполнить функцию с дополнительной обработкой."""
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

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def confirm_action(action_name):
    """Запросить подтверждение перед выполнением операции."""

    def decorator(func):
        """Обернуть функцию подтверждением операции."""

        def wrapper(*args, **kwargs):
            """Выполнить функцию с дополнительной обработкой."""
            answer = input(f'Вы уверены, что хотите выполнить "{action_name}"? [y/n]: ')

            if answer.lower() != "y":
                print("Операция отменена.")
                return None

            return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


def log_time(func):
    """Вывести длительность выполнения операции."""

    def wrapper(*args, **kwargs):
        """Выполнить функцию с дополнительной обработкой."""
        start_time = time.monotonic()

        result = func(*args, **kwargs)

        end_time = time.monotonic()
        execution_time = end_time - start_time

        print(f"Функция {func.__name__} выполнилась за {execution_time:.3f} секунд")

        return result

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def create_cacher():
    """Создать замыкание для кэширования результатов."""
    cache = {}

    def cache_result(key, value_func):
        """Вернуть сохранённый результат или вычислить новый."""
        if key in cache:
            return cache[key]

        result = value_func()
        cache[key] = result

        return result

    return cache_result
