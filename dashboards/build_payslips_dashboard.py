"""Generates the Grafana "Finance - Payslips" dashboard (PromQL over the `finance` Mimir tenant).

    python dashboards/build_payslips_dashboard.py ../stack/src/observability/files/dashboards/finance/payslips.json

The View switch (Monthly / Year to date / Rolling 12 months) is a dashboard variable that
selects the metric-name prefix: the publisher emits every flow figure three times,
`finance_payslip_<m>_eur`, `finance_payslip_ytd_<m>_eur`, `finance_payslip_r12_<m>_eur`.
Names are matched with `{__name__=~"finance_payslip_${view}<m>_eur"}` and the variable values are
regex groups (`()`, `(ytd_)`, `(r12_)`), so no value is empty.
"""

import json
import sys

DS = {"type": "prometheus", "uid": "metrics-finance"}
HOLD = "[45d]"  # one sample a month: carry the last one forward until the next payslip
_id = [0]


def name(measure: str, extra: str = "") -> str:
    sel = f'__name__=~"finance_payslip_${{view}}{measure}_eur"'
    return "{" + sel + (", " + extra if extra else "") + "}"


def held(measure: str, extra: str = "", window: str = HOLD) -> str:
    return f"last_over_time({name(measure, extra)}{window})"


def tgt(expr, legend="", ref="A", instant=False):
    return {"datasource": DS, "editorMode": "code", "expr": expr, "legendFormat": legend, "refId": ref,
            "range": not instant, "instant": instant}


def panel(kind, title, x, y, w, h, targets, unit="short", custom=None, options=None, overrides=None, desc=None):
    _id[0] += 1
    d = {"id": _id[0], "type": kind, "title": title, "gridPos": {"x": x, "y": y, "w": w, "h": h}, "datasource": DS,
         "targets": targets,
         "fieldConfig": {"defaults": {"unit": unit, "custom": custom or {}, "color": {"mode": "palette-classic"}},
                         "overrides": overrides or []},
         "options": options or {}}
    if desc:
        d["description"] = desc
    return d


def stat(title, x, expr, unit, desc="Latest payslip in the selected time range, in the selected view."):
    p = panel("stat", title, x, 0, 4, 4, [tgt(expr, instant=True)], unit,
              options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                       "colorMode": "value", "graphMode": "none", "textMode": "auto"}, desc=desc)
    p["fieldConfig"]["defaults"]["color"] = {"mode": "fixed", "fixedColor": "blue"}
    p["fieldConfig"]["defaults"]["thresholds"] = {"mode": "absolute", "steps": [{"color": "blue", "value": None}]}
    return p


def last_in_range(measure, extra=""):
    return f"sum({held(measure, extra, '[$__range]')})"


BONUS = 'element=~"bonus|bonus_exempt"'
EL_BONUS = 'element="bonus"'
EL_EXEMPT = 'element="bonus_exempt"'
SIDE_EMPLOYEE = 'side="employee"'
SIDE_EMPLOYER = 'side="employer"'
P = []
P.append(stat("Net paid", 0, last_in_range("net_paid"), "currencyEUR"))
P.append(stat("Gross", 4, last_in_range("gross"), "currencyEUR"))
P.append(stat("Bonuses", 8, last_in_range("pay_element", BONUS), "currencyEUR",
              "Bonuses and commissions, plus the value-sharing bonus printed outside the gross."))
P.append(stat("Tax withheld", 12, last_in_range("tax_withheld"), "currencyEUR"))
P.append(stat("Net / gross", 16, f'{last_in_range("net_paid")} / {last_in_range("gross")}', "percentunit"))
P.append(stat("Bonuses / gross", 20, f'{last_in_range("pay_element", BONUS)} / {last_in_range("gross")}', "percentunit"))

ts = {"lineWidth": 2, "fillOpacity": 10, "showPoints": "never", "spanNulls": True, "lineInterpolation": "stepAfter"}
stack = {**ts, "stacking": {"mode": "normal"}, "fillOpacity": 60}
leg = {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}
tab = {"legend": {"displayMode": "table", "placement": "right", "calcs": ["lastNotNull"]}, "tooltip": {"mode": "multi"}}

P.append(panel("timeseries", "Gross vs net (${view:text})", 0, 4, 12, 8, [
    tgt(f'sum({held("gross")})', "Gross"),
    tgt(f'sum({held("net_before_tax")})', "Net before tax", "B"),
    tgt(f'sum({held("net_paid")})', "Net paid", "C")], "currencyEUR", ts, leg))
