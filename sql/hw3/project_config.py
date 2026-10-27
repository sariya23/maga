import os
from pathlib import Path
import yaml


class ProjectConfig:
    def __init__(self):
        path = Path(os.environ.get('WAREHOUSE_CONFIG', Path(__file__).with_name('config.yaml')))
        with path.open(encoding='utf-8') as stream:
            config = yaml.safe_load(stream)
        if not isinstance(config, dict):
            raise ValueError('Настройки должны быть словарём YAML.')
        self.connection = {}
        for key, env in [('dbname', 'PGDATABASE'), ('user', 'PGUSER'),
                         ('password', 'PGPASSWORD'), ('host', 'PGHOST'), ('port', 'PGPORT')]:
            value = os.environ.get(env, config.get(key))
            if value is not None:
                self.connection[key] = str(value)
        self.connection['connect_timeout'] = 5
        self.connection['options'] = '-c statement_timeout=5000 -c lock_timeout=3000'
