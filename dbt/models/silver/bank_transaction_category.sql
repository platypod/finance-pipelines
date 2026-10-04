{# Classification, strongest first: an override you wrote, a paired transfer between your own accounts, the
   first matching rule (private rules before generic ones), then a default. Every row says which one decided. #}
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='txn_id', on_schema_change='fail', full_refresh=false) }}

with t as (select * from {{ ref('bank_transaction') }}),
pairs as (  -- money out of one own account, same amount into another within 3 days; one-to-one on both sides
  select o.txn_id as out_id, i.txn_id as in_id,
         row_number() over (partition by o.txn_id order by abs(o.booking_date - i.booking_date), i.txn_id) as rn_out,
         row_number() over (partition by i.txn_id order by abs(o.booking_date - i.booking_date), o.txn_id) as rn_in
  from t o
  join t i on o.account <> i.account and o.family = 'transfer_out' and i.family = 'transfer_in'
          and o.amount < 0 and i.amount = -o.amount and abs(o.booking_date - i.booking_date) <= 3
),
internal as (
  select out_id as txn_id from pairs where rn_out = 1 and rn_in = 1
  union all
  select in_id from pairs where rn_out = 1 and rn_in = 1
),
ov as (  -- the last matching line of overrides.csv wins
  select distinct on (t.txn_id) t.txn_id, o.category, o.subcategory, o.necessity
  from t join {{ source('silver', 'bank_override') }} o
    on (o.txn_id is null or o.txn_id = t.txn_id)
   and (o.account is null or o.account = t.account)
   and (o.booking_date is null or o.booking_date = t.booking_date)
   and (o.amount is null or o.amount = abs(t.amount))
   and (o.label_contains is null or t.label ilike '%' || o.label_contains || '%')
  order by t.txn_id, o.line_no desc
),
ruled as (
  select t.txn_id, m.rule_id, m.category, m.subcategory, m.necessity
  from t
  left join lateral (
    select r.rule_id, r.category, r.subcategory, r.necessity
    from {{ source('silver', 'bank_rule') }} r
    where (r.family is null or r.family = t.family)
      and (r.direction is null or r.direction = case when t.amount < 0 then 'debit' else 'credit' end)
      and (r.label_regex is null or t.label_clean ~* r.label_regex or t.label ~* r.label_regex)
      and (r.amount_min is null or abs(t.amount) >= r.amount_min)
      and (r.amount_max is null or abs(t.amount) <= r.amount_max)
      and (r.account is null or r.account = t.account)
    order by r.priority
    limit 1
  ) m on true
)
select
  t.txn_id,
  case when ov.txn_id is not null then ov.category
       when i.txn_id is not null then 'transfers'
       when ruled.rule_id is not null then ruled.category
       when t.family in ('transfer_in', 'transfer_out') then 'transfers'
       when t.amount > 0 then 'income'
       else 'uncategorized' end as category,
  case when ov.txn_id is not null then ov.subcategory
       when i.txn_id is not null then 'internal'
       when ruled.rule_id is not null then ruled.subcategory
       when t.family = 'transfer_in' then 'from_others'
       when t.family = 'transfer_out' then 'to_others'
       when t.amount > 0 then 'other_income'
       else 'uncategorized' end as subcategory,
  case when ov.txn_id is not null then ov.necessity
       when i.txn_id is not null then null
       else ruled.necessity end as necessity,
  case when ov.txn_id is not null then 'override'
       when i.txn_id is not null then 'transfer_pair'
       when ruled.rule_id is not null then 'rule'
       else 'default' end as source,
  case when ov.txn_id is null and i.txn_id is null then ruled.rule_id end as rule_id
from t
left join ov on ov.txn_id = t.txn_id
left join (select distinct txn_id from internal) i on i.txn_id = t.txn_id
left join ruled on ruled.txn_id = t.txn_id
