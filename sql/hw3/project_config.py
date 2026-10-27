"""Чтение конфигурации по образцу ProjectPostgreSQL.
Пароль рекомендуется передавать через PGPASSWORD, а не хранить в архиве.
"""
import os
from pathlib import Path

import yaml


class ProjectConfig:
    def __init__(self, path=None):
        path = Path(path) if path else Path(__file__).resolve().parent / "config.yaml"
        with path.open(encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}
        self.dbname = os.getenv("PGDATABASE", config.get("dbname", "warehouse"))
        self.user = os.getenv("PGUSER", config.get("user", "postgres"))
        self.password = os.getenv("PGPASSWORD", config.get("password", ""))
        self.host = os.getenv("PGHOST", config.get("host", "localhost"))
        self.port = int(os.getenv("PGPORT", config.get("port", 5432)))
        prefix = config.get("dbtableprefix", "public.")
        if not isinstance(prefix, str) or not prefix.endswith(".") or not prefix[:-1].strip():
            raise ValueError("dbtableprefix должен иметь формат 'public.'")
        self.schema = prefix[:-1]
