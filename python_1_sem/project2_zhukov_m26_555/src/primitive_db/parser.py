import ast
import re


def parse_value(value):
    value = value.strip()

    if value.lower() == "true":
        return True

    if value.lower() == "false":
        return False

    if (
        value.startswith('"')
        and value.endswith('"')
    ):
        return value[1:-1]

    try:
        return int(value)
    except ValueError:
        raise ValueError(
            f"Некорректное значение: {value}."
        )


def parse_condition(condition):
    parts = condition.split("=", 1)

    if len(parts) != 2:
        raise ValueError(
            f"Некорректное условие: {condition}."
        )

    column = parts[0].strip()

    if not column:
        raise ValueError(
            f"Некорректное условие: {condition}."
        )

    value = parse_value(
        parts[1]
    )

    return {
        column: value,
    }


def parse_insert(command):
    pattern = (
        r"^insert\s+into\s+(\w+)"
        r"\s+values\s*\((.*)\)$"
    )

    match = re.match(
        pattern,
        command,
        re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            "Некорректная команда insert."
        )

    table_name = match.group(1)
    values_string = match.group(2)

    values_string = re.sub(
        r"\btrue\b",
        "True",
        values_string,
        flags=re.IGNORECASE,
    )

    values_string = re.sub(
        r"\bfalse\b",
        "False",
        values_string,
        flags=re.IGNORECASE,
    )

    try:
        values = ast.literal_eval(
            f"({values_string},)"
        )
    except (ValueError, SyntaxError):
        raise ValueError(
            "Некорректные значения insert."
        )

    return table_name, list(values)