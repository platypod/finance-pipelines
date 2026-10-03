{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='period', on_schema_change='fail', full_refresh=false) }}

select
  period,
  category,
  coalesce(sum(employee_deduction), 0)::numeric(12,2)  as employee_amount,
  coalesce(sum(employer_amount), 0)::numeric(12,2)     as employer_amount
from {{ ref('payslip_line') }}
where section = 'cotisations' or category = 'meal_vouchers'
group by period, category
