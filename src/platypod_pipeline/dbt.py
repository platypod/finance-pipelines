"""Run dbt through `dbt-ol`, nested under the wrapper's OpenLineage run.

dbt-ol parses dbt's artifacts after the run and emits the model-level jobs
(with column lineage) as children of `ctx.lineage_parent`. We point it at a
temp file transport and load the result into `ops.openlineage_event` (+ the
backend, if configured) so there is one store for all lineage.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from . import lineage, telemetry
from .runner import RunContext


def run_dbt(ctx: RunContext, *args: str, select: str | None = None) -> None:
    settings = ctx.settings
    with tempfile.TemporaryDirectory() as tmp:
        events = Path(tmp) / "ol-events.jsonl"
        config = Path(tmp) / "openlineage.yml"
        config.write_text(f"transport:\n  type: file\n  log_file_path: {events}\n  append: true\n")
        env = {
            **os.environ,
            "OPENLINEAGE_CONFIG": str(config),
            "OPENLINEAGE_NAMESPACE": settings.ol_namespace,
            "OPENLINEAGE_PARENT_ID": f"{settings.ol_namespace}/{ctx.job}/{ctx.run_id}",
            "FINANCE_PG_HOST": settings.pg_host,
            "FINANCE_PG_PORT": str(settings.pg_port),
            "FINANCE_PG_DATABASE": settings.pg_database,
        }
        if tp := telemetry.current_traceparent():
            env["TRACEPARENT"] = tp
        cmd = [
            "dbt-ol", *(args or ("build",)),
            "--project-dir", str(settings.dbt_dir),
            "--profiles-dir", str(settings.dbt_dir),
            "--target-path", str(Path(tmp) / "target"),
            "--log-path", str(Path(tmp) / "logs"),
        ]
        if select:
            cmd += ["--select", *select.split()]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        print(proc.stdout[-4000:], flush=True)
        if events.exists():
            for line in events.read_text().splitlines():
                payload = json.loads(line)
                lineage.store_event(settings, payload)
        if proc.returncode != 0:
            raise RuntimeError(f"dbt-ol failed (exit {proc.returncode}):\n{proc.stdout[-3000:]}\n{proc.stderr[-1500:]}")
