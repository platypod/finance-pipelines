-- GENERATED from contracts/silver.bank_override.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:silver:bank_override
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS silver.bank_override (
  line_no integer not null primary key,
  txn_id text,
  account text,
  booking_date date,
  amount numeric(12,2),
  label_contains text,
  category text not null,
  subcategory text not null,
  necessity text
);

COMMENT ON TABLE silver.bank_override IS 'One row per override line.';
COMMENT ON COLUMN silver.bank_override.line_no IS 'Line in overrides.csv.';
COMMENT ON COLUMN silver.bank_override.txn_id IS 'Target transaction id.';
COMMENT ON COLUMN silver.bank_override.account IS 'Account alias condition.';
COMMENT ON COLUMN silver.bank_override.booking_date IS 'Booking date condition.';
COMMENT ON COLUMN silver.bank_override.amount IS 'Absolute amount condition.';
COMMENT ON COLUMN silver.bank_override.label_contains IS 'Substring of the label.';
COMMENT ON COLUMN silver.bank_override.category IS 'Category to assign.';
COMMENT ON COLUMN silver.bank_override.subcategory IS 'Subcategory to assign.';
COMMENT ON COLUMN silver.bank_override.necessity IS 'essential | comfort | luxury.';
