from __future__ import annotations

import psycopg

from .config import Settings


def connect(settings: Settings, role: str | None = None, *, autocommit: bool = True) -> psycopg.Connection:
    return psycopg.connect(settings.dsn(role), autocommit=autocommit)
