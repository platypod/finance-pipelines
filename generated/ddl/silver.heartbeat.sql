-- GENERATED from contracts/silver.heartbeat.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:silver:heartbeat
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS silver.heartbeat (
  beat_id uuid not null primary key,
  beat_at timestamptz not null,
  source text not null,
  lag_seconds numeric(12,3) not null
);

COMMENT ON TABLE silver.heartbeat IS 'One row per distinct heartbeat.';
COMMENT ON COLUMN silver.heartbeat.beat_id IS 'Unique id of the beat.';
COMMENT ON COLUMN silver.heartbeat.beat_at IS 'When the beat was produced.';
COMMENT ON COLUMN silver.heartbeat.source IS 'Emitting job.';
COMMENT ON COLUMN silver.heartbeat.lag_seconds IS 'Seconds between production and ingestion.';
