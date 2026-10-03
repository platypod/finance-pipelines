-- GENERATED from contracts/bronze.payslip_file.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:bronze:payslip_file
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS bronze.payslip_file (
  sha256 text not null primary key,
  source_path text not null,
  size_bytes bigint not null,
  file_mtime timestamptz not null,
  period date not null,
  layout text not null,
  source text not null,
  parser_version text not null,
  status text not null,
  warnings jsonb not null,
  summary jsonb not null,
  _ingested_at timestamptz not null,
  _run_id uuid not null
);

COMMENT ON TABLE bronze.payslip_file IS 'One row per distinct file content (sha256).';
COMMENT ON COLUMN bronze.payslip_file.sha256 IS 'SHA-256 of the file content (idempotency key).';
COMMENT ON COLUMN bronze.payslip_file.source_path IS 'Path relative to the payslip root. [classification: internal]';
COMMENT ON COLUMN bronze.payslip_file.size_bytes IS 'File size.';
COMMENT ON COLUMN bronze.payslip_file.file_mtime IS 'File modification time.';
COMMENT ON COLUMN bronze.payslip_file.period IS 'Pay month (first day), from the file name.';
COMMENT ON COLUMN bronze.payslip_file.layout IS 'Detected layout: silae | modern | unknown.';
COMMENT ON COLUMN bronze.payslip_file.source IS 'How the text was obtained: text | ocr.';
COMMENT ON COLUMN bronze.payslip_file.parser_version IS 'Version of the parser that produced `summary`.';
COMMENT ON COLUMN bronze.payslip_file.status IS 'parsed (all arithmetic checks pass) | review (checks failed) | unsupported (no known layout).';
COMMENT ON COLUMN bronze.payslip_file.warnings IS 'Parser/consistency warnings.';
COMMENT ON COLUMN bronze.payslip_file.summary IS 'Raw summary fields exactly as printed (strings), canonical keys. [classification: confidential]';
COMMENT ON COLUMN bronze.payslip_file._ingested_at IS 'When the row landed in bronze (lineage column).';
COMMENT ON COLUMN bronze.payslip_file._run_id IS 'Pipeline run that ingested the row (lineage column).';
