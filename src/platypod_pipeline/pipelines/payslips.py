"""Payslips: PDFs on the NAS -> bronze (as parsed) -> silver/gold (dbt) -> contract gate.

    PAYSLIPS_DIR       root holding <year>/<YYYYMM>.pdf (read-only mount)   [/data/payslips]
    PAYSLIPS_REPARSE   "1" re-parses files whose stored parser_version is older

Files are keyed by SHA-256, so re-running is a no-op until a new payslip shows up.
Nothing personal beyond the finance figures is extracted: no social-security number,
IBAN or address ever reaches the database (the parsers do not read them).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .. import db
from ..config import Settings
from ..dbt import run_dbt
from ..lineage import Dataset
from ..publish import publish
from ..payslips import PARSER_VERSION
from ..payslips.parse import parse_pdf
from ..runner import RunContext, pipeline_run

log = logging.getLogger(__name__)
JOB = "finance.payslips"
NAME = re.compile(r"^(\d{4})(\d{2})\.pdf$")
OUTPUTS = ["bronze.payslip_file", "bronze.payslip_line_raw", "silver.payslip", "silver.payslip_line",
           "gold.income_monthly", "gold.contributions_monthly", "gold.payslip_measure"]
LINE_COLS = ("section", "label", "base", "rate", "employee_gain", "employee_deduct",
             "employer_base", "employer_rate", "employer_amount")


class NeedsAttention(RuntimeError):
    """Some payslip has no successfully parsed file. Raised AFTER everything good has been loaded and
    published, so the run is marked failed (Job, ops.pipeline_run, OpenLineage FAIL) without losing data."""


UNRESOLVED_SQL = """
    select to_char(f.period, 'YYYY-MM'), f.status, coalesce(f.warnings ->> 0, '')
    from bronze.payslip_file f
    where f.status <> 'parsed'
      and not exists (select 1 from bronze.payslip_file g where g.period = f.period and g.status = 'parsed')
    order by f.period
"""


def discover(root: Path) -> list[tuple[Path, str]]:
    """(path, 'YYYY-MM') for every payslip PDF; skips macOS `._*` and Synology `@eaDir` debris."""
    found = []
    for path in sorted(root.glob("*/*.pdf")):
        if path.name.startswith("._") or "@eaDir" in path.parts:
            continue
        if m := NAME.match(path.name):
            found.append((path, f"{m.group(1)}-{m.group(2)}"))
    return found


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_file(settings: Settings, ctx: RunContext, root: Path, path: Path, period: str, digest: str) -> str:
    """Parse one PDF and write it to bronze in one transaction; returns its status."""
    stat = path.stat()
    parsed, source = parse_pdf(path, period)
    if parsed is None:
        layout, status, summary, warnings, lines = "unknown", "unsupported", {}, ["no known layout"], []
    else:
        layout, summary, warnings, lines = parsed.layout, parsed.summary, parsed.warnings, parsed.lines
        status = "parsed" if not warnings else "review"
    with db.connect(settings, "ingest", autocommit=False) as conn:
        conn.execute("delete from bronze.payslip_line_raw where sha256 = %s", (digest,))
        conn.execute("delete from bronze.payslip_file where sha256 = %s", (digest,))
        conn.execute(
            "insert into bronze.payslip_file (sha256, source_path, size_bytes, file_mtime, period, layout, source,"
            " parser_version, status, warnings, summary, _run_id, _ingested_at)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, now())",
            (digest, str(path.relative_to(root)), stat.st_size, datetime.fromtimestamp(stat.st_mtime, timezone.utc),
             f"{period}-01", layout, source, PARSER_VERSION, status, json.dumps(warnings), json.dumps(summary), ctx.run_id),
        )
        for line in lines:
            conn.execute(
                f"insert into bronze.payslip_line_raw (sha256, line_no, {', '.join(LINE_COLS)}, _run_id, _ingested_at)"
                f" values (%s, %s, {', '.join(['%s'] * len(LINE_COLS))}, %s, now())",
                (digest, line.line_no, *(getattr(line, c) for c in LINE_COLS), ctx.run_id),
            )
        conn.commit()
    ctx.add_rows("bronze.payslip_file", 1)
    ctx.add_rows("bronze.payslip_line_raw", len(lines))
    return status


def run(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    root = Path(os.environ.get("PAYSLIPS_DIR", "/data/payslips"))
    reparse = os.environ.get("PAYSLIPS_REPARSE") == "1"
    source = Dataset(f"{root}", namespace=os.environ.get("PAYSLIPS_NAMESPACE", "file://payslips"))
    outputs = [Dataset(n, n) for n in OUTPUTS]
    if settings.owner and settings.otlp_endpoint:
        outputs.append(Dataset("tenant/finance", namespace="mimir://platypod"))  # published metrics
    with pipeline_run(JOB, inputs=[source], outputs=outputs, settings=settings) as run:
        with run.step("discover"):
            files = discover(root)
            with db.connect(settings, "ingest") as conn:
                known = dict(conn.execute("select sha256, parser_version from bronze.payslip_file").fetchall())
            todo = []
            for path, period in files:
                digest = sha256(path)
                if digest not in known or (reparse and known[digest] != PARSER_VERSION):
                    todo.append((path, period, digest))
            log.info("%d payslip files found, %d to load", len(files), len(todo))
        statuses: dict[str, list[str]] = {}
        with run.step("parse"):
            for path, period, digest in todo:
                status = load_file(settings, run, root, path, period, digest)
                statuses.setdefault(status, []).append(period)
                log.info("%s: %s", period, status)
        for status in ("review", "unsupported"):
            if statuses.get(status):
                log.warning("%d payslip(s) %s, excluded from silver: %s", len(statuses[status]), status, ", ".join(statuses[status]))
        with run.step("transform"):
            run_dbt(run, "build", select="payslip payslip_line income_monthly contributions_monthly payslip_measure")
            with db.connect(settings, "transform") as conn:
                for table in OUTPUTS[2:]:
                    run.rows[table] = conn.execute(f"select count(*) from {table}").fetchone()[0]
        with run.step("contract"):
            for ds in OUTPUTS:
                run.check_contract(ds)
        # Only after the gate: nothing that failed its contracts is ever published.
        if settings.owner and settings.otlp_endpoint:
            with run.step("publish"):
                publish(settings)
        else:
            log.info("FINANCE_OWNER / OTEL_EXPORTER_OTLP_ENDPOINT not set: skipping the Mimir publish step")
        # A `review` file at the END of the series is not a gap, so the contract's no-missing-month rule stays
        # silent about it: fail the run explicitly (a period is resolved once ANY file of it parsed).
        with db.connect(settings, "ingest") as conn:
            unresolved = conn.execute(UNRESOLVED_SQL).fetchall()
        if unresolved:
            raise NeedsAttention(
                f"{len(unresolved)} payslip(s) could not be parsed and are NOT in the dashboards: "
                + "; ".join(f"{p} ({st}): {w[:120]}" for p, st, w in unresolved)
            )
