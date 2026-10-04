-- GENERATED from contracts/gold.bank_transaction_detail.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:gold:bank_transaction_detail
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS gold.bank_transaction_detail (
  txn_id text not null primary key,
  account text not null,
  person text not null,
  owner text not null,
  booking_date date not null,
  spend_date date not null,
  amount numeric(12,2) not null,
  label text not null,
  family text not null,
  category text not null,
  subcategory text not null,
  necessity text,
  source text not null,
  rule_id text,
  needs_review boolean not null
);

COMMENT ON TABLE gold.bank_transaction_detail IS 'One row per de-duplicated operation (same key as silver.bank_transaction).';
COMMENT ON COLUMN gold.bank_transaction_detail.txn_id IS 'Transaction (primary key).';
COMMENT ON COLUMN gold.bank_transaction_detail.account IS 'Account alias.';
COMMENT ON COLUMN gold.bank_transaction_detail.person IS 'Whose account (login or joint).';
COMMENT ON COLUMN gold.bank_transaction_detail.owner IS 'Who may see it (login or group:<name>).';
COMMENT ON COLUMN gold.bank_transaction_detail.booking_date IS 'Booking date.';
COMMENT ON COLUMN gold.bank_transaction_detail.spend_date IS 'Reporting date: the purchase date on card payments, else the booking date.';
COMMENT ON COLUMN gold.bank_transaction_detail.amount IS 'Signed amount: negative = money out. [classification: restricted]';
COMMENT ON COLUMN gold.bank_transaction_detail.label IS 'Cleaned operation label. [classification: restricted]';
COMMENT ON COLUMN gold.bank_transaction_detail.family IS 'card | direct_debit | transfer_in | transfer_out | cash | refund | interest | fees | payment | other.';
COMMENT ON COLUMN gold.bank_transaction_detail.category IS 'Category (taxonomy).';
COMMENT ON COLUMN gold.bank_transaction_detail.subcategory IS 'Subcategory (taxonomy).';
COMMENT ON COLUMN gold.bank_transaction_detail.necessity IS 'essential | comfort | luxury.';
COMMENT ON COLUMN gold.bank_transaction_detail.source IS 'override | transfer_pair | rule | default.';
COMMENT ON COLUMN gold.bank_transaction_detail.rule_id IS 'Rule that matched.';
COMMENT ON COLUMN gold.bank_transaction_detail.needs_review IS 'True when no rule or override decided it: uncategorized, or a default transfer to/from another person.';
