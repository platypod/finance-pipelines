-- GENERATED from contracts/gold.bank_measure.odcs.yaml by `pp generate`. Do not edit.

-- Data Contract: urn:platypod:finance:gold:bank_measure
-- SQL Dialect: postgres
CREATE TABLE IF NOT EXISTS gold.bank_measure (
  period date not null,
  measure text not null,
  person text not null,
  owner text not null,
  item1 text not null,
  item2 text not null,
  value numeric(14,2),
  ytd_value numeric(14,2),
  r12_value numeric(14,2),
  CONSTRAINT pk_bank_measure PRIMARY KEY (period, measure, person, owner, item1, item2)
);

COMMENT ON TABLE gold.bank_measure IS 'One row per month, measure, person, owner, item1 and item2. Dense for spend/income categories (zero months are rows).';
COMMENT ON COLUMN gold.bank_measure.period IS 'First day of the month (by spend date).';
COMMENT ON COLUMN gold.bank_measure.measure IS 'spend | income | spend_necessity | balance.';
COMMENT ON COLUMN gold.bank_measure.person IS 'Whose figures (login or joint).';
COMMENT ON COLUMN gold.bank_measure.owner IS 'Visibility principal: the metrics'' owner label (login or group:<name>).';
COMMENT ON COLUMN gold.bank_measure.item1 IS 'spend/income: category; spend_necessity: necessity; balance: account alias.';
COMMENT ON COLUMN gold.bank_measure.item2 IS 'spend/income: subcategory; otherwise ''''.';
COMMENT ON COLUMN gold.bank_measure.value IS 'Amount for the month (spend: money out net of refunds, positive; balance: month-end). [classification: confidential]';
COMMENT ON COLUMN gold.bank_measure.ytd_value IS 'Calendar year to date. NULL for balances. [classification: confidential]';
COMMENT ON COLUMN gold.bank_measure.r12_value IS 'Rolling 12 months. NULL until 12 months exist, and for balances. [classification: confidential]';
