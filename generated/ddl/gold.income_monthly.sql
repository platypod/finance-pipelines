-- GENERATED from contracts/gold.income_monthly.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:gold:income_monthly
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS gold.income_monthly (
  period date not null primary key,
  year integer not null,
  gross_amount numeric(12,2) not null,
  net_before_tax numeric(12,2) not null,
  net_paid numeric(12,2) not null,
  pas_amount numeric(12,2) not null,
  pas_rate numeric(7,4),
  employee_contributions numeric(12,2) not null,
  employer_contributions numeric(12,2),
  employer_cost numeric(12,2),
  taxable_net numeric(12,2),
  ytd_gross numeric(12,2) not null,
  ytd_net_paid numeric(12,2) not null,
  ytd_pas numeric(12,2) not null,
  net_to_gross numeric(7,4) not null,
  contributions_to_gross numeric(7,4) not null,
  leave_cp_balance numeric(7,2),
  leave_rtt_balance numeric(7,2)
);

COMMENT ON TABLE gold.income_monthly IS 'One row per month, with running year-to-date figures computed from the months themselves.';
COMMENT ON COLUMN gold.income_monthly.period IS 'First day of the pay month.';
COMMENT ON COLUMN gold.income_monthly.year IS 'Calendar year.';
COMMENT ON COLUMN gold.income_monthly.gross_amount IS 'Gross pay. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.net_before_tax IS 'Net before income tax. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.net_paid IS 'Net paid. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.pas_amount IS 'Income tax withheld. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.pas_rate IS 'Withholding rate, percent.';
COMMENT ON COLUMN gold.income_monthly.employee_contributions IS 'Employee contributions. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.employer_contributions IS 'Employer contributions. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.employer_cost IS 'Employer cost. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.taxable_net IS 'Net taxable. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.ytd_gross IS 'Gross, year to date (sum of months). [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.ytd_net_paid IS 'Net paid, year to date. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.ytd_pas IS 'Tax withheld, year to date. [classification: confidential]';
COMMENT ON COLUMN gold.income_monthly.net_to_gross IS 'net_paid / gross_amount.';
COMMENT ON COLUMN gold.income_monthly.contributions_to_gross IS 'employee_contributions / gross_amount.';
COMMENT ON COLUMN gold.income_monthly.leave_cp_balance IS 'Paid-leave balance (previous + current year, days).';
COMMENT ON COLUMN gold.income_monthly.leave_rtt_balance IS 'RTT balance (days).';
