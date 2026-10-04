{# The balance printed at the top of each account in each export. One row per account and export date. #}
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key=['account', 'as_of'], on_schema_change='fail', full_refresh=false) }}

select distinct on (a.alias, to_date(e->>'balance_date', 'DD/MM/YYYY'))
  a.alias                                                as account,
  to_date(e->>'balance_date', 'DD/MM/YYYY')              as as_of,
  {{ fr_num("e->>'balance'") }}::numeric(14,2)           as balance,
  f.sha256                                               as source_sha256
from {{ source('bronze', 'bank_file') }} f
cross join lateral jsonb_array_elements(f.accounts) as e
join {{ source('silver', 'bank_account') }} a on a.bank = f.bank and a.last4 = e->>'last4'
where f.status = 'parsed' and e->>'balance_date' <> ''
order by a.alias, to_date(e->>'balance_date', 'DD/MM/YYYY'), f._ingested_at desc
