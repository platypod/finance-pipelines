"""Bank statements: CSV exports on the NAS -> bronze -> silver (de-duplicated, classified) -> gold -> published.

    BANK_DIR           statements + the private accounts.yaml / rules.yaml / overrides.csv    [/data/bank-statements]
    BANK_REPARSE       "1" re-parses files whose stored parser_version is older

Files are keyed by SHA-256 and exports overlap (rolling window), so re-running is cheap and the same operation is
never counted twice. Only the last four digits of an account number are kept; holder names are never read.
Row-level labels stay in Postgres: Mimir only ever receives monthly aggregates.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .. import db
from ..bank import PARSER_VERSION, reference
from ..bank.parse import parse_statement
from ..config import Settings
from ..dbt import run_dbt
from ..lineage import Dataset
from ..publish import publish_bank
from ..runner import RunContext, pipeline_run
from .payslips import NeedsAttention

log = logging.getLogger(__name__)
JOB = "finance.bank"
NOT_STATEMENTS = {"overrides.csv"}
OUTPUTS = ["bronze.bank_file", "bronze.bank_transaction_raw", "silver.bank_account", "silver.bank_rule", "silver.bank_override",
           "silver.bank_balance", "silver.bank_transaction", "silver.bank_transaction_category", "gold.bank_measure"]
MODELS = "bank_balance bank_transaction bank_transaction_category bank_measure"

UNRESOLVED_SQL = """
    select f.source_path, f.status, coalesce(f.warnings ->> 0, '')
    from bronze.bank_file f where f.status <> 'parsed' order by f.source_path
"""
UNMAPPED_SQL = """
    select distinct e ->> 'kind', e ->> 'last4'
    from bronze.bank_file f cross join lateral jsonb_array_elements(f.accounts) e
    where f.status = 'parsed'
      and not exists (select 1 from silver.bank_account a where a.bank = f.bank and a.last4 = e ->> 'last4')
    order by 2
"""


def discover(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("*.csv") if not p.name.startswith("._") and p.name not in NOT_STATEMENTS)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_file(settings: Settings, ctx: RunContext, root: Path, path: Path, digest: str) -> str:
    stat = path.stat()
    parsed = parse_statement(path)
    if parsed is None:
        bank, status, warnings, accounts, exported_on = "unknown", "unsupported", ["not a known bank export"], [], None
    else:
        bank, warnings, exported_on = parsed.bank, parsed.warnings, parsed.exported_on
        status = "parsed" if not warnings else "review"
        accounts = [
            {"kind": a.kind, "last4": a.last4, "digits": a.number_digits, "balance": a.balance, "balance_date": a.balance_date,
             "period_from": a.period_from, "period_to": a.period_to, "rows": len(a.rows)}
            for a in parsed.accounts
        ]
    rows = [(a.last4, r) for a in (parsed.accounts if parsed else []) for r in a.rows]
    exported = datetime.strptime(exported_on, "%d/%m/%Y").date() if exported_on else None
    with db.connect(settings, "ingest", autocommit=False) as conn:
        conn.execute("delete from bronze.bank_transaction_raw where sha256 = %s", (digest,))
        conn.execute("delete from bronze.bank_file where sha256 = %s", (digest,))
        conn.execute(
            "insert into bronze.bank_file (sha256, source_path, size_bytes, file_mtime, bank, exported_on, parser_version,"
            " status, warnings, accounts, _run_id, _ingested_at) values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, now())",
            (digest, str(path.relative_to(root)), stat.st_size, datetime.fromtimestamp(stat.st_mtime, timezone.utc), bank, exported,
             PARSER_VERSION, status, json.dumps(warnings), json.dumps(accounts), ctx.run_id),
        )
        with conn.cursor() as cur:
            cur.executemany(
                "insert into bronze.bank_transaction_raw (sha256, account_ref, line_no, booking_date, value_date, label, debit,"
                " credit, _run_id, _ingested_at) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
                [(digest, ref, r.line_no, r.booking_date, r.value_date, r.label, r.debit or None, r.credit or None, ctx.run_id)
                 for ref, r in rows],
            )
        conn.commit()
    ctx.add_rows("bronze.bank_file", 1)
    ctx.add_rows("bronze.bank_transaction_raw", len(rows))
    return status


def run(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    root = Path(os.environ.get("BANK_DIR", "/data/bank-statements"))
    reparse = os.environ.get("BANK_REPARSE") == "1"
    outputs = [Dataset(n, n) for n in OUTPUTS]
    if settings.otlp_endpoint:
        outputs.append(Dataset("tenant/finance", namespace="mimir://platypod"))
    with pipeline_run(JOB, inputs=[Dataset(str(root), namespace=os.environ.get("BANK_NAMESPACE", "file://bank-statements"))],
                      outputs=outputs, settings=settings) as run:
        with run.step("reference"):
            tax = reference.load_taxonomy(settings)
            accounts = reference.load_accounts(root / "accounts.yaml")
            rules = reference.load_rules(root / "rules.yaml", settings.root / "reference" / "default-rules.yaml", tax)
            overrides = reference.load_overrides(root / "overrides.csv", tax)
            reference.write_reference(settings, accounts, rules, overrides)
            log.info("reference: %d accounts, %d rules (%d private), %d overrides", len(accounts), len(rules),
                     sum(r["origin"] == "private" for r in rules), len(overrides))
            run.add_rows("silver.bank_account", len(accounts))
        with run.step("discover"):
            files = discover(root)
            with db.connect(settings, "ingest") as conn:
                known = dict(conn.execute("select sha256, parser_version from bronze.bank_file").fetchall())
            todo = []
            for path in files:
                digest = sha256(path)
                if digest not in known or (reparse and known[digest] != PARSER_VERSION):
                    todo.append((path, digest))
            log.info("%d statement files found, %d to load", len(files), len(todo))
        with run.step("parse"):
            for path, digest in todo:
                log.info("%s: %s", path.name, load_file(settings, run, root, path, digest))
        with run.step("transform"):
            run_dbt(run, "build", select=MODELS)
            with db.connect(settings, "transform") as conn:
                for table in OUTPUTS[5:]:
                    run.rows[table] = conn.execute(f"select count(*) from {table}").fetchone()[0]
        with run.step("contract"):
            for ds in OUTPUTS:
                run.check_contract(ds)
        if settings.otlp_endpoint:
            with run.step("publish"):
                publish_bank(settings)
        else:
            log.info("OTEL_EXPORTER_OTLP_ENDPOINT not set: skipping the Mimir publish step")
        with db.connect(settings, "transform") as conn:  # needs bronze + silver (ingest has no silver access)
            unresolved = conn.execute(UNRESOLVED_SQL).fetchall()
            unmapped = conn.execute(UNMAPPED_SQL).fetchall()
        problems = [f"{p} ({st}): {w[:120]}" for p, st, w in unresolved]
        problems += [f"account …{last4} ({kind}) is in the statements but not in accounts.yaml: its operations are NOT loaded"
                     for kind, last4 in unmapped]
        if problems:
            raise NeedsAttention("; ".join(problems))
