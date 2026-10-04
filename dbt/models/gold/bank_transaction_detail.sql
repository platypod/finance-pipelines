{# Detail view for the dedicated finance Grafana: the operations with their classification, plus a review flag.
   needs_review = nothing decided it (no rule, no override, not a paired transfer): uncategorized debits and the
   default transfers to/from other people, which are excluded from spend and income until someone says what they are.
   Plain credits that fall to income/other_income are a default too, but harmless: not flagged. #}
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='txn_id', on_schema_change='fail', full_refresh=false) }}

select
  t.txn_id, t.account, t.person, t.visibility as owner, t.booking_date, t.spend_date, t.amount,
  t.label_clean as label, t.family, c.category, c.subcategory, c.necessity, c.source, c.rule_id,
  (c.source = 'default' and not (c.category = 'income' and c.subcategory = 'other_income')) as needs_review
from {{ ref('bank_transaction') }} t
join {{ ref('bank_transaction_category') }} c using (txn_id)
