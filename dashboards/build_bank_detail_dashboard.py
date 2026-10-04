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
FILTER = ("person in ($person) AND account in ($account) AND category in ($category) "
          "AND label ILIKE '%${search}%' AND $__timeFilter(spend_date)")


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
P = [
    stat("Operations to review", 0, f"SELECT count(*) AS \"to review\" FROM {T} WHERE needs_review", "none",
         "Uncategorized, or a transfer to/from another person that no rule or override has explained."),
    stat("Amount to review (EUR, absolute)", 6, f"SELECT coalesce(sum(abs(amount)), 0) AS amount FROM {T} WHERE needs_review", "currencyEUR",
         "Sum of the absolute amounts: money out and in."),
    stat("Classified by rule or override", 12,
         f"SELECT round(100.0 * count(*) FILTER (WHERE source <> 'default') / nullif(count(*), 0), 1) AS \"%\" FROM {T}", "none",
         "Share of operations decided by a rule, an override or a paired internal transfer."),
    stat("Operations", 18, f"SELECT count(*) AS operations FROM {T}", "none", "All de-duplicated operations loaded."),
    panel("table", "Review queue: what no rule explains yet (largest first)", 0, 4, 24, 10, [sql(
        f"SELECT spend_date AS date, account, person, amount, label, family, category, subcategory, txn_id FROM {T} "
        "WHERE needs_review ORDER BY abs(amount) DESC")], "short", table_opts, money,
        desc="Fix it once for all similar operations with a rule in rules.yaml (match on the label), or for this one "
             "operation with a line in overrides.csv (use txn_id). Both live next to the statements; then run `make sync-bank`."),
    panel("table", "Where the money goes: top labels not yet covered by a rule", 0, 14, 12, 9, [sql(
        f"SELECT label, count(*) AS operations, sum(amount) AS amount FROM {T} WHERE needs_review AND amount < 0 "
        "GROUP BY label ORDER BY sum(amount) LIMIT 30")], "short", table_opts, money,
        desc="Grouped by cleaned label: a good rule candidate has many operations or a large amount."),
    panel("barchart", "How operations were classified", 12, 14, 12, 9, [sql(
        f"SELECT source, count(*) AS operations FROM {T} GROUP BY source ORDER BY 2 DESC")], "short",
        {"legend": {"showLegend": False}, "xField": "source"},
        desc="rule, override, transfer_pair (own-account transfers) or default (nothing matched)."),
    panel("table", "Transactions", 0, 23, 24, 14, [sql(
        f"SELECT spend_date AS date, account, person, amount, label, category, subcategory, necessity, source, rule_id, txn_id "
        f"FROM {T} WHERE {FILTER} ORDER BY spend_date DESC, abs(amount) DESC")], "short", table_opts, money,
        desc="Filter with the variables above (person, account, category, label search) and the time range (on the reporting date)."),
]


def qvar(name, label, query):
    return {"name": name, "label": label, "type": "query", "datasource": DS, "query": query, "definition": query,
            "includeAll": True, "multi": True, "current": {"text": "All", "value": "$__all"}, "refresh": 2, "sort": 1, "hide": 0}


templating = [
    qvar("person", "Person", f"SELECT DISTINCT person FROM {T} ORDER BY 1"),
    qvar("account", "Account", f"SELECT DISTINCT account FROM {T} WHERE person IN ($person) ORDER BY 1"),
    qvar("category", "Category", f"SELECT DISTINCT category FROM {T} ORDER BY 1"),
    {"name": "search", "label": "Label contains", "type": "textbox", "query": "", "current": {"text": "", "value": ""}, "hide": 0},
]
dash = {"uid": "finance-bank-detail", "title": "Finance - Bank detail", "tags": ["finance", "bank"], "timezone": "browser",
        "schemaVersion": 39, "version": 1, "refresh": "", "time": {"from": "now-13M", "to": "now"},
        "description": "Operations with their category, and the review queue of what no rule explains yet. Postgres: gold.bank_transaction_detail.",
        "panels": P, "templating": {"list": templating}, "annotations": {"list": []}}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "bank-detail.json"
    json.dump(dash, open(out, "w"), indent=2, ensure_ascii=False)
    print(f"{len(P)} panels -> {out}")
