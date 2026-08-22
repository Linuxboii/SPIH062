"""Connection pool. One pool for the process, opened at startup."""
from __future__ import annotations

from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

_dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")

pool = ConnectionPool(
    _dsn,
    min_size=1,
    max_size=8,
    kwargs={"row_factory": dict_row},
    open=False,
)


@contextmanager
def cursor():
    with pool.connection() as conn, conn.cursor() as cur:
        yield cur


def fetch_all(sql: str, params: tuple | dict = ()) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(sql: str, params: tuple | dict = ()) -> dict | None:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()
