{# One typed, de-duplicated row per bank operation.
   Exports overlap (rolling ~13-month window), and identical operations really repeat within a day (a vending
   machine, two coffees), so: per file count identical rows, keep the highest count over files, and number the
   copies. The id is a hash of the whole key + that number, hence stable across exports. #}
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='txn_id', on_schema_change='fail', full_refresh=false) }}

with raw as (
  select f.bank, r.sha256, r.account_ref,
         to_date(r.booking_date, 'DD/MM/YYYY') as booking_date,
         to_date(r.value_date, 'DD/MM/YYYY')   as value_date,
         r.label,
         (coalesce({{ fr_num('r.credit') }}, 0) - coalesce({{ fr_num('r.debit') }}, 0))::numeric(12,2) as amount
  from {{ source('bronze', 'bank_transaction_raw') }} r
  join {{ source('bronze', 'bank_file') }} f using (sha256)
  where f.status = 'parsed'
),
per_file as (
  select bank, account_ref, booking_date, value_date, label, amount, sha256, count(*) as n
  from raw group by 1, 2, 3, 4, 5, 6, 7
),
dedup as (
  select bank, account_ref, booking_date, value_date, label, amount, max(n) as copies
  from per_file group by 1, 2, 3, 4, 5, 6
),
expanded as (
  select d.*, g.occurrence from dedup d cross join lateral generate_series(1, d.copies) as g(occurrence)
),
coverage as (  -- first day each account's exports cover
  select f.bank, e->>'last4' as last4, min(to_date(e->>'period_from', 'DD/MM/YYYY')) as covered_from
  from {{ source('bronze', 'bank_file') }} f cross join lateral jsonb_array_elements(f.accounts) as e
  where f.status = 'parsed' and e->>'period_from' <> '' group by 1, 2
),
mapped as (
  select x.*, a.alias as account, a.person, a.visibility, c.covered_from
  from expanded x
  join {{ source('silver', 'bank_account') }} a on a.bank = x.bank and a.last4 = x.account_ref
  left join coverage c on c.bank = x.bank and c.last4 = x.account_ref
),
typed as (
  select m.*,
    case
      when label ~* '^paiement par carte' then 'card'
      when label ~* '^pr[ée]l[èe]vement' then 'direct_debit'
      when label ~* '^virement en votre faveur' then 'transfer_in'
      when label ~* '^virement [ée]mis' then 'transfer_out'
      when label ~* '^retrait' then 'cash'
      when label ~* '^remboursement de pr[êe]t' then 'payment'
      when label ~* '^(remboursement|avoir)' then 'refund'
      when label ~* '^int[ée]r[êe]ts' then 'interest'
      when label ~* '^(cotisation|frais)' then 'fees'
      when label ~* '^r[èe]glement' then 'payment'
      else 'other'
    end as family,
    substring(label from '^Paiement par carte X(\d{4})') as card_last4,
    regexp_match(label, '(\d{2})/(\d{2})(?: - .*)?$') as dm
  from mapped m
),
dated as (
  select t.*,
    -- a card label ends with the purchase day/month (no year): the latest such date not after the booking
    case when family = 'card' and dm is not null then
      coalesce(
        case when {{ safe_date('extract(year from booking_date)', 'dm[2]::int', 'dm[1]::int') }} <= booking_date
             then {{ safe_date('extract(year from booking_date)', 'dm[2]::int', 'dm[1]::int') }} end,
        {{ safe_date('extract(year from booking_date) - 1', 'dm[2]::int', 'dm[1]::int') }})
    end as purchase_date
  from typed t
)
select
  encode(sha256(convert_to(concat_ws('|', bank, account_ref, booking_date, value_date, label, amount, occurrence), 'UTF8')), 'hex') as txn_id,
  account, person, visibility,
  booking_date, value_date,
  case when purchase_date is not null and booking_date - purchase_date <= 60
        and (covered_from is null or purchase_date >= covered_from)
       then purchase_date else booking_date end as spend_date,
  amount,
  label,
  case when family = 'card'
       then regexp_replace(regexp_replace(label, '^Paiement par carte X\d{4}\s+', ''), '\s+\d{2}/\d{2}(?= - |\s*$)', '')
       else label end as label_clean,
  family,
  card_last4,
  occurrence::int as occurrence
from dated
