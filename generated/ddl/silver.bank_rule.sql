-- GENERATED from contracts/silver.bank_rule.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:silver:bank_rule
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS silver.bank_rule (
  priority integer not null primary key,
  rule_id text not null,
  family text,
  direction text,
  label_regex text,
  amount_min numeric(12,2),
  amount_max numeric(12,2),
  account text,
  category text not null,
  subcategory text not null,
  necessity text,
  origin text not null
);

COMMENT ON TABLE silver.bank_rule IS 'One row per rule; priority is the evaluation order.';
COMMENT ON COLUMN silver.bank_rule.priority IS 'Evaluation order (1 = first).';
COMMENT ON COLUMN silver.bank_rule.rule_id IS 'Rule id.';
COMMENT ON COLUMN silver.bank_rule.family IS 'Operation family condition.';
COMMENT ON COLUMN silver.bank_rule.direction IS 'debit | credit condition.';
COMMENT ON COLUMN silver.bank_rule.label_regex IS 'PostgreSQL regex condition on the cleaned label.';
COMMENT ON COLUMN silver.bank_rule.amount_min IS 'Minimum absolute amount.';
COMMENT ON COLUMN silver.bank_rule.amount_max IS 'Maximum absolute amount.';
COMMENT ON COLUMN silver.bank_rule.account IS 'Account alias condition.';
COMMENT ON COLUMN silver.bank_rule.category IS 'Category to assign.';
COMMENT ON COLUMN silver.bank_rule.subcategory IS 'Subcategory to assign.';
COMMENT ON COLUMN silver.bank_rule.necessity IS 'essential | comfort | luxury.';
COMMENT ON COLUMN silver.bank_rule.origin IS 'private | default.';
