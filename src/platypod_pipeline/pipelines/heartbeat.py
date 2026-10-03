"""Canary pipeline: ingest -> dbt (bronze -> silver) -> contract tests.

Carries no finance data. It exercises every moving part of the platform
(wrapper, telemetry, lineage, dbt, contracts) and doubles as a freshness probe.
"""

from __future__ import annotations

from uuid import uuid4

from .. import db
from ..config import Settings
from ..dbt import run_dbt
from ..lineage import Dataset
from ..runner import pipeline_run

JOB = "platform.heartbeat"


def run(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    with pipeline_run(
        JOB,
        outputs=[Dataset("bronze.heartbeat_raw", "bronze.heartbeat_raw"), Dataset("silver.heartbeat", "silver.heartbeat")],
        settings=settings,
    ) as run:
        with run.step("ingest"):
            with db.connect(settings, "ingest") as conn:
                # Both timestamps come from the database clock: a client/container clock skew
                # would otherwise produce negative lags (and a spurious contract violation).
                conn.execute(
                    "insert into bronze.heartbeat_raw (beat_id, beat_at, source, _run_id, _ingested_at)"
                    " values (%s, now(), %s, %s, clock_timestamp())",
                    (uuid4(), JOB, run.run_id),
                )
            run.add_rows("bronze.heartbeat_raw", 1)
        with run.step("transform"):
            run_dbt(run, "build", select="heartbeat")
            run.add_rows("silver.heartbeat", 1)  # one beat per run reaches silver
        with run.step("contract"):
            run.check_contract("bronze.heartbeat_raw")
            run.check_contract("silver.heartbeat")
