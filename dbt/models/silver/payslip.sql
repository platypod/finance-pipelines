{{ config(materialized='incremental', unique_key='period', on_schema_change='fail', full_refresh=false) }}

{# One row per month: the latest successfully parsed file wins (a re-issued payslip replaces the old one). #}
with latest as (
  select distinct on (period) *
  from {{ source('bronze', 'payslip_file') }}
  where status = 'parsed'
  order by period, _ingested_at desc
)
select
  period,
  summary->>'employer_siret'                                               as employer_siret,
  {{ fr_num("summary->>'gross'") }}::numeric(12,2)                         as gross_amount,
  {{ fr_num("summary->>'employee_contributions'") }}::numeric(12,2)        as employee_contributions,
  {{ fr_num("summary->>'employer_contributions'") }}::numeric(12,2)        as employer_contributions,
  {{ fr_num("summary->>'net_before_tax'") }}::numeric(12,2)                as net_before_tax,
  {{ fr_num("summary->>'net_social'") }}::numeric(12,2)                    as net_social,
  {{ fr_num("summary->>'pas_base'") }}::numeric(12,2)                      as pas_base,
  {{ fr_num("summary->>'pas_rate'") }}::numeric(7,4)                       as pas_rate,
  {{ fr_num("summary->>'pas_amount'") }}::numeric(12,2)                    as pas_amount,
  {{ fr_num("summary->>'net_paid'") }}::numeric(12,2)                      as net_paid,
  {{ fr_num("summary->>'taxable_net'") }}::numeric(12,2)                   as taxable_net,
  {{ fr_num("summary->>'employer_cost'") }}::numeric(12,2)                 as employer_cost,
  {{ fr_num("summary->>'total_paid'") }}::numeric(12,2)                    as total_paid,
  {{ fr_num("summary->>'hours'") }}::numeric(8,2)                          as hours,
  {{ fr_num("summary->>'ytd_gross'") }}::numeric(12,2)                     as ytd_gross,
  {{ fr_num("summary->>'ytd_taxable_net'") }}::numeric(12,2)               as ytd_taxable_net,
  {{ fr_num("summary->>'leave_cp_n1_balance'") }}::numeric(7,2)            as leave_cp_n1_balance,
  {{ fr_num("summary->>'leave_cp_n_balance'") }}::numeric(7,2)             as leave_cp_n_balance,
  {{ fr_num("summary->>'leave_rtt_balance'") }}::numeric(7,2)              as leave_rtt_balance,
  {{ fr_date("summary->>'payment_date'") }}                                as payment_date,
  layout,
  source,
  sha256                                                                   as source_sha256
from latest
