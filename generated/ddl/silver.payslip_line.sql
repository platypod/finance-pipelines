-- GENERATED from contracts/silver.payslip_line.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:silver:payslip_line
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS silver.payslip_line (
  period date not null,
  line_no integer not null,
  section text not null,
  label text not null,
  category text not null,
  base numeric(12,2),
  rate numeric(10,4),
  employee_gain numeric(12,2),
  employee_deduction numeric(12,2),
  employer_base numeric(12,2),
  employer_rate numeric(10,4),
  employer_amount numeric(12,2),
  source_sha256 text not null,
  CONSTRAINT pk_payslip_line PRIMARY KEY (period, line_no)
);

COMMENT ON TABLE silver.payslip_line IS 'Typed table rows, classified by category.';
COMMENT ON COLUMN silver.payslip_line.period IS 'Pay month.';
COMMENT ON COLUMN silver.payslip_line.line_no IS 'Row order within the payslip.';
COMMENT ON COLUMN silver.payslip_line.section IS 'brut | cotisations | other.';
COMMENT ON COLUMN silver.payslip_line.label IS 'Printed label.';
COMMENT ON COLUMN silver.payslip_line.category IS 'Gross section: base_salary | bonus | time_off (leave, RTT, absences, sick pay) | back_pay | other_pay. Net side: bonus_exempt (value-sharing bonus, printed outside the gross) | health | provident | work_accident | retirement | family | unemployment | csg_crds | meal_vouchers | other_contributions | other.';
COMMENT ON COLUMN silver.payslip_line.base IS 'Base amount. [classification: confidential]';
COMMENT ON COLUMN silver.payslip_line.rate IS 'Rate, percent.';
COMMENT ON COLUMN silver.payslip_line.employee_gain IS 'Employee-side gain (pay element). [classification: confidential]';
COMMENT ON COLUMN silver.payslip_line.employee_deduction IS 'Employee-side deduction. [classification: confidential]';
COMMENT ON COLUMN silver.payslip_line.employer_base IS 'Employer base. [classification: confidential]';
COMMENT ON COLUMN silver.payslip_line.employer_rate IS 'Employer rate, percent.';
COMMENT ON COLUMN silver.payslip_line.employer_amount IS 'Employer-side amount. [classification: confidential]';
COMMENT ON COLUMN silver.payslip_line.source_sha256 IS 'File this row was derived from.';
