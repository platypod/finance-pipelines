-- GENERATED from contracts/silver.bank_transaction.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:silver:bank_transaction
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS silver.bank_transaction (
  txn_id text not null primary key,
  account text not null,
  person text not null,
  visibility text not null,
  booking_date date not null,
  value_date date not null,
  spend_date date not null,
  amount numeric(12,2) not null,
  label text not null,
  label_clean text not null,
  family text not null,
  card_last4 text,
  occurrence integer not null
);

COMMENT ON TABLE silver.bank_transaction IS 'Identical operations within a day are kept (occurrence index); overlapping exports collapse to one row.';
COMMENT ON COLUMN silver.bank_transaction.txn_id IS 'Stable id: hash of account, dates, label, amount and occurrence.';
COMMENT ON COLUMN silver.bank_transaction.account IS 'Account alias.';
COMMENT ON COLUMN silver.bank_transaction.person IS 'Whose account (login or joint).';
COMMENT ON COLUMN silver.bank_transaction.visibility IS 'Who may see it (login or group:<name>).';
COMMENT ON COLUMN silver.bank_transaction.booking_date IS 'Booking date.';
COMMENT ON COLUMN silver.bank_transaction.value_date IS 'Value date.';
COMMENT ON COLUMN silver.bank_transaction.spend_date IS 'Date used for reporting: the purchase date printed on card payments, else the booking date.';
COMMENT ON COLUMN silver.bank_transaction.amount IS 'Signed amount: negative = money out. [classification: restricted]';
COMMENT ON COLUMN silver.bank_transaction.label IS 'Operation label. [classification: restricted]';
COMMENT ON COLUMN silver.bank_transaction.label_clean IS 'Label with card prefix, date and noise removed (what rules match). [classification: restricted]';
COMMENT ON COLUMN silver.bank_transaction.family IS 'card | direct_debit | transfer_in | transfer_out | cash | refund | interest | fees | payment | other.';
COMMENT ON COLUMN silver.bank_transaction.card_last4 IS 'Last 4 digits of the card used.';
COMMENT ON COLUMN silver.bank_transaction.occurrence IS '1-based index among identical operations of the same day.';
