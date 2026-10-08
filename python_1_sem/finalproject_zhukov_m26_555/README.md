# ValutaTrade Hub

Учебная платформа с CLI для виртуального валютного портфеля. Требуется Python 3.10+.
HTTP-запросы выполняются через `requests`, `.env` загружается через `python-dotenv`.

## Запуск

```bash
uv sync
uv run valutatrade
```

Внутри одной интерактивной сессии:

```text
update-rates
register --username alice --password 1234
login --username alice --password 1234
show-portfolio
buy --currency BTC --amount 0.05
buy --currency EUR --amount 200
show-portfolio --base USD
sell --currency BTC --amount 0.01
get-rate --from USD --to BTC
exit
```

`help`, `help get-rate` и `<команда> --help` показывают справку. Аргументы с пробелами заключайте
в кавычки. Вход действует до выхода из текущего процесса; регистрация не выполняет
автоматический вход. Для `show-portfolio`, `buy` и `sell` нужен `login`.

Отдельную публичную команду можно выполнить без интерактивного режима:

```bash
python3 main.py get-rate --from EUR --to USD
```

Для другого каталога данных: `python3 main.py --data-dir /tmp/valutatrade-demo`.
Этот параметр задаётся при запуске программы и переопределяет `DATA_DIR` из
`config.json`. Относительные пути в конфигурации отсчитываются от её каталога,
поэтому запуск из другого рабочего каталога не меняет расположение данных.

## Данные и расчёты

- `data/users.json`: пользователи, SHA-256 от `password + salt`, индивидуальная
  случайная соль и дата регистрации. Открытый пароль не сохраняется.
- `data/portfolios.json`: кошельки, связанные с `user_id`. При регистрации
  создаётся пустой портфель.
- `data/rates.json`: курсы, время обновления и источник. Отсутствующие и пустые
  файлы считаются пустым хранилищем; повреждённый JSON вызывает ошибку.

В текущем упрощённом режиме `buy` добавляет указанное количество валюты, `sell`
списывает его. USD-эквивалент выводится только для отчёта, отдельного расчёта
через USD-кошелёк нет. Балансы используют `float` согласно заданию.

Parser Service получает котировки CoinGecko и ExchangeRate-API. Core читает только
`rates.json` в формате `{"pairs": {"BTC_USD": {"rate": 60000, "updated_at": "...", "source": "CoinGecko"}}, "last_refresh": "..."}`.
Свежий кеш по умолчанию действует 5 минут; доступны прямые, обратные и кросс-курсы
через USD. Если свежих данных нет, Core предлагает выполнить `update-rates`.
Фиксированная заглушка больше не используется. Старый плоский кеш следует обновить
через `update-rates`. Временные метки сохраняются в UTC.

## Parser Service

В `.env` в корне проекта задайте `EXCHANGERATE_API_KEY=ваш_ключ`.
Файл исключён из Git. Загрузка `.env` и чтение переменных окружения выполняются
только в функции `main()` в `cli/interface.py`, вызываемой из `main.py`.
Поддерживается также имя `EXCHANGE_RATE_API` из существующего `.env`;
при наличии обоих ключей приоритет имеет `EXCHANGERATE_API_KEY`.
Уже заданные переменные окружения имеют приоритет. CoinGecko вызывается без ключа.

```bash
uv run python main.py update-rates
uv run python main.py update-rates --source coingecko
uv run python main.py update-rates --source exchangerate
uv run python main.py show-rates --currency RUB
uv run python main.py show-rates --top 2
uv run python main.py show-rates --base EUR
uv run python main.py schedule-rates --interval 3600
```

Эти команды также доступны в интерактивной сессии. Планировщик обновляет сразу,
затем ждёт указанный интервал; Ctrl+C останавливает его. Интервал выбирайте с учётом
лимитов API и TTL: повторный запрос не делает старую котировку свежей.

`ParserConfig` содержит эндпоинты, таймаут, пути и списки валют: BTC, ETH, SOL,
EUR, GBP, RUB; базовая валюта по умолчанию USD. Core и представление кросс-курсов
используют кеш пар к USD. `--data-dir` применяется и к кешу, и к истории.

