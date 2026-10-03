{# Small table, cheap to recompute: replace every month on each run (delete+insert on the key). #}
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='period', on_schema_change='fail', full_refresh=false) }}

select
  period,
  extract(year from period)::int                                                   as year,
  gross_amount,
  net_before_tax,
  net_paid,
  coalesce(pas_amount, 0)::numeric(12,2)                                           as pas_amount,
  pas_rate,
  employee_contributions,
  employer_contributions,
  employer_cost,
  taxable_net,
  sum(gross_amount) over w ::numeric(12,2)                                         as ytd_gross,
  sum(net_paid) over w ::numeric(12,2)                                              as ytd_net_paid,
  sum(coalesce(pas_amount, 0)) over w ::numeric(12,2)                               as ytd_pas,
  round(net_paid / gross_amount, 4)::numeric(7,4)                                  as net_to_gross,
  round(employee_contributions / gross_amount, 4)::numeric(7,4)                    as contributions_to_gross,
  (coalesce(leave_cp_n1_balance, 0) + coalesce(leave_cp_n_balance, 0))::numeric(7,2) as leave_cp_balance,
  leave_rtt_balance
from {{ ref('payslip') }}
window w as (partition by extract(year from period) order by period)
