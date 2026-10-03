-- GENERATED from contracts/silver.payslip.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:silver:payslip
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS silver.payslip (
  period date not null primary key,
  employer_siret text not null,
  gross_amount numeric(12,2) not null,
  employee_contributions numeric(12,2) not null,
  employer_contributions numeric(12,2),
  net_before_tax numeric(12,2) not null,
  net_social numeric(12,2),
  pas_base numeric(12,2),
  pas_rate numeric(7,4),
  pas_amount numeric(12,2),
  net_paid numeric(12,2) not null,
  taxable_net numeric(12,2),
  employer_cost numeric(12,2),
  total_paid numeric(12,2),
  hours numeric(8,2),
  ytd_gross numeric(12,2),
  ytd_taxable_net numeric(12,2),
  leave_cp_n1_balance numeric(7,2),
  leave_cp_n_balance numeric(7,2),
  leave_rtt_balance numeric(7,2),
  payment_date date,
  layout text not null,
  source text not null,
  source_sha256 text not null
);

COMMENT ON TABLE silver.payslip IS 'Monthly payslip summary (latest file wins per period).';
COMMENT ON COLUMN silver.payslip.period IS 'First day of the pay month.';
COMMENT ON COLUMN silver.payslip.employer_siret IS 'Employer SIRET. [classification: internal]';
COMMENT ON COLUMN silver.payslip.gross_amount IS 'Gross pay. [classification: confidential]';
COMMENT ON COLUMN silver.payslip.employee_contributions IS 'Total employee contributions (cotisations salariales). [classification: confidential]';
COMMENT ON COLUMN silver.payslip.employer_contributions IS 'Total employer contributions. [classification: confidential]';
COMMENT ON COLUMN silver.payslip.net_before_tax IS 'Net pay before income tax. [classification: confidential]';
COMMENT ON COLUMN silver.payslip.net_social IS 'Net social amount (printed from 2024). [classification: confidential]';
COMMENT ON COLUMN silver.payslip.pas_base IS 'Withholding-tax base. [classification: confidential]';
COMMENT ON COLUMN silver.payslip.pas_rate IS 'Withholding-tax rate, percent.';
COMMENT ON COLUMN silver.payslip.pas_amount IS 'Income tax withheld at source (PAS). [classification: confidential]';
COMMENT ON COLUMN silver.payslip.net_paid IS 'Net paid to the bank account. [classification: confidential]';
COMMENT ON COLUMN silver.payslip.taxable_net IS 'Net taxable income of the month. [classification: confidential]';
COMMENT ON COLUMN silver.payslip.employer_cost IS 'Total employer cost (coût global; not printed after 2025-10). [classification: confidential]';
COMMENT ON COLUMN silver.payslip.total_paid IS 'Total paid by the employer. [classification: confidential]';
COMMENT ON COLUMN silver.payslip.hours IS 'Hours worked in the month.';
COMMENT ON COLUMN silver.payslip.ytd_gross IS 'Year-to-date gross as printed. [classification: confidential]';
COMMENT ON COLUMN silver.payslip.ytd_taxable_net IS 'Year-to-date taxable net as printed. [classification: confidential]';
COMMENT ON COLUMN silver.payslip.leave_cp_n1_balance IS 'Paid-leave balance, previous year (days).';
COMMENT ON COLUMN silver.payslip.leave_cp_n_balance IS 'Paid-leave balance, current year (days).';
COMMENT ON COLUMN silver.payslip.leave_rtt_balance IS 'RTT balance (days).';
COMMENT ON COLUMN silver.payslip.payment_date IS 'Payment date.';
COMMENT ON COLUMN silver.payslip.layout IS 'Source layout.';
COMMENT ON COLUMN silver.payslip.source IS 'text | ocr.';
COMMENT ON COLUMN silver.payslip.source_sha256 IS 'File this row was derived from.';
