-- GENERATED from contracts/gold.payslip_measure.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:gold:payslip_measure
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS gold.payslip_measure (
  period date not null,
  measure text not null,
  item text not null,
  side text not null,
  value numeric(12,2),
  ytd_value numeric(12,2),
  r12_value numeric(12,2),
  CONSTRAINT pk_payslip_measure PRIMARY KEY (period, measure, item, side)
);

COMMENT ON TABLE gold.payslip_measure IS 'One row per month, measure, item and side. Dense: zero amounts are rows too.';
COMMENT ON COLUMN gold.payslip_measure.period IS 'First day of the pay month.';
COMMENT ON COLUMN gold.payslip_measure.measure IS 'gross | net_before_tax | net_paid | tax_withheld | taxable_net | employee_contributions | employer_contributions | employer_cost | pay_element | contribution.';
COMMENT ON COLUMN gold.payslip_measure.item IS ''''' for plain flows; the pay element (base_salary | bonus | time_off | back_pay | other_pay | bonus_exempt) or the contribution category.';
COMMENT ON COLUMN gold.payslip_measure.side IS ''''' except for contributions: employee | employer.';
COMMENT ON COLUMN gold.payslip_measure.value IS 'The amount for the month. NULL when the payslip does not print it. [classification: confidential]';
COMMENT ON COLUMN gold.payslip_measure.ytd_value IS 'Calendar year to date including this month. NULL if any month so far has no figure. [classification: confidential]';
COMMENT ON COLUMN gold.payslip_measure.r12_value IS 'Rolling 12 months ending this month. NULL until 12 months exist or if any has no figure. [classification: confidential]';
