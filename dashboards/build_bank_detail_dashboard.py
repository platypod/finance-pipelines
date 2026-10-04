"""Generates the "Finance - Bank detail" dashboard for the DEDICATED finance Grafana (Postgres datasource uid `finance`).

    python dashboards/build_bank_detail_dashboard.py ../stack/src/finance/files/dashboards/bank-detail.json

Reads gold.bank_transaction_detail only (the finance_grafana role sees gold only). Transaction labels live here and
nowhere else: the shared Grafana / Mimir only ever get monthly aggregates.
"""

import json
import sys

DS = {"type": "grafana-postgresql-datasource", "uid": "finance"}
T = "gold.bank_transaction_detail"
_id = [0]
FILTER = ("person IN ($person) AND account IN ($account) AND category IN ($category) AND subcategory IN ($subcategory) "
          "AND coalesce(necessity, 'none') IN ($necessity) AND family IN ($family) AND source IN ($source) "
          "AND abs(amount) BETWEEN ${min_amount} AND ${max_amount} AND label ILIKE '%${search}%' AND $__timeFilter(spend_date)")


def sql(q, ref="A", fmt="table"):
    return {"datasource": DS, "editorMode": "code", "format": fmt, "rawQuery": True, "rawSql": q, "refId": ref}


def panel(kind, title, x, y, w, h, targets, unit="short", options=None, overrides=None, desc=None, custom=None):
    _id[0] += 1
    d = {"id": _id[0], "type": kind, "title": title, "gridPos": {"x": x, "y": y, "w": w, "h": h}, "datasource": DS,
         "targets": targets,
         "fieldConfig": {"defaults": {"unit": unit, "custom": custom or {}, "color": {"mode": "palette-classic"}},
                         "overrides": overrides or []},
         "options": options or {}}
    if desc:
        d["description"] = desc
    return d


def stat(title, x, q, unit, desc):
    p = panel("stat", title, x, 0, 6, 4, [sql(q)], unit,
              options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "value",
                       "graphMode": "none", "textMode": "auto"}, desc=desc)
    p["fieldConfig"]["defaults"]["color"] = {"mode": "fixed", "fixedColor": "blue"}
    return p


money = [{"matcher": {"id": "byName", "options": "amount"}, "properties": [{"id": "unit", "value": "currencyEUR"}]}]
table_opts = {"showHeader": True, "footer": {"show": False}}
def sel_stat(title, x, q, unit, desc):
    p = stat(title, x, q, unit, desc)
    p["gridPos"]["w"] = 6
    return p


