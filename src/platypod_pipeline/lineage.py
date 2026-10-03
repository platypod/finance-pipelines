"""OpenLineage emission.

Every event is stored in `ops.openlineage_event` (jsonb, replayable) and, when
`OPENLINEAGE_URL` is set, also POSTed to that backend. Storing first means a
lineage backend can be added later and fed from history; a backend outage never
fails a pipeline.
"""

from __future__ import annotations

import json
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from openlineage.client import OpenLineageClient
from openlineage.client.event_v2 import InputDataset, Job, OutputDataset, Run, RunEvent, RunState
from openlineage.client.facet_v2 import (
    data_quality_assertions_dataset,
    error_message_run,
    job_type_job,
    output_statistics_output_dataset,
    parent_run,
    schema_dataset,
)
from openlineage.client.serde import Serde
from openlineage.client.transport import Transport

from . import contracts, db
from .config import Settings

log = logging.getLogger(__name__)
PRODUCER = "https://github.com/platypod/finance-pipelines"


class PostgresTransport(Transport):
    """Appends serialized events to ops.openlineage_event."""

    kind = "postgres"
    name = "ops.openlineage_event"

    def __init__(self, settings: Settings):
        self._settings = settings

    def emit(self, event) -> None:
        store_event(self._settings, json.loads(Serde.to_json(event)))


def store_event(settings: Settings, payload: dict) -> None:
    with db.connect(settings) as conn:
        conn.execute(
            "insert into ops.openlineage_event (event_time, event_type, run_id, job_namespace, job_name, payload)"
            " values (%s, %s, %s, %s, %s, %s::jsonb)",
            (
                payload["eventTime"],
                payload.get("eventType"),
                payload["run"]["runId"],
                payload["job"]["namespace"],
                payload["job"]["name"],
                json.dumps(payload),
            ),
        )


@dataclass
class Dataset:
    """A pipeline input/output. `name` is schema-qualified: `silver.heartbeat`."""

    name: str
    contract: str | None = None  # dataset name of its contract, when it has one
    namespace: str | None = None  # non-Postgres datasets (e.g. "nfs://host"); `name` is then used verbatim


@dataclass
class Emitter:
    settings: Settings
    job_name: str
    run_id: UUID
    inputs: list[Dataset] = field(default_factory=list)
    outputs: list[Dataset] = field(default_factory=list)
    parent: dict | None = None  # {"run_id": ..., "job": ...}
    _clients: list[OpenLineageClient] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._clients = [OpenLineageClient(transport=PostgresTransport(self.settings))]
        if self.settings.ol_url:
            self._clients.append(OpenLineageClient(url=self.settings.ol_url))

    # -- dataset construction -------------------------------------------------
    def _ns(self) -> str:
        return self.settings.pg_namespace

    def _facets(self, ds: Dataset) -> dict:
        facets = {}
        if ds.contract:
            fields = contracts.schema_fields(contracts.contract_path(self.settings, ds.contract))
            facets["schema"] = schema_dataset.SchemaDatasetFacet(
                fields=[schema_dataset.SchemaDatasetFacetFields(name=f["name"], type=f["type"]) for f in fields]
            )
        return facets

    def _ref(self, d: Dataset) -> tuple[str, str]:
        return (d.namespace, d.name) if d.namespace else (self._ns(), self.settings.dataset_name(d.name))

    def _inputs(self) -> list[InputDataset]:
        return [InputDataset(*self._ref(d), facets=self._facets(d)) for d in self.inputs]

    def _outputs(
        self, rows: dict[str, int] | None = None, results: dict[str, contracts.ContractResult] | None = None
    ) -> list[OutputDataset]:
        out = []
        for d in self.outputs:
            facets = self._facets(d)
            if rows and d.name in rows:
                facets["outputStatistics"] = output_statistics_output_dataset.OutputStatisticsOutputDatasetFacet(
                    rowCount=rows[d.name]
                )
            result = (results or {}).get(d.contract or d.name)
            if result:
                facets["dataQualityAssertions"] = data_quality_assertions_dataset.DataQualityAssertionsDatasetFacet(
                    assertions=[
                        data_quality_assertions_dataset.Assertion(
                            assertion=c.name, success=c.passed, column=c.field
                        )
                        for c in result.checks
                    ]
                )
            out.append(OutputDataset(*self._ref(d), facets=facets))
        return out

    # -- events -----------------------------------------------------------------
    def _event(self, state: RunState, *, run_facets: dict | None = None, **datasets) -> RunEvent:
        facets = dict(run_facets or {})
        if self.parent:
            facets["parent"] = parent_run.ParentRunFacet(
                run=parent_run.Run(runId=str(self.parent["run_id"])),
                job=parent_run.Job(namespace=self.settings.ol_namespace, name=self.parent["job"]),
            )
        return RunEvent(
            eventType=state,
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=Run(runId=str(self.run_id), facets=facets),
            job=Job(
                namespace=self.settings.ol_namespace,
                name=self.job_name,
                facets={
                    "jobType": job_type_job.JobTypeJobFacet(
                        processingType="BATCH", integration="PLATYPOD", jobType="PIPELINE"
                    )
                },
            ),
            producer=PRODUCER,
            **datasets,
        )

    def _emit(self, event: RunEvent) -> None:
        for client in self._clients:
            try:
                client.emit(event)
            except Exception:  # noqa: BLE001 - lineage must never fail a pipeline
                log.warning("OpenLineage emit failed via %s", client.transport, exc_info=True)

    def start(self) -> None:
        self._emit(self._event(RunState.START, inputs=self._inputs(), outputs=self._outputs()))

    def complete(self, rows: dict[str, int], results: dict[str, contracts.ContractResult]) -> None:
        self._emit(
            self._event(RunState.COMPLETE, inputs=self._inputs(), outputs=self._outputs(rows, results))
        )

    def fail(self, error: BaseException, results: dict[str, contracts.ContractResult]) -> None:
        run_facets = {
            "errorMessage": error_message_run.ErrorMessageRunFacet(
                message=str(error)[:2000],
                programmingLanguage="python",
                stackTrace="".join(traceback.format_exception(error))[-8000:],
            )
        }
        self._emit(
            self._event(
                RunState.FAIL, run_facets=run_facets, inputs=self._inputs(), outputs=self._outputs(None, results)
            )
        )

    def close(self) -> None:
        for client in self._clients:
            try:
                client.transport.close(5)
            except Exception:  # noqa: BLE001
                pass
