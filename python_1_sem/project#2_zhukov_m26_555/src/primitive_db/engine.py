import prompt


def greet_user() -> str:
    welcome = """
    project

    Первая попытка запустить проект!

    ***
    <command> exit - выйти из программы
    <command> help - справочная информация
    Введите команду: help

    <command> exit - выйти из программы
    <command> help - справочная информация
    Введите команду: _
    """
    cmd = prompt.string(welcome)
    return cmd
