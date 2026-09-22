"""Разбор команд с сохранением строк в кавычках."""

import shlex


def tokenize(text):
    """Разделить команду, сохранив кавычки и знаки пунктуации."""
    lexer = shlex.shlex(text, posix=False, punctuation_chars="(),=")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = []
    for token in lexer:
        if all(char in "(),=" for char in token):
            tokens.extend(token)
        else:
            tokens.append(token)
    return tokens


def parse_value(value):
    """Разобрать строковое, целое или логическое значение."""
    value = value.strip()
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Некорректное значение: {value}.") from None


def parse_condition(condition):
    """Разобрать равенство столбца и значения."""
    tokens = tokenize(condition)
    if len(tokens) != 3 or tokens[1] != "=":
        raise ValueError(f"Некорректное условие: {condition}.")
    return {tokens[0]: parse_value(tokens[2])}


def parse_insert(command):
    """Разобрать имя таблицы и список добавляемых значений."""
    tokens = tokenize(command)
    if (
        len(tokens) < 6
        or tokens[0].lower() != "insert"
        or tokens[1].lower() != "into"
        or tokens[3].lower() != "values"
        or tokens[4] != "("
        or tokens[-1] != ")"
    ):
        raise ValueError("Некорректная команда insert.")
    values = tokens[5:-1]
    if values and (len(values) % 2 == 0 or any(token != "," for token in values[1::2])):
        raise ValueError("Некорректные значения insert.")
    return tokens[2], [parse_value(value) for value in values[::2]]


def parse_select(command):
    """Разобрать выборку с необязательным условием."""
    tokens = tokenize(command)
    if (
        len(tokens) not in (3, 7)
        or tokens[0].lower() != "select"
        or tokens[1].lower() != "from"
    ):
        raise ValueError("Некорректная команда select.")
    if len(tokens) == 3:
        return tokens[2], None
    if tokens[3].lower() != "where":
        raise ValueError("Ожидалось where.")
    condition = " ".join(tokens[4:])
    parse_condition(condition)
    return tokens[2], condition


def parse_update(command):
    """Разобрать изменение и условие без разделения внутри строк."""
    tokens = tokenize(command)
    if (
        len(tokens) != 10
        or tokens[0].lower() != "update"
        or tokens[2].lower() != "set"
        or tokens[6].lower() != "where"
    ):
        raise ValueError("Некорректная команда update.")
    return (
        tokens[1],
        parse_condition(" ".join(tokens[3:6])),
        parse_condition(" ".join(tokens[7:])),
    )


def parse_delete(command):
    """Разобрать удаление записей по условию."""
    tokens = tokenize(command)
    if (
        len(tokens) != 7
        or tokens[0].lower() != "delete"
        or tokens[1].lower() != "from"
        or tokens[3].lower() != "where"
    ):
        raise ValueError("Некорректная команда delete.")
    return tokens[2], parse_condition(" ".join(tokens[4:]))
