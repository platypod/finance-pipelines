-- GENERATED from contracts/bronze.bank_transaction_raw.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:bronze:bank_transaction_raw
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS bronze.bank_transaction_raw (
  sha256 text not null,
  account_ref text not null,
  line_no integer not null,
  booking_date text not null,
  value_date text not null,
  label text not null,
  debit text,
  credit text,
  _ingested_at timestamptz not null,
  _run_id uuid not null,
  CONSTRAINT pk_bank_transaction_raw PRIMARY KEY (sha256, account_ref, line_no)
);

COMMENT ON TABLE bronze.bank_transaction_raw IS 'One row per printed operation; values are raw strings.';
COMMENT ON COLUMN bronze.bank_transaction_raw.sha256 IS 'Parent file.';
COMMENT ON COLUMN bronze.bank_transaction_raw.account_ref IS 'Last 4 digits of the account number.';
COMMENT ON COLUMN bronze.bank_transaction_raw.line_no IS 'Row order within the account''s table.';
COMMENT ON COLUMN bronze.bank_transaction_raw.booking_date IS 'Booking date as printed (dd/mm/yyyy).';
COMMENT ON COLUMN bronze.bank_transaction_raw.value_date IS 'Value date as printed.';
COMMENT ON COLUMN bronze.bank_transaction_raw.label IS 'Operation label (multi-line in the export, whitespace collapsed). [classification: restricted]';
COMMENT ON COLUMN bronze.bank_transaction_raw.debit IS 'Debit amount as printed, or empty. [classification: restricted]';
COMMENT ON COLUMN bronze.bank_transaction_raw.credit IS 'Credit amount as printed, or empty. [classification: restricted]';
COMMENT ON COLUMN bronze.bank_transaction_raw._ingested_at IS 'When the row landed in bronze (lineage column).';
COMMENT ON COLUMN bronze.bank_transaction_raw._run_id IS 'Pipeline run that ingested the row (lineage column).';
