"""End to end against a real Postgres. Needs FINANCE_PG_* (see Makefile `test-integration`)."""

import pytest

from platypod_pipeline import contracts, db
from platypod_pipeline.config import Settings
from platypod_pipeline.migrate import migrate
from platypod_pipeline.pipelines import heartbeat
from platypod_pipeline.runner import ContractViolation, pipeline_run
from platypod_pipeline.lineage import Dataset

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def settings():
    s = Settings()
    migrate(s)
    return s


def q(settings, sql, *args):
    with db.connect(settings) as conn:
        return conn.execute(sql, args).fetchall()


def test_heartbeat_runs_end_to_end_and_is_recorded(settings):
    heartbeat.run(settings)
    heartbeat.run(settings)

    runs = q(settings, "select status, rows_written, contract_violations from ops.pipeline_run where job=%s order by started_at desc limit 2", heartbeat.JOB)
    assert runs == [("success", 2, 0), ("success", 2, 0)]

    # dbt-ol's model jobs are nested under the wrapper's run
    nested = q(
        settings,
        "select count(*) from ops.openlineage_event e join ops.pipeline_run r"
        " on e.payload->'run'->'facets'->'parent'->'run'->>'runId' = r.run_id::text"
        " where r.job=%s and e.job_name like 'dbt-run%%'",
        heartbeat.JOB,
    )
    assert nested[0][0] >= 2

    # column lineage reaches the store
    (n,) = q(settings, "select count(*) from ops.openlineage_event where payload::text like '%%columnLineage%%'")[0]
    assert n >= 1


def test_contract_violation_fails_the_run_and_emits_fail_event(settings):
    with db.connect(settings, "admin") as conn:
        conn.execute("insert into silver.heartbeat values (gen_random_uuid(), now(), 'test', -5)")
    try:
        with pytest.raises(ContractViolation) as exc:
            with pipeline_run("test.violation", outputs=[Dataset("silver.heartbeat", "silver.heartbeat")], settings=settings) as run:
                run.check_contract("silver.heartbeat")
        assert any("negative" in (c.name or "") or "lag" in (c.name or "").lower() for c in exc.value.result.failures)
    finally:
        with db.connect(settings, "admin") as conn:
            conn.execute("delete from silver.heartbeat where source='test'")
    (run_id, status) = q(settings, "select run_id, status from ops.pipeline_run where job='test.violation' order by started_at desc limit 1")[0]
    assert status == "failed"
    (fails,) = q(settings, "select count(*) from ops.openlineage_event where run_id=%s and event_type='FAIL'", run_id)[0]
    assert fails == 1
