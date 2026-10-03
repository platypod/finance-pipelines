"""ODCS contract loading, binding to the live database, and testing.

Contracts in `contracts/` are the source of truth. They carry a *logical* server
(`finance-pg`); host/port/database are patched in at runtime from Settings so one
contract serves local, CI and prod. Credentials never live in a contract.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from datacontract.data_contract import DataContract

from .config import Settings


@dataclass(frozen=True)
class Check:
    name: str
    field: str | None
    passed: bool
    reason: str | None


@dataclass(frozen=True)
class ContractResult:
    dataset: str  # "silver.heartbeat"
    passed: bool
    checks: list[Check]

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]


def contract_files(settings: Settings) -> list[Path]:
    return sorted(settings.contracts_dir.glob("*.odcs.yaml"))


def dataset_of(path: Path) -> str:
    """`silver.heartbeat.odcs.yaml` -> `silver.heartbeat`."""
    return path.name.removesuffix(".odcs.yaml")


def contract_path(settings: Settings, dataset: str) -> Path:
    path = settings.contracts_dir / f"{dataset}.odcs.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no contract for dataset {dataset!r} ({path})")
    return path


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def bound_yaml(settings: Settings, path: Path) -> str:
    """Contract text with the logical server pointed at the live database."""
    doc = load(path)
    for server in doc.get("servers", []):
        if server.get("server") == settings.server_name:
            server["host"] = settings.pg_host
            server["port"] = settings.pg_port
            server["database"] = settings.pg_database
    return yaml.safe_dump(doc, sort_keys=False)


def layer_and_table(path: Path, settings: Settings) -> tuple[str, str]:
    """(schema, table) from the contract's logical server and first schema object."""
    doc = load(path)
    server = next(s for s in doc["servers"] if s["server"] == settings.server_name)
    return server["schema"], doc["schema"][0]["name"]


def schema_fields(path: Path) -> list[dict]:
    """Column list for the OpenLineage `schema` dataset facet."""
    doc = load(path)
    return [
        {"name": p["name"], "type": p.get("physicalType") or p.get("logicalType")}
        for p in doc["schema"][0].get("properties", [])
    ]


def run_test(settings: Settings, dataset: str, *, role: str = "transform") -> ContractResult:
    """`datacontract test` against the live database; one Check per executed check."""
    path = contract_path(settings, dataset)
    user, password = settings.credentials(role)
    os.environ["DATACONTRACT_POSTGRES_USERNAME"] = user
    os.environ["DATACONTRACT_POSTGRES_PASSWORD"] = password
    run = DataContract(
        data_contract_str=bound_yaml(settings, path), server=settings.server_name
    ).test()
    checks = [
        Check(
            name=c.name or c.type or "check",
            field=c.field,
            passed=str(c.result.value if hasattr(c.result, "value") else c.result) == "passed",
            reason=c.reason,
        )
        for c in run.checks
    ]
    return ContractResult(dataset=dataset, passed=run.has_passed(), checks=checks)
