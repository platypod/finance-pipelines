-- GENERATED from contracts/bronze.bank_file.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:bronze:bank_file
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS bronze.bank_file (
  sha256 text not null primary key,
  source_path text not null,
  size_bytes bigint not null,
  file_mtime timestamptz not null,
  bank text not null,
  exported_on date,
  parser_version text not null,
  status text not null,
  warnings jsonb not null,
  accounts jsonb not null,
  _ingested_at timestamptz not null,
  _run_id uuid not null
);

COMMENT ON TABLE bronze.bank_file IS 'One row per distinct file content (sha256).';
COMMENT ON COLUMN bronze.bank_file.sha256 IS 'SHA-256 of the file content (idempotency key).';
COMMENT ON COLUMN bronze.bank_file.source_path IS 'Path relative to the statements directory. [classification: internal]';
COMMENT ON COLUMN bronze.bank_file.size_bytes IS 'File size.';
COMMENT ON COLUMN bronze.bank_file.file_mtime IS 'File modification time.';
COMMENT ON COLUMN bronze.bank_file.bank IS 'Detected bank: ca | unknown.';
COMMENT ON COLUMN bronze.bank_file.exported_on IS 'Download date printed in the export.';
COMMENT ON COLUMN bronze.bank_file.parser_version IS 'Version of the parser that produced the rows.';
COMMENT ON COLUMN bronze.bank_file.status IS 'parsed | review (warnings) | unsupported (not a known export).';
COMMENT ON COLUMN bronze.bank_file.warnings IS 'Parser warnings.';
COMMENT ON COLUMN bronze.bank_file.accounts IS 'Per account: kind, last4, balance, balance_date, period, row count. [classification: restricted]';
COMMENT ON COLUMN bronze.bank_file._ingested_at IS 'When the row landed in bronze (lineage column).';
COMMENT ON COLUMN bronze.bank_file._run_id IS 'Pipeline run that ingested the row (lineage column).';
