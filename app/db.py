import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / 'data' / 'app.db'


def dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@contextmanager
def get_conn(row_factory: bool = False):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    if row_factory:
        conn.row_factory = dict_factory
    try:
        yield conn
    finally:
        conn.close()


def execute(script: str, params: Iterable[Any] | None = None) -> int:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(script, tuple(params or []))
        conn.commit()
        return int(cur.lastrowid)


def execute_many(script: str, params_seq: list[tuple[Any, ...]]) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.executemany(script, params_seq)
        conn.commit()


def query_all(script: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    with get_conn(row_factory=True) as conn:
        cur = conn.cursor()
        cur.execute(script, tuple(params or []))
        return cur.fetchall()


def query_one(script: str, params: Iterable[Any] | None = None) -> dict[str, Any] | None:
    rows = query_all(script, params)
    return rows[0] if rows else None