[ExchangeRate-API](https://www.exchangerate-api.com/docs/standard-requests) возвращает
`conversion_rates` для направления USD→валюта. Клиент сохраняет обратный курс:
например, USD→EUR = 0.927 означает EUR→USD ≈ 1.07875. Для совместимости поддерживается
также поле `rates`. CoinGecko запрашивается по ID с `include_last_updated_at=true`.
Метки источника сохраняются в UTC; если CoinGecko не передал время, используется
время получения ответа.

`data/exchange_rates.json` — массив исторических измерений с ID вида
`BTC_USD_<ISO-UTC timestamp>`, источником и метаданными запроса. Повторные ID
не добавляются. Кеш содержит по одному последнему значению пары; только более
свежая котировка заменяет прежнюю. Не обновлённые пары сохраняются.
Каждый файл записывается атомарно через временный файл, fsync и rename.
История записывается первой: повтор после сбоя не дублирует замеры. Замена двух файлов
не является единой транзакцией; одновременный запуск нескольких процессов обновления
не поддерживается.

Ошибка одного API не мешает сохранить данные другого. При полном отказе файлы
остаются без изменений. Частичный и полный отказ дают код выхода 1 для разовой команды.
Журнал шагов и ошибок с ротацией находится в `logs/parser.log`; ключ API в него
не выводится. `show-rates` помечает устаревшие котировки и предлагает обновление;
`--top` выбирает только криптовалюты, сортируя по цене единицы, а не капитализации.

Единый контракт `CoreService.get_rate(from_currency, to_currency)` возвращает:

```python
{
    "from_currency": "EUR",
    "to_currency": "USD",
    "rate": 1.1,
    "updated_at": "2026-10-08T12:00:00+00:00",
}
```

CLI разбирает команды и форматирует ответы. Операции и сессия находятся в
`core/usecases.py`, сервис курсов — в `core/utils.py`, JSON-хранилище — в
`infra/database.py`. Ошибки получения курса преобразуются в
`ApiRequestError`; устаревшая котировка при сбое не используется.

## Валюты и ошибки

`Currency` — абстрактный класс с методом `get_display_info()`. `FiatCurrency`
добавляет страну эмиссии, `CryptoCurrency` — алгоритм и капитализацию.
Название не может быть пустым; код в объекте — 2–5 латинских букв/цифр в верхнем
регистре, без пробелов. `get_currency()` нормализует пользовательский ввод и
возвращает объект из реестра USD, EUR, GBP, RUB, BTC, ETH, SOL. Капитализация и описание
алгоритмов в реестре — учебные примеры, без обновления из API.

```text
[FIAT] USD — US Dollar (Issuing: United States)
[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)
```

Код кошелька доступен только для чтения; баланс меняется через проверяемое
свойство и методы. `Wallet.withdraw()` и `sell()` при нехватке средств бросают
`InsufficientFundsError`. Отсутствующий кошелёк при продаже означает доступный
баланс 0. Регистрация по-прежнему создаёт пустой портфель.

| Команда/слой | Исключение | Сообщение CLI |
| --- | --- | --- |
| `sell`, `Wallet.withdraw` | `InsufficientFundsError` | `Недостаточно средств: доступно 0.0400 BTC, требуется 0.0500 BTC` |
| `buy`, `sell`, `show-portfolio`, `get-rate` | `CurrencyNotFoundError` | `Неизвестная валюта 'ABC'` + поддерживаемые коды и `help get-rate` |
| `buy`, `sell`, `show-portfolio`, `get-rate` при сбое курсов | `ApiRequestError` | `Ошибка при обращении к внешнему API: {reason}` + предложение повторить позже / проверить сеть |
| `buy`, `sell` | `ValueError` / `TypeError` | `'amount' должен быть положительным числом` |
| Операции с JSON | `StorageError` | Сообщение о файле и причине ошибки |

Код неизвестной валюты в кеше не расширяет реестр. Ошибки не завершают
интерактивную сессию; отдельная команда возвращает код выхода 1.

## Конфигурация и Singleton

`SettingsLoader()` и `DatabaseManager()` реализованы через `__new__` с блокировкой:
повторные вызовы возвращают тот же экземпляр. При импорте экземпляры не создаются.
Выбран `__new__` как более простой и явный вариант по сравнению с метаклассом.

`SettingsLoader.get(key, default=None)` читает кеш. `reload()` перечитывает
конфигурацию; `reload(path)` явно выбирает другой JSON-файл. Некорректные настройки
не заменяют предыдущие. Значения по умолчанию также заданы в коде.

| Ключ в `config.json` | По умолчанию | Назначение |
| --- | --- | --- |
| `DATA_DIR` | `data` | Каталог данных |
| `USERS_FILE` | `users.json` | Имя файла пользователей |
| `PORTFOLIOS_FILE` | `portfolios.json` | Имя файла портфелей |
| `RATES_FILE` | `rates.json` | Имя файла кеша курсов |
| `RATES_TTL_SECONDS` | `300` | Предельный возраст котировки в секундах |
| `DEFAULT_BASE_CURRENCY` | `USD` | База для `show-portfolio` без `--base` |
| `LOG_DIR` / `LOG_FILE` | `logs` / `actions.log` | Расположение журнала |
| `LOG_FORMAT` | `json` | Одна JSON-запись на строку |
| `LOG_LEVEL` | `INFO` | Уровень; для отладки можно задать `DEBUG` |
| `LOG_MAX_BYTES` | `1048576` | Порог ротации, 1 MiB |
| `LOG_BACKUP_COUNT` | `3` | Количество архивных файлов |

`CoreService` использует настройки для каталога и базовой валюты, а `RateService`
проверяет актуальный TTL при каждом запросе. `JsonStorage` привязывает каталог
к единственному `DatabaseManager`, не меняя путь у других сессий.
`DatabaseManager.read()`, `write()` и `transaction()` обслуживают JSON-файлы.

Регистрация выполняет изменение пользователей и портфелей в одной операции
`transaction("users", "portfolios")`; сделки — в `transaction("portfolios")`,
Parser записывает кеш и историю отдельно. Чтение, изменение и запись защищены
общей блокировкой внутри процесса. Каждый файл сохраняется через временный файл,
`fsync` и замену. При обычной ошибке записи документы откатываются. Это не
транзакционная СУБД: аварийное завершение между заменами файлов и параллельная
работа нескольких процессов не покрываются этой гарантией.

## Журнал операций

`@log_action` применяется к `register`, `login`, `buy`, `sell`.
Успехи и ошибки пишутся на уровне INFO в JSON Lines. Поля: `timestamp` (ISO UTC),
`level`, `action`, `username`, `user_id`, `currency_code`, `amount`, `rate`, `base`,
`result`, `error_type`, `error_message`. Неприменимые значения — `null`.
Для сделок `verbose=True` добавляет `before` и `after` при успехе.
Декоратор сохраняет метаданные функции и пробрасывает исходное исключение.
Пароли, соли и хеши не записываются.

Ротация создаёт `actions.log.1`–`actions.log.3`. Повторная настройка логирования
не добавляет дублирующие обработчики. Журналы исключены через `.gitignore`.

## Проверка

```bash
make lint
make build
```

## Структура проекта

```text
.
├── data/
│   ├── users.json
│   ├── portfolios.json
│   ├── rates.json
│   └── exchange_rates.json  # создаётся Parser при успешном обновлении
├── valutatrade_hub/
│   ├── core/               # currencies, exceptions, models, usecases, utils
│   ├── infra/              # settings, database
│   ├── parser_service/     # config, api_clients, updater, storage, scheduler, views
│   ├── cli/interface.py
│   ├── logging_config.py
│   └── decorators.py
├── main.py
├── config.json
├── pyproject.toml
├── uv.lock
├── Makefile
├── .env.example
└── README.md
```

`make install` устанавливает зависимости; `make project` / `make run` запускает CLI.
`make lint` проверяет стиль и форматирование, `make format` форматирует код,
`make build` создаёт wheel и исходный архив в `dist/`. После `uv sync` доступна
команда `uv run valutatrade` с теми же аргументами, что у `main.py`.

`Portfolio.get_total_value(base_currency='USD')` использует свежий кеш через
поставщика курсов. CoreService передаёт ему свой RateService, сохраняя выбранный
каталог данных. Для отдельного Portfolio по умолчанию используются настройки
проекта. SOL и GBP обрабатываются так же, как остальные валюты; старые котировки
не заменяются фиксированными значениями.

## Демо

[Смотреть запись работы ValutaTrade Hub на asciinema](https://asciinema.org/a/sLXilBDbUKHWoYZZ).
