{# One row per month x measure x item x side, with the month, its calendar year-to-date and its rolling 12 months.
   Dense on purpose: a month where a category has no amount still gets a 0 row, otherwise a dashboard that
   carries the previous sample forward would show last month's value. YTD / 12-month sums are NULL when any
   month in the window has no printed figure (e.g. employer cost after 2025-10) rather than a silent undercount. #}
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='period', on_schema_change='fail', full_refresh=false) }}

with months as (
  select period, gross_amount, net_before_tax, net_paid, coalesce(pas_amount, 0) as tax_withheld,
         taxable_net, employee_contributions, employer_contributions, employer_cost
  from {{ ref('payslip') }}
),
flows as (
  select period, 'gross' as measure, gross_amount as value from months
  union all select period, 'net_before_tax', net_before_tax from months
  union all select period, 'net_paid', net_paid from months
  union all select period, 'tax_withheld', tax_withheld from months
  union all select period, 'taxable_net', taxable_net from months
  union all select period, 'employee_contributions', employee_contributions from months
  union all select period, 'employer_contributions', employer_contributions from months
  union all select period, 'employer_cost', employer_cost from months
),
lines as (
  select * from {{ ref('payslip_line') }}
),
pay_elements as (
  select m.period, 'pay_element' as measure, c.item, '' as side,
         coalesce(sum(coalesce(l.employee_gain, 0) - coalesce(l.employee_deduction, 0)), 0) as value
  from months m
  cross join (values ('base_salary'), ('bonus'), ('time_off'), ('back_pay'), ('other_pay'), ('bonus_exempt')) as c(item)
  left join lines l on l.period = m.period and l.category = c.item and (l.section = 'brut' or c.item = 'bonus_exempt')
  group by m.period, c.item
),
contribution_universe as (
  select distinct category as item from lines where section = 'cotisations' or category = 'meal_vouchers'
),
contributions as (
  select m.period, 'contribution' as measure, u.item, s.side,
         coalesce(sum(case s.side when 'employee' then l.employee_deduction else l.employer_amount end), 0) as value
  from months m
  cross join contribution_universe u
  cross join (values ('employee'), ('employer')) as s(side)
  left join lines l on l.period = m.period and l.category = u.item and (l.section = 'cotisations' or l.category = 'meal_vouchers')
  group by m.period, u.item, s.side
),
everything as (
  select period, measure, ''::text as item, ''::text as side, value from flows
  union all select period, measure, item, side, value from pay_elements
  union all select period, measure, item, side, value from contributions
)
select
  period,
  measure,
  item,
  side,
  value::numeric(12,2) as value,
  (case when count(value) over ytd = count(*) over ytd then sum(value) over ytd end)::numeric(12,2) as ytd_value,
  (case when count(*) over r12 = 12 and count(value) over r12 = 12 then sum(value) over r12 end)::numeric(12,2) as r12_value
from everything
window
  ytd as (partition by extract(year from period), measure, item, side order by period rows between unbounded preceding and current row),
  r12 as (partition by measure, item, side order by period rows between 11 preceding and current row)