P.append(panel("timeseries", "What the gross is made of (${view:text})", 12, 4, 12, 8, [
    tgt(f'sum by (element) ({held("pay_element")})', "{{element}}")], "currencyEUR", stack, tab,
    desc="base_salary, bonus, time_off (leave, RTT, absences, sick pay), back_pay, other_pay add up to the gross. "
         "bonus_exempt (value-sharing bonus) is printed outside the gross, so it sits on top."))
P.append(panel("timeseries", "Bonuses (${view:text})", 0, 12, 12, 8, [
    tgt(f'sum({held("pay_element", EL_BONUS)})', "Bonuses and commissions"),
    tgt(f'sum({held("pay_element", EL_EXEMPT)})', "Value-sharing bonus", "B"),
    tgt(f'sum({held("pay_element", BONUS)}) / sum({held("gross")})', "Share of gross", "C")], "currencyEUR",
    {**ts, "fillOpacity": 25}, leg,
    overrides=[{"matcher": {"id": "byName", "options": "Share of gross"}, "properties": [
        {"id": "unit", "value": "percentunit"}, {"id": "custom.axisPlacement", "value": "right"},
        {"id": "custom.fillOpacity", "value": 0}]}]))
P.append(panel("timeseries", "Income tax withheld and effective rate (${view:text})", 12, 12, 12, 8, [
    tgt(f'sum({held("tax_withheld")})', "Tax withheld"),
    tgt(f'sum({held("tax_withheld")}) / sum({held("taxable_net")})', "Effective rate (tax / taxable net)", "B")],
    "currencyEUR", {**ts, "fillOpacity": 25}, leg,
    desc="Taxable net is missing for a few scanned 2020-21 months, so the rate has gaps there.",
    overrides=[{"matcher": {"id": "byName", "options": "Effective rate (tax / taxable net)"}, "properties": [
        {"id": "unit", "value": "percentunit"}, {"id": "custom.axisPlacement", "value": "right"},
        {"id": "custom.fillOpacity", "value": 0}]}]))
P.append(panel("timeseries", "Net-to-gross and contribution share (${view:text})", 0, 20, 12, 8, [
    tgt(f'sum({held("net_paid")}) / sum({held("gross")})', "Net / gross"),
    tgt(f'sum({held("employee_contributions")}) / sum({held("gross")})', "Employee contributions / gross", "B")],
    "percentunit", ts, leg))
P.append(panel("timeseries", "Employer cost (${view:text})", 12, 20, 12, 8, [
    tgt(f'sum({held("employer_contributions")})', "Employer contributions"),
    tgt(f'sum({held("employer_cost")})', "Total employer cost", "B")], "currencyEUR", ts, leg,
    desc="The total employer cost is not printed on payslips after 2025-10; its year-to-date and rolling views stay empty for the affected windows."))
P.append(panel("timeseries", "Employee-side contributions by category (${view:text})", 0, 28, 12, 9, [
    tgt(f'sum by (category) ({held("contribution", SIDE_EMPLOYEE)} > 0)', "{{category}}")],
    "currencyEUR", stack, tab))
P.append(panel("timeseries", "Employer-side contributions by category (${view:text})", 12, 28, 12, 9, [
    tgt(f'sum by (category) ({held("contribution", SIDE_EMPLOYER)} > 0)', "{{category}}")],
    "currencyEUR", stack, tab))
P.append(panel("timeseries", "Leave balances (days; not affected by the View)", 0, 37, 24, 7, [
    tgt(f'sum by (kind) (last_over_time(finance_payslip_leave_days{HOLD}))', "{{kind}}")], "none", ts, leg))

view = {
    "name": "view", "label": "View", "type": "custom", "query": "Monthly : (),Year to date : (ytd_),Rolling 12 months : (r12_)",
    "current": {"text": "Monthly", "value": "()", "selected": True},
    "options": [{"text": "Monthly", "value": "()", "selected": True},
                {"text": "Year to date", "value": "(ytd_)", "selected": False},
                {"text": "Rolling 12 months", "value": "(r12_)", "selected": False}],
    "includeAll": False, "multi": False, "hide": 0,
}
dash = {"uid": "finance-payslips", "title": "Finance - Payslips", "tags": ["finance", "payslips"], "timezone": "browser",
        "schemaVersion": 39, "version": 2, "refresh": "", "time": {"from": "now-7y", "to": "now"},
        "description": "Payslip figures published by finance-pipelines into the `finance` Mimir tenant. The View "
                       "switch picks the month, the calendar year to date, or the rolling 12 months for every flow. "
                       "Each viewer only sees series whose owner label is their own login (scope shim); admins see all owners.",
        "panels": P, "templating": {"list": [view]}, "annotations": {"list": []}}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "payslips.json"
    json.dump(dash, open(out, "w"), indent=2, ensure_ascii=False)
    print(f"{len(P)} panels -> {out}")
