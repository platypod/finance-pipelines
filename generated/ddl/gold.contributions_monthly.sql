-- GENERATED from contracts/gold.contributions_monthly.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:gold:contributions_monthly
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS gold.contributions_monthly (
  period date not null,
  category text not null,
  employee_amount numeric(12,2) not null,
  employer_amount numeric(12,2) not null,
  CONSTRAINT pk_contributions_monthly PRIMARY KEY (period, category)
);

COMMENT ON TABLE gold.contributions_monthly IS 'One row per month and category.';
COMMENT ON COLUMN gold.contributions_monthly.period IS 'First day of the pay month.';
COMMENT ON COLUMN gold.contributions_monthly.category IS 'Contribution category (see silver.payslip_line).';
COMMENT ON COLUMN gold.contributions_monthly.employee_amount IS 'Employee-side deductions in the category. [classification: confidential]';
COMMENT ON COLUMN gold.contributions_monthly.employer_amount IS 'Employer-side amounts in the category. [classification: confidential]';