P = [
    sel_stat("Operations in the selection", 0, f"SELECT count(*) AS operations FROM {T} WHERE {FILTER}", "none",
             "Every filter above and the time range apply (on the reporting date)."),
    sel_stat("Money out", 6, f"SELECT coalesce(-sum(amount) FILTER (WHERE amount < 0), 0) AS out FROM {T} WHERE {FILTER}", "currencyEUR",
             "Sum of the debits in the selection. Transfers between own accounts are included here: filter them out with Category."),
    sel_stat("Money in", 12, f"SELECT coalesce(sum(amount) FILTER (WHERE amount > 0), 0) AS income FROM {T} WHERE {FILTER}", "currencyEUR",
             "Sum of the credits in the selection."),
    sel_stat("Net", 18, f"SELECT coalesce(sum(amount), 0) AS net FROM {T} WHERE {FILTER}", "currencyEUR", "Credits minus debits."),
    panel("barchart", "Selection by month (money out, by category)", 0, 4, 24, 8, [sql(
        f"SELECT date_trunc('month', spend_date) AS time, category, -sum(amount) FILTER (WHERE amount < 0) AS out FROM {T} "
        f"WHERE {FILTER} GROUP BY 1, 2 ORDER BY 1", fmt="table")], "currencyEUR",
        {"xField": "time", "stacking": "normal", "legend": {"displayMode": "list", "placement": "bottom"}},
        desc="Follows the filters. For 'all car operations', pick Category = car."),
    panel("table", "Operations (every line of the selection)", 0, 12, 24, 16, [sql(
        f"SELECT spend_date AS date, account, person, amount, label, category, subcategory, necessity, family, source, rule_id, txn_id "
        f"FROM {T} WHERE {FILTER} ORDER BY spend_date DESC, abs(amount) DESC")], "short",
        {"showHeader": True, "footer": {"show": True, "reducer": ["sum"], "fields": ["amount"]}}, money,
        desc="Click a column header to sort, or use the filters above. txn_id is what overrides.csv needs to fix one operation."),
    panel("table", "Review queue: what no rule explains yet (largest first)", 0, 28, 24, 10, [sql(
        f"SELECT spend_date AS date, account, person, amount, label, family, category, subcategory, txn_id FROM {T} "
        "WHERE needs_review ORDER BY abs(amount) DESC")], "short", table_opts, money,
        desc="Not affected by the filters. Fix it once for all similar operations with a rule in rules.yaml (match on the label), or "
             "for this one operation with a line in overrides.csv (use txn_id); then `make sync-bank`."),
    panel("table", "Top labels not yet covered by a rule", 0, 38, 12, 9, [sql(
        f"SELECT label, count(*) AS operations, sum(amount) AS amount FROM {T} WHERE needs_review AND amount < 0 "
        "GROUP BY label ORDER BY sum(amount) LIMIT 30")], "short", table_opts, money,
        desc="Grouped by cleaned label: a good rule candidate has many operations or a large amount."),
    panel("barchart", "How operations were classified", 12, 38, 12, 9, [sql(
        f"SELECT source, count(*) AS operations FROM {T} GROUP BY source ORDER BY 2 DESC")], "short",
        {"legend": {"showLegend": False}, "xField": "source"},
        desc="rule, override, transfer_pair (own-account transfers) or default (nothing matched)."),
]


def qvar(name, label, query):
    return {"name": name, "label": label, "type": "query", "datasource": DS, "query": query, "definition": query,
            "includeAll": True, "multi": True, "current": {"text": "All", "value": "$__all"}, "refresh": 2, "sort": 1, "hide": 0}


templating = [
    qvar("person", "Person", f"SELECT DISTINCT person FROM {T} ORDER BY 1"),
    qvar("account", "Account", f"SELECT DISTINCT account FROM {T} WHERE person IN ($person) ORDER BY 1"),
    qvar("category", "Category", f"SELECT DISTINCT category FROM {T} ORDER BY 1"),
    qvar("subcategory", "Subcategory", f"SELECT DISTINCT subcategory FROM {T} WHERE category IN ($category) ORDER BY 1"),
    qvar("necessity", "Necessity", f"SELECT DISTINCT coalesce(necessity, 'none') FROM {T} ORDER BY 1"),
    qvar("family", "Kind", f"SELECT DISTINCT family FROM {T} ORDER BY 1"),
    qvar("source", "Decided by", f"SELECT DISTINCT source FROM {T} ORDER BY 1"),
    {"name": "min_amount", "label": "Min amount (abs)", "type": "textbox", "query": "0", "current": {"text": "0", "value": "0"}, "hide": 0},
    {"name": "max_amount", "label": "Max amount (abs)", "type": "textbox", "query": "10000000", "current": {"text": "10000000", "value": "10000000"}, "hide": 0},
    {"name": "search", "label": "Label contains", "type": "textbox", "query": "", "current": {"text": "", "value": ""}, "hide": 0},
]
dash = {"uid": "finance-bank-detail", "title": "Finance - Bank detail", "tags": ["finance", "bank"], "timezone": "browser",
        "schemaVersion": 39, "version": 2, "refresh": "", "time": {"from": "now-13M", "to": "now"},
        "description": "Every operation, filterable by person, account, category, subcategory, necessity, kind, decided-by, amount, label and date; plus the review queue of what no rule explains yet. Postgres: gold.bank_transaction_detail.",
        "panels": P, "templating": {"list": templating}, "annotations": {"list": []}}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "bank-detail.json"
    json.dump(dash, open(out, "w"), indent=2, ensure_ascii=False)
    print(f"{len(P)} panels -> {out}")
