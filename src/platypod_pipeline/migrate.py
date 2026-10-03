"""Apply schema migrations and contract-generated DDL, in a fixed order.

migrations/*.sql   hand-written plumbing (schemas, grants, ops tables)
generated/ddl/*.sql  one file per contract, bronze -> silver -> gold

All statements are idempotent (IF NOT EXISTS). Evolving an existing table is NOT
automatic yet: a changed contract shows up as schema drift in `datacontract test`
and needs an explicit migration (phase-0 limitation).
"""

from __future__ import annotations

import logging

from . import db
from .config import Settings

log = logging.getLogger(__name__)
LAYER_ORDER = {"bronze": 0, "silver": 1, "gold": 2}


def _ddl_files(settings: Settings):
    return sorted(
        settings.ddl_dir.glob("*.sql"),
        key=lambda p: (LAYER_ORDER.get(p.name.split(".")[0], 9), p.name),
    )


def migrate(settings: Settings) -> list[str]:
    applied = []
    with db.connect(settings, "admin") as conn:
        for path in [*sorted(settings.migrations_dir.glob("*.sql")), *_ddl_files(settings)]:
            conn.execute(path.read_text())
            applied.append(path.name)
            log.info("applied %s", path.name)
    return applied
