-- GENERATED from contracts/silver.bank_transaction_category.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:silver:bank_transaction_category
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS silver.bank_transaction_category (
  txn_id text not null primary key,
  category text not null,
  subcategory text not null,
  necessity text,
  source text not null,
  rule_id text
);

COMMENT ON TABLE silver.bank_transaction_category IS 'One row per transaction.';
COMMENT ON COLUMN silver.bank_transaction_category.txn_id IS 'Transaction.';
COMMENT ON COLUMN silver.bank_transaction_category.category IS 'Category (taxonomy).';
COMMENT ON COLUMN silver.bank_transaction_category.subcategory IS 'Subcategory (taxonomy).';
COMMENT ON COLUMN silver.bank_transaction_category.necessity IS 'essential | comfort | luxury.';
COMMENT ON COLUMN silver.bank_transaction_category.source IS 'override | transfer_pair | rule | default.';
COMMENT ON COLUMN silver.bank_transaction_category.rule_id IS 'Rule that matched.';
