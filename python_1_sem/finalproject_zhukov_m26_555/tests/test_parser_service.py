import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from valutatrade_hub.cli.interface import main
from valutatrade_hub.core.exceptions import ApiRequestError, StorageError
from valutatrade_hub.core.utils import RateService
from valutatrade_hub.infra.database import JsonStorage
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
    utc_timestamp,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater
from valutatrade_hub.parser_service.views import cached_rates


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = ParserConfig(
            EXCHANGERATE_API_KEY="secret-test-key",
            RATES_FILE_PATH=str(self.directory / "rates.json"),
            HISTORY_FILE_PATH=str(self.directory / "exchange_rates.json"),
        )
        self.storage = RatesStorage(self.config)
        self.now = utc_timestamp()

    def record(self, code="BTC", rate=100, timestamp=None):
        timestamp = timestamp or self.now
        return {
            "id": f"{code}_USD_{timestamp}",
            "from_currency": code,
            "to_currency": "USD",
            "rate": rate,
            "timestamp": timestamp,
            "source": "test",
            "meta": {},
        }

    def response(self, payload, status=200):
        return Mock(
            status_code=status,
            headers={"ETag": 'W/"abc"'},
            json=Mock(return_value=payload),
        )

    @patch("valutatrade_hub.parser_service.api_clients.requests.get")
    def test_crypto_request_and_metadata(self, get):
        get.return_value = self.response(
            {
                name: {"usd": price, "last_updated_at": 1700000000}
                for name, price in (
                    ("bitcoin", 60000),
                    ("ethereum", 3000),
                    ("solana", 150),
                )
            }
        )
        client = CoinGeckoClient(self.config)
        self.assertEqual(client.fetch_rates()["SOL_USD"], 150)
        self.assertEqual(
            get.call_args.kwargs["params"]["ids"], "bitcoin,ethereum,solana"
        )
        self.assertNotIn("headers", get.call_args.kwargs)
        self.assertEqual(client.metadata["BTC_USD"]["meta"]["raw_id"], "bitcoin")

    @patch("valutatrade_hub.parser_service.api_clients.requests.get")
    def test_fiat_inverse_and_timestamp(self, get):
        get.return_value = self.response(
            {
                "result": "success",
                "base_code": "USD",
                "time_last_update_unix": 1700000000,
                "conversion_rates": {"EUR": 0.8, "GBP": 0.5, "RUB": 100},
            }
        )
        client = ExchangeRateApiClient(self.config)
        self.assertEqual(
            client.fetch_rates(), {"EUR_USD": 1.25, "GBP_USD": 2, "RUB_USD": 0.01}
        )
        self.assertEqual(
            client.metadata["EUR_USD"]["timestamp"], "2023-11-14T22:13:20Z"
        )

    @patch("valutatrade_hub.parser_service.api_clients.requests.get")
    def test_errors_do_not_expose_key(self, get):
        client = ExchangeRateApiClient(self.config)
        for status in (401, 429, 500):
            get.return_value = self.response({}, status)
            with self.assertRaisesRegex(ApiRequestError, str(status)) as caught:
                client.fetch_rates()
            self.assertNotIn("secret-test-key", str(caught.exception))
        get.side_effect = requests.Timeout("https://example/secret-test-key")
        with self.assertRaises(ApiRequestError) as caught:
            client.fetch_rates()
        self.assertNotIn("secret-test-key", str(caught.exception))

    @patch("valutatrade_hub.parser_service.api_clients.requests.get")
    def test_invalid_rates_rejected(self, get):
        for rate in (True, 0, -1, "123", None, float("nan"), float("inf")):
            get.return_value = self.response({"bitcoin": {"usd": rate}})
            with self.assertRaises(ApiRequestError):
                CoinGeckoClient(self.config).fetch_rates()

    def test_dedup_newest_wins_and_preserves_other_pairs(self):
        self.assertEqual(
            self.storage.save([self.record(), self.record("ETH", 10)], self.now), 2
        )
        self.assertEqual(self.storage.save([self.record()], self.now), 0)
        old = utc_timestamp(datetime.now(timezone.utc) - timedelta(days=1))
        self.assertEqual(
            self.storage.save([self.record(rate=1, timestamp=old)], self.now), 0
        )
        self.assertEqual(self.storage.read_cache()["pairs"]["BTC_USD"]["rate"], 100)
        self.assertEqual(len(json.loads(self.storage.history_path.read_text())), 3)
        self.assertIn("ETH_USD", self.storage.read_cache()["pairs"])

    def test_partial_failure_and_total_failure_preserve_cache(self):
        good = Mock(
            source="CoinGecko",
            metadata={},
            fetch_rates=Mock(return_value={"BTC_USD": 100}),
        )
        bad = Mock(
            source="ExchangeRate-API",
            fetch_rates=Mock(side_effect=ApiRequestError("offline")),
        )
        result = RatesUpdater([bad, good], self.storage).run_update()
        self.assertEqual(result["updated"], 1)
        self.assertEqual(len(result["errors"]), 1)
        before = self.storage.rates_path.read_bytes()
        with self.assertRaises(ApiRequestError):
            RatesUpdater([bad], self.storage).run_update()
        self.assertEqual(before, self.storage.rates_path.read_bytes())

    def test_corrupt_history_not_overwritten(self):
        self.storage.history_path.write_text("broken")
        with self.assertRaises(StorageError):
            self.storage.save([self.record()], self.now)
        self.assertEqual(self.storage.history_path.read_text(), "broken")

    def test_atomic_replace_failure_keeps_cache(self):
        self.storage.save([self.record()], self.now)
        original = self.storage.rates_path.read_bytes()
        with (
            patch(
                "valutatrade_hub.parser_service.storage.os.replace",
                side_effect=OSError("fail"),
            ),
            self.assertRaises(StorageError),
        ):
            self.storage._write(self.storage.rates_path, {})
        self.assertEqual(original, self.storage.rates_path.read_bytes())
        self.assertEqual(len(list(self.directory.iterdir())), 2)

    def test_core_cross_rate_and_staleness(self):
        self.storage.save([self.record(), self.record("EUR", 2)], self.now)
        core = RateService(JsonStorage(self.directory))
        self.assertEqual(core.get_rate("BTC", "EUR")["rate"], 50)
        self.assertEqual(core.get_rate("USD", "EUR")["rate"], 0.5)
        cache = self.storage.read_cache()
        cache["pairs"]["BTC_USD"]["updated_at"] = "2000-01-01T00:00:00Z"
        self.storage._write(self.storage.rates_path, cache)
        before = self.storage.rates_path.read_bytes()
        with self.assertRaisesRegex(ApiRequestError, "update-rates"):
            core.get_rate("BTC", "USD")
        self.assertEqual(before, self.storage.rates_path.read_bytes())

    def test_show_filters_conversion_and_stale_label(self):
        old = "2000-01-01T00:00:00Z"
        self.storage.save(
            [self.record(timestamp=old), self.record("ETH", 10), self.record("EUR", 2)],
            self.now,
        )
        rows = cached_rates(self.storage.read_cache(), 300, top=2, base="EUR")
        self.assertEqual([row["pair"] for row in rows], ["BTC_EUR", "ETH_EUR"])
        self.assertEqual(rows[0]["rate"], 50)
        self.assertTrue(rows[0]["stale"])
        with self.assertRaisesRegex(ValueError, "ABC"):
            cached_rates(self.storage.read_cache(), 300, currency="ABC")

    def test_cli_selected_source(self):
        with (
            patch.object(CoinGeckoClient, "fetch_rates", return_value={"BTC_USD": 42}),
            patch.object(ExchangeRateApiClient, "fetch_rates") as fiat,
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(
                main(
                    [
                        "--data-dir",
                        str(self.directory),
                        "update-rates",
                        "--source",
                        "coingecko",
                    ]
                ),
                0,
            )
            fiat.assert_not_called()
            self.assertIn("Обновлено курсов: 1", output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                main(
                    [
                        "--data-dir",
                        str(self.directory),
                        "show-rates",
                        "--currency",
                        "BTC",
                    ]
                ),
                0,
            )
            self.assertIn("42.00000000", output.getvalue())


if __name__ == "__main__":
    unittest.main()
