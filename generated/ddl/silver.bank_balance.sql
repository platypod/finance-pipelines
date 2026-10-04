-- GENERATED from contracts/silver.bank_balance.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:silver:bank_balance
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS silver.bank_balance (
  account text not null,
  as_of date not null,
  balance numeric(14,2) not null,
  source_sha256 text not null,
  CONSTRAINT pk_bank_balance PRIMARY KEY (account, as_of)
);

COMMENT ON TABLE silver.bank_balance IS 'One row per account and export date.';
COMMENT ON COLUMN silver.bank_balance.account IS 'Account alias.';
COMMENT ON COLUMN silver.bank_balance.as_of IS 'Date of the balance.';
COMMENT ON COLUMN silver.bank_balance.balance IS 'Balance on that date. [classification: confidential]';
COMMENT ON COLUMN silver.bank_balance.source_sha256 IS 'Export it came from.';
