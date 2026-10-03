-- Pipeline plumbing (not a medallion layer, no contract).
create table if not exists ops.pipeline_run (
  run_id               uuid primary key,
  job                  text        not null,
  status               text        not null check (status in ('running', 'success', 'failed')),
  started_at           timestamptz not null,
  ended_at             timestamptz,
  trace_id             text,
  error                text,
  rows_written         bigint,
  contract_violations  integer
);
create index if not exists pipeline_run_job_started on ops.pipeline_run (job, started_at desc);

-- Every OpenLineage event ever emitted, verbatim. Replayable into any backend.
create table if not exists ops.openlineage_event (
  id            bigserial primary key,
  event_time    timestamptz not null,
  event_type    text,
  run_id        uuid        not null,
  job_namespace text        not null,
  job_name      text        not null,
  payload       jsonb       not null,
  replayed_at   timestamptz
);
create index if not exists openlineage_event_run on ops.openlineage_event (run_id);
create index if not exists openlineage_event_unreplayed on ops.openlineage_event (id) where replayed_at is null;
