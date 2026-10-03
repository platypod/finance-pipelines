{# delete+insert on `period` replaces all lines of a month at once, so a re-issued payslip with fewer lines leaves nothing stale. #}
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='period', on_schema_change='fail', full_refresh=false) }}

select
  p.period,
  l.line_no,
  l.section,
  l.label,
  {{ line_category('l.section', 'l.label') }}                      as category,
  {{ fr_num('l.base') }}::numeric(12,2)                            as base,
  {{ fr_num('l.rate') }}::numeric(10,4)                            as rate,
  {{ fr_num('l.employee_gain') }}::numeric(12,2)                   as employee_gain,
  {{ fr_num('l.employee_deduct') }}::numeric(12,2)                 as employee_deduction,
  {{ fr_num('l.employer_base') }}::numeric(12,2)                   as employer_base,
  {{ fr_num('l.employer_rate') }}::numeric(10,4)                   as employer_rate,
  {{ fr_num('l.employer_amount') }}::numeric(12,2)                 as employer_amount,
  l.sha256                                                         as source_sha256
from {{ ref('payslip') }} p
join {{ source('bronze', 'payslip_line_raw') }} l on l.sha256 = p.source_sha256
