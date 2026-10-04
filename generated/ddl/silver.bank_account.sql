-- GENERATED from contracts/silver.bank_account.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:silver:bank_account
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS silver.bank_account (
  alias text not null primary key,
  bank text not null,
  last4 text not null,
  kind text not null,
  person text not null,
  holders text,
  visibility text not null
);

COMMENT ON TABLE silver.bank_account IS 'One row per mapped account.';
COMMENT ON COLUMN silver.bank_account.alias IS 'Account alias (shown in dashboards).';
COMMENT ON COLUMN silver.bank_account.bank IS 'Bank code (ca).';
COMMENT ON COLUMN silver.bank_account.last4 IS 'Last 4 digits of the account number.';
COMMENT ON COLUMN silver.bank_account.kind IS 'current | savings.';
COMMENT ON COLUMN silver.bank_account.person IS 'Whose account it is: a login, or ''joint''. The dashboards'' person filter.';
COMMENT ON COLUMN silver.bank_account.holders IS 'Comma-separated holders (documentation).';
COMMENT ON COLUMN silver.bank_account.visibility IS 'Who may see this account''s figures: a login or group:<name> (becomes the metrics'' owner label).';
