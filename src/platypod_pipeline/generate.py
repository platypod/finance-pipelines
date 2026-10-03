"""Generate every declarative artifact from the ODCS contracts.

    contracts/*.odcs.yaml  ->  generated/ddl/<dataset>.sql          (all layers)
                           ->  dbt/models/<layer>/<table>.yml        (silver, gold)

Generated files are never edited by hand; `check` regenerates in memory and
reports drift (wired into CI / `make check`).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from datacontract.data_contract import DataContract

from . import contracts
from .config import Settings

HEADER = "-- GENERATED from contracts/{dataset}.odcs.yaml by `pp generate`. Do not edit.\n"
YAML_HEADER = "# GENERATED from contracts/{dataset}.odcs.yaml by `pp generate`. Do not edit.\n"
DBT_LAYERS = {"silver", "gold"}  # bronze is a dbt *source*, not a model


def _q(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _comments(doc: dict, schema: str, table: str) -> list[str]:
    obj = doc["schema"][0]
    out = []
    if obj.get("description"):
        out.append(f"COMMENT ON TABLE {schema}.{table} IS {_q(obj['description'])};")
    for prop in obj.get("properties", []):
        parts = [prop[k] for k in ("description",) if prop.get(k)]
        if prop.get("classification"):
            parts.append(f"[classification: {prop['classification']}]")
        if parts:
            out.append(
                f"COMMENT ON COLUMN {schema}.{table}.{prop['name']} IS {_q(' '.join(parts))};"
            )
    return out


def ddl_for(settings: Settings, path: Path) -> str:
    dataset = contracts.dataset_of(path)
    schema, table = contracts.layer_and_table(path, settings)
    raw = DataContract(data_contract_file=str(path), server=settings.server_name).export(
        "sql", sql_server_type="postgres"
    )
    # The exporter emits unqualified, non-idempotent DDL; qualify and make it re-runnable.
    ddl, n = re.subn(
        rf"CREATE TABLE {re.escape(table)}\b", f"CREATE TABLE IF NOT EXISTS {schema}.{table}", raw
    )
    if n != 1:
        raise RuntimeError(f"{dataset}: expected exactly one CREATE TABLE {table}, got {n}")
    lines = [HEADER.format(dataset=dataset), ddl.strip() + "\n", *_comments(contracts.load(path), schema, table)]
    return "\n".join(lines).rstrip() + "\n"


def dbt_yaml_for(settings: Settings, path: Path) -> str:
    dataset = contracts.dataset_of(path)
    out = DataContract(data_contract_file=str(path), server=settings.server_name).export("dbt-models")
    # The exporter emits dbt *tests* too (e.g. dbt_utils for composite keys). Tests are
    # the contract gate's job (`datacontract test`) and the tables' own constraints, so
    # only model/column definitions are kept: no second copy of the rules, no dbt_utils.
    doc = yaml.safe_load(out)
    for model in doc.get("models", []):
        for key in ("data_tests", "tests"):
            model.pop(key, None)
            for col in model.get("columns", []):
                col.pop(key, None)
    return YAML_HEADER.format(dataset=dataset) + yaml.safe_dump(doc, sort_keys=False)


def targets(settings: Settings) -> dict[Path, str]:
    """Every generated file -> its expected content."""
    files: dict[Path, str] = {}
    for path in contracts.contract_files(settings):
        dataset = contracts.dataset_of(path)
        schema, table = contracts.layer_and_table(path, settings)
        files[settings.ddl_dir / f"{dataset}.sql"] = ddl_for(settings, path)
        if schema in DBT_LAYERS:
            files[settings.dbt_dir / "models" / schema / f"{table}.yml"] = dbt_yaml_for(settings, path)
    return files


def generate(settings: Settings, *, check: bool = False) -> list[Path]:
    """Write generated files (or, with check=True, return the ones that drifted)."""
    wanted = targets(settings)
    drift = [p for p, content in wanted.items() if not p.exists() or p.read_text() != content]
    if check:
        return drift
    for path in drift:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(wanted[path])
    return drift
