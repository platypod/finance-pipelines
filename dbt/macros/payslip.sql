{# Payslip numbers arrive as printed: "5 357,13" (new layout) or "3 193.44" (Silae), maybe with NBSP. #}
{% macro fr_num(expr) -%}
  nullif(replace(replace(replace(trim({{ expr }}), chr(160), ''), ' ', ''), ',', '.'), '')::numeric
{%- endmacro %}

{% macro fr_date(expr) -%}
  to_date(nullif(trim({{ expr }}), ''), 'DD/MM/YYYY')
{%- endmacro %}

{# Category of a payslip line. Labels differ across layouts; order matters (specific before generic). #}
{% macro line_category(section, label) -%}
  case
    when {{ section }} = 'brut' then 'gross_pay'
    when {{ label }} ~* 'csg' then 'csg_crds'
    when {{ label }} ~* 'ch.mage|apec' then 'unemployment'
    when {{ label }} ~* '^(base|compl[eé]ment)$|^famille|familiales' then 'family'
    when {{ label }} ~* 'accidents? du travail' then 'work_accident'
    when {{ label }} ~* 'incap|pr[eé]voyance|rente' then 'provident'
    when {{ label }} ~* 'mal\. mat|maladie|mutuelle|sant[eé]' then 'health'
    when {{ label }} ~* 'titres?-restaurant' then 'meal_vouchers'
    when {{ label }} ~* 'adesatt|autres contributions|fnal|solidarit|dialogue social|formation prof|apprentissage|paritarisme|^ags$' then 'other_contributions'
    when {{ label }} ~* 's[eé]curit[eé] sociale|compl[eé]mentaire|tranche|[eé]quilibre|retraite|vieillesse' then 'retirement'
    else 'other'
  end
{%- endmacro %}
