{# Spending and income by month, person and category; spending by necessity; month-end balances. Each flow as the
   month, the calendar year to date and the rolling 12 months. Dense: a month where a category has no operation is
   a zero row, so a dashboard carrying the previous sample forward never shows last month's amount. Transfers
   (between your own accounts, or to/from another person) and investments are neither spend nor income: see reference/taxonomy.yaml `excluded`. #}
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='period', on_schema_change='fail', full_refresh=false) }}

with cls as (
  select t.person, t.visibility as owner, t.account, t.booking_date, t.amount,
         date_trunc('month', t.spend_date)::date as period,
         c.category, c.subcategory, coalesce(c.necessity, 'unspecified') as necessity
  from {{ ref('bank_transaction') }} t join {{ ref('bank_transaction_category') }} c using (txn_id)
),
months as (select generate_series(min(period), max(period), interval '1 month')::date as period from cls),
spending as (
  select * from cls
  where category <> 'income'
    and category <> 'transfers'                                     -- internal / to_others / from_others
    and not (category = 'savings' and subcategory = 'investment')
),
income as (select * from cls where category = 'income'),
spend_universe as (select distinct person, owner, category as item1, subcategory as item2 from spending),
income_universe as (select distinct person, owner, category as item1, subcategory as item2 from income),
nec_universe as (select distinct person, owner, necessity as item1 from spending),
spend_rows as (
  select m.period, 'spend' as measure, u.person, u.owner, u.item1, u.item2, -coalesce(sum(s.amount), 0) as value
  from months m cross join spend_universe u
  left join spending s on s.period = m.period and s.person = u.person and s.owner = u.owner and s.category = u.item1 and s.subcategory = u.item2
  group by 1, 3, 4, 5, 6
),
income_rows as (
  select m.period, 'income' as measure, u.person, u.owner, u.item1, u.item2, coalesce(sum(s.amount), 0) as value
  from months m cross join income_universe u
  left join income s on s.period = m.period and s.person = u.person and s.owner = u.owner and s.category = u.item1 and s.subcategory = u.item2
  group by 1, 3, 4, 5, 6
),
nec_rows as (
  select m.period, 'spend_necessity' as measure, u.person, u.owner, u.item1, ''::text as item2, -coalesce(sum(s.amount), 0) as value
  from months m cross join nec_universe u
  left join spending s on s.period = m.period and s.person = u.person and s.owner = u.owner and s.necessity = u.item1
  group by 1, 3, 4, 5
),
anchor as (select distinct on (account) account, as_of, balance from {{ ref('bank_balance') }} order by account, as_of desc),
balance_rows as (
  select m.period, 'balance' as measure, a.person, a.visibility as owner, an.account as item1, ''::text as item2,
         an.balance - coalesce((select sum(t.amount) from {{ ref('bank_transaction') }} t
                                where t.account = an.account and t.booking_date > (m.period + interval '1 month' - interval '1 day')::date
                                  and t.booking_date <= an.as_of), 0) as value
  from months m cross join anchor an
  join {{ source('silver', 'bank_account') }} a on a.alias = an.account
),
everything as (
  select * from spend_rows union all select * from income_rows union all select * from nec_rows union all select * from balance_rows
)
select
  period, measure, person, owner, item1, item2,
  value::numeric(14,2) as value,
  (case when measure <> 'balance' then sum(value) over ytd end)::numeric(14,2) as ytd_value,
  (case when measure <> 'balance' and count(*) over r12 = 12 then sum(value) over r12 end)::numeric(14,2) as r12_value
from everything
window
  ytd as (partition by extract(year from period), measure, person, owner, item1, item2 order by period rows between unbounded preceding and current row),
  r12 as (partition by measure, person, owner, item1, item2 order by period rows between 11 preceding and current row)
