"""Generates the Grafana "Finance - Bank" dashboard (PromQL over the `finance` Mimir tenant).

    python dashboards/build_bank_dashboard.py ../stack/src/observability/files/dashboards/finance/bank.json

Series: finance_bank_[ytd_|r12_]{spend,income}_eur{category,subcategory,person,owner}, spend_necessity_eur{necessity},
balance_eur{account}. `owner` decides who may see a series (scope shim), `person` whose figures they are
(login, or `joint`): the Person variable filters on it (several at once, or All). Internal transfers between a
person's own accounts and savings/investment are excluded from spend and income upstream.
"""

import json
import sys

DS = {"type": "prometheus", "uid": "metrics-finance"}
HOLD = "[45d]"  # one sample a month: carry the last one forward until the next one
_id = [0]
WHO = 'person=~"${person}"'


def sel(measure, extra=""):
    return "{" + f'__name__=~"finance_bank_${{view}}{measure}_eur", {WHO}' + (", " + extra if extra else "") + "}"


def held(measure, extra="", window=HOLD):
    return f"last_over_time({sel(measure, extra)}{window})"


def monthly(measure, extra="", window="[$__range]"):
    """Every month's own figure, whatever the View: used for totals over the selected range."""
    s = "{" + f'__name__="finance_bank_{measure}_eur", {WHO}' + (", " + extra if extra else "") + "}"
    return f"sum_over_time({s}{window})"


def tgt(expr, legend="", ref="A", instant=False, table=False):
    t = {"datasource": DS, "editorMode": "code", "expr": expr, "legendFormat": legend, "refId": ref,
         "range": not instant, "instant": instant}
    if table:
        t["format"] = "table"
    return t


def panel(kind, title, x, y, w, h, targets, unit="short", custom=None, options=None, overrides=None, desc=None, transformations=None):
    _id[0] += 1
    d = {"id": _id[0], "type": kind, "title": title, "gridPos": {"x": x, "y": y, "w": w, "h": h}, "datasource": DS,
         "targets": targets,
         "fieldConfig": {"defaults": {"unit": unit, "custom": custom or {}, "color": {"mode": "palette-classic"}},
                         "overrides": overrides or []},
         "options": options or {}}
    if desc:
        d["description"] = desc
    if transformations:
        d["transformations"] = transformations
    return d


def stat(title, x, expr, unit, desc, legend="{{person}}"):
    p = panel("stat", title, x, 0, 4, 4, [tgt(expr, legend, instant=True)], unit,
              options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                       "colorMode": "value", "graphMode": "none", "textMode": "auto"}, desc=desc)
    p["fieldConfig"]["defaults"]["color"] = {"mode": "fixed", "fixedColor": "blue"}
    return p


ts = {"lineWidth": 2, "fillOpacity": 10, "showPoints": "never", "spanNulls": True, "lineInterpolation": "stepAfter"}
stack = {**ts, "stacking": {"mode": "normal"}, "fillOpacity": 60}
leg = {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}
tab = {"legend": {"displayMode": "table", "placement": "right", "calcs": ["lastNotNull", "sum"]}, "tooltip": {"mode": "multi"}}
pct = [{"matcher": {"id": "byRegexp", "options": ".*"}, "properties": [{"id": "unit", "value": "percentunit"}]}]

SPEND, INCOME = monthly("spend"), monthly("income")
P = [
    stat("Spend (selected range)", 0, f"sum by (person) ({SPEND})", "currencyEUR",
         "Sum of the monthly figures in the time range, whatever the View. Excludes transfers between own accounts and savings."),
    stat("Income (selected range)", 4, f"sum by (person) ({INCOME})", "currencyEUR", "Salary, reimbursements, interest and other income."),
    stat("Savings rate", 8, f"1 - sum by (person) ({SPEND}) / sum by (person) ({INCOME})", "percentunit",
         "(income - spend) / income over the selected range."),
    stat("Uncategorized share", 12, f'sum by (person) ({monthly("spend", 'category="uncategorized"')}) / sum by (person) ({SPEND})',
         "percentunit", "Spend no rule classified yet: add a rule or an override (see the finance README)."),
    stat("Luxury share", 16, f'sum by (person) ({monthly("spend_necessity", 'necessity="luxury"')}) / sum by (person) ({SPEND})',
         "percentunit", "Share of spend tagged luxury (by rule, or by an override)."),
    stat("Balances (latest)", 20, f'sum by (person) (last_over_time(finance_bank_balance_eur{{{WHO}}}[$__range]))', "currencyEUR",
         "Sum of the latest month-end balance of every account in range (current + savings), per person."),
]

