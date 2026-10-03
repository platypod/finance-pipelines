-- GENERATED from contracts/bronze.heartbeat_raw.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:bronze:heartbeat_raw
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS bronze.heartbeat_raw (
  beat_id uuid not null primary key,
  beat_at timestamptz not null,
  source text not null,
  _run_id uuid not null,
  _ingested_at timestamptz not null
);

COMMENT ON TABLE bronze.heartbeat_raw IS 'One row per heartbeat as emitted by the ingest step, untouched.';
COMMENT ON COLUMN bronze.heartbeat_raw.beat_id IS 'Unique id of the beat.';
COMMENT ON COLUMN bronze.heartbeat_raw.beat_at IS 'When the beat was produced.';
COMMENT ON COLUMN bronze.heartbeat_raw.source IS 'Emitting job.';
COMMENT ON COLUMN bronze.heartbeat_raw._run_id IS 'Pipeline run that ingested the row (lineage column).';
COMMENT ON COLUMN bronze.heartbeat_raw._ingested_at IS 'When the row landed in bronze (lineage column).';
