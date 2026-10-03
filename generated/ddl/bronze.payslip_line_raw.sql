-- GENERATED from contracts/bronze.payslip_line_raw.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:bronze:payslip_line_raw
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS bronze.payslip_line_raw (
  sha256 text not null,
  line_no integer not null,
  section text not null,
  label text not null,
  base text,
  rate text,
  employee_gain text,
  employee_deduct text,
  employer_base text,
  employer_rate text,
  employer_amount text,
  _ingested_at timestamptz not null,
  _run_id uuid not null,
  CONSTRAINT pk_payslip_line_raw PRIMARY KEY (sha256, line_no)
);

COMMENT ON TABLE bronze.payslip_line_raw IS 'One row per printed table row; values are raw strings.';
COMMENT ON COLUMN bronze.payslip_line_raw.sha256 IS 'Parent file.';
COMMENT ON COLUMN bronze.payslip_line_raw.line_no IS 'Row order within the payslip.';
COMMENT ON COLUMN bronze.payslip_line_raw.section IS 'brut | cotisations | other.';
COMMENT ON COLUMN bronze.payslip_line_raw.label IS 'Printed label.';
COMMENT ON COLUMN bronze.payslip_line_raw.base IS 'Raw `base` value as printed. [classification: confidential]';
COMMENT ON COLUMN bronze.payslip_line_raw.rate IS 'Raw `rate` value as printed. [classification: confidential]';
COMMENT ON COLUMN bronze.payslip_line_raw.employee_gain IS 'Raw `employee_gain` value as printed. [classification: confidential]';
COMMENT ON COLUMN bronze.payslip_line_raw.employee_deduct IS 'Raw `employee_deduct` value as printed. [classification: confidential]';
COMMENT ON COLUMN bronze.payslip_line_raw.employer_base IS 'Raw `employer_base` value as printed. [classification: confidential]';
COMMENT ON COLUMN bronze.payslip_line_raw.employer_rate IS 'Raw `employer_rate` value as printed. [classification: confidential]';
COMMENT ON COLUMN bronze.payslip_line_raw.employer_amount IS 'Raw `employer_amount` value as printed. [classification: confidential]';
COMMENT ON COLUMN bronze.payslip_line_raw._ingested_at IS 'When the row landed in bronze (lineage column).';
COMMENT ON COLUMN bronze.payslip_line_raw._run_id IS 'Pipeline run that ingested the row (lineage column).';