P += [
    panel("timeseries", "Spend by category (${view:text})", 0, 4, 12, 9,
          [tgt(f"sum by (category) ({held('spend')})", "{{category}}")], "currencyEUR", stack, tab,
          desc="Stacks the selected persons. Pick a single person to see only theirs."),
    panel("timeseries", "Spend by necessity (${view:text})", 12, 4, 12, 9,
          [tgt(f"sum by (necessity) ({held('spend_necessity')})", "{{necessity}}")], "currencyEUR", stack, tab,
          desc="essential / comfort / luxury, from the rules (or an override). Cash and uncategorized have none."),
    panel("timeseries", "Income vs spend (${view:text})", 0, 13, 12, 8,
          [tgt(f"sum by (person) ({held('income')})", "Income", "A"),
           tgt(f"sum by (person) ({held('spend')})", "Spend", "B")], "currencyEUR", ts, leg),
    panel("timeseries", "Savings rate (${view:text})", 12, 13, 12, 8,
          [tgt(f"1 - sum by (person) ({held('spend')}) / sum by (person) ({held('income')})", "Savings rate")],
          "percentunit", ts, leg, desc="(income - spend) / income. Credits from other people (transfers) are not income here."),
    panel("timeseries", "Spend by person (${view:text})", 0, 21, 12, 8,
          [tgt(f"sum by (person) ({held('spend')})", "Spend")], "currencyEUR", {**ts, "fillOpacity": 25}, leg,
          desc="`joint` is the shared account. Each person's own accounts are theirs."),
    panel("timeseries", "Account balances (month end)", 12, 21, 12, 8,
          [tgt(f'sum by (account) (last_over_time(finance_bank_balance_eur{{{WHO}}}{HOLD}))', "{{account}}")], "currencyEUR", ts, tab,
          desc="Reconstructed backwards from the balance printed on each export; the pipeline checks the exports agree."),
    panel("timeseries", "Uncategorized spend (monthly)", 0, 29, 12, 8,
          [tgt('sum by (person) (last_over_time({__name__="finance_bank_spend_eur", category="uncategorized", ' + WHO + '}' + HOLD + '))',
               "Uncategorized")], "currencyEUR", {**ts, "drawStyle": "bars", "fillOpacity": 60, "lineInterpolation": "linear"}, leg,
          desc="Should trend to ~0 as rules are added. Details are in the SQL view / overrides.csv."),
    panel("table", "Spend by category and subcategory (selected range)", 12, 29, 12, 8,
          [tgt(f"sum by (category, subcategory) ({SPEND})", "", instant=True, table=True)], "currencyEUR",
          options={"showHeader": True, "sortBy": [{"displayName": "Value", "desc": True}]},
          transformations=[{"id": "organize", "options": {"excludeByName": {"Time": True},
                                                          "renameByName": {"Value": "Spend (EUR)"}}}],
          desc="Whatever the View: the sum of the months in the time range."),
]

view = {
    "name": "view", "label": "View", "type": "custom", "query": "Monthly : (),Year to date : (ytd_),Rolling 12 months : (r12_)",
    "current": {"text": "Monthly", "value": "()", "selected": True},
    "options": [{"text": "Monthly", "value": "()", "selected": True},
                {"text": "Year to date", "value": "(ytd_)", "selected": False},
                {"text": "Rolling 12 months", "value": "(r12_)", "selected": False}],
    "includeAll": False, "multi": False, "hide": 0,
}
person = {
    "name": "person", "label": "Person", "type": "query", "datasource": DS,
    "query": {"query": 'label_values({__name__=~"finance_bank_spend_eur"}, person)', "refId": "person"},
    "definition": 'label_values({__name__=~"finance_bank_spend_eur"}, person)',
    "includeAll": True, "allValue": ".+", "multi": True, "current": {"text": "All", "value": "$__all"},
    "refresh": 2, "sort": 1, "hide": 0,
}
dash = {"uid": "finance-bank", "title": "Finance - Bank", "tags": ["finance", "bank"], "timezone": "browser",
        "schemaVersion": 39, "version": 1, "refresh": "", "time": {"from": "now-13M", "to": "now"},
        "description": "Bank-statement figures published by finance-pipelines into the `finance` Mimir tenant, by category, "
                       "necessity and person. Series carry `owner` (who may see them: scope shim, login or the finance group) and "
                       "`person` (whose figures: the Person filter). Transfers between own accounts and savings are excluded.",
        "panels": P, "templating": {"list": [view, person]}, "annotations": {"list": []}}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "bank.json"
    json.dump(dash, open(out, "w"), indent=2, ensure_ascii=False)
    print(f"{len(P)} panels -> {out}")
