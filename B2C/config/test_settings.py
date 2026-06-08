import atexit
import os

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

from testcontainers.postgres import PostgresContainer  # noqa: E402


_postgres = PostgresContainer("postgres:16")
_postgres.start()


def _stop_postgres_container():
    _postgres.stop()


atexit.register(_stop_postgres_container)

os.environ["POSTGRES_DB"] = _postgres.dbname
os.environ["POSTGRES_USER"] = _postgres.username
os.environ["POSTGRES_PASSWORD"] = _postgres.password
os.environ["POSTGRES_HOST"] = _postgres.get_container_host_ip()
os.environ["POSTGRES_PORT"] = str(_postgres.get_exposed_port(5432))

from config.settings import *  # noqa: E402,F403
