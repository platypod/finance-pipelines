"""`pipeline_run`: the one wrapper every job goes through.

    with pipeline_run("finance.heartbeat", outputs=[Dataset("silver.heartbeat", "silver.heartbeat")]) as run:
        with run.step("ingest"):
            ...
        run.add_rows("silver.heartbeat", n)
        run.check_contract("silver.heartbeat")      # raises ContractViolation

On entry/exit it emits the OTel root span + metrics, the OpenLineage
START/COMPLETE/FAIL events, and the `ops.pipeline_run` row. It does not care
who launched the process (k8s CronJob, Kestra, a shell).
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator
from uuid import UUID, uuid4

from . import contracts, db, telemetry
from .config import Settings
from .lineage import Dataset, Emitter

log = logging.getLogger(__name__)


class ContractViolation(RuntimeError):
    def __init__(self, result: contracts.ContractResult):
        self.result = result
        lines = "; ".join(f"{c.name} ({c.field or '-'}): {c.reason}" for c in result.failures)
        super().__init__(f"contract {result.dataset} violated: {lines}")


@dataclass
class RunContext:
    settings: Settings
    job: str
    run_id: UUID
    emitter: Emitter
    rows: dict[str, int] = field(default_factory=dict)
    results: dict[str, contracts.ContractResult] = field(default_factory=dict)

    @property
    def lineage_parent(self) -> dict:
        """What a child process (e.g. dbt-ol) needs to nest its jobs under this run."""
        return {"run_id": self.run_id, "job": self.job}

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        with telemetry.span(f"{self.job}.{name}", **{"pipeline.step": name}):
            log.info("step %s: start", name)
            started = time.monotonic()
            yield
            log.info("step %s: done in %.2fs", name, time.monotonic() - started)

    def add_rows(self, dataset: str, n: int) -> None:
        self.rows[dataset] = self.rows.get(dataset, 0) + n

    def check_contract(self, dataset: str) -> contracts.ContractResult:
        with telemetry.span(f"contract.{dataset}", **{"contract.dataset": dataset}) as span:
            result = contracts.run_test(self.settings, dataset)
            self.results[dataset] = result
            span.set_attribute("contract.passed", result.passed)
            span.set_attribute("contract.failures", len(result.failures))
        if not result.passed:
            raise ContractViolation(result)
        return result

    @property
    def violations(self) -> int:
        return sum(len(r.failures) for r in self.results.values())


def _upsert_run(settings: Settings, ctx_id: UUID, job: str, **cols) -> None:
    with db.connect(settings) as conn:
        if cols.pop("_insert", False):
            conn.execute(
                "insert into ops.pipeline_run (run_id, job, status, started_at, trace_id)"
                " values (%s, %s, 'running', %s, %s)",
                (ctx_id, job, cols["started_at"], cols["trace_id"]),
            )
        else:
            conn.execute(
                "update ops.pipeline_run set status=%s, ended_at=%s, error=%s, rows_written=%s,"
                " contract_violations=%s where run_id=%s",
                (cols["status"], cols["ended_at"], cols["error"], cols["rows"], cols["violations"], ctx_id),
            )


@contextmanager
def pipeline_run(
    job: str,
    *,
    inputs: list[Dataset] | None = None,
    outputs: list[Dataset] | None = None,
    settings: Settings | None = None,
) -> Iterator[RunContext]:
    settings = settings or Settings()
    telemetry.setup(settings.service_name)
    run_id = uuid4()
    emitter = Emitter(settings, job, run_id, inputs or [], outputs or [])
    ctx = RunContext(settings, job, run_id, emitter)
    started = time.monotonic()
    started_at = datetime.now(timezone.utc)

    # An orchestrator-supplied TRACEPARENT (env) makes this run a child of its trace.
    with telemetry.span(job, context=telemetry.parent_context(), **{"pipeline.run_id": str(run_id)}) as root:
        _upsert_run(settings, run_id, job, _insert=True, started_at=started_at, trace_id=telemetry.trace_id_hex())
        emitter.start()
        log.info("run %s of %s started", run_id, job)
        status, error = "success", None
        try:
            yield ctx
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            status, error = "failed", exc
            root.record_exception(exc)
            emitter.fail(exc, ctx.results)
            raise
        else:
            emitter.complete(ctx.rows, ctx.results)
        finally:
            seconds = time.monotonic() - started
            _upsert_run(
                settings,
                run_id,
                job,
                status=status,
                ended_at=datetime.now(timezone.utc),
                error=str(error)[:2000] if error else None,
                rows=sum(ctx.rows.values()),
                violations=ctx.violations,
            )
            telemetry.record_run(
                job, status=status, seconds=seconds, rows_written=sum(ctx.rows.values()), violations=ctx.violations
            )
            emitter.close()
            log.info("run %s of %s %s in %.2fs", run_id, job, status, seconds)
