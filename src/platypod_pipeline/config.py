"""Runtime settings, all from the environment (12-factor; secrets come from k8s)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Project root: <repo>/finance-pipelines (the dir holding contracts/, dbt/, ...).
# Overridable so the installed package can find them inside the container.
_DEFAULT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    root: Path = field(default_factory=lambda: Path(os.environ.get("FINANCE_ROOT", _DEFAULT_ROOT)))
    pg_host: str = field(default_factory=lambda: os.environ.get("FINANCE_PG_HOST", "localhost"))
    pg_port: int = field(default_factory=lambda: int(os.environ.get("FINANCE_PG_PORT", "5432")))
    pg_database: str = field(default_factory=lambda: os.environ.get("FINANCE_PG_DATABASE", "finance"))
    # Logical server name used in every ODCS contract (`servers[].server`).
    server_name: str = "finance-pg"
    ol_namespace: str = field(default_factory=lambda: os.environ.get("OPENLINEAGE_NAMESPACE", "platypod"))
    ol_url: str | None = field(default_factory=lambda: os.environ.get("OPENLINEAGE_URL") or None)
    service_name: str = field(default_factory=lambda: os.environ.get("OTEL_SERVICE_NAME", "platypod-pipeline"))
    # Whose figures these are: the `owner` label on every published metric, which must equal
    # the person's Grafana/Authelia login (the scope shim compares them). Unset = do not publish.
    owner: str | None = field(default_factory=lambda: os.environ.get("FINANCE_OWNER") or None)
    otlp_endpoint: str | None = field(default_factory=lambda: os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or None)

    @property
    def contracts_dir(self) -> Path:
        return self.root / "contracts"

    @property
    def migrations_dir(self) -> Path:
        return self.root / "migrations"

    @property
    def ddl_dir(self) -> Path:
        return self.root / "generated" / "ddl"

    @property
    def dbt_dir(self) -> Path:
        return self.root / "dbt"

    @property
    def pg_namespace(self) -> str:
        """OpenLineage namespace for Postgres datasets (same form dbt-ol uses)."""
        return f"postgres://{self.pg_host}:{self.pg_port}"

    def credentials(self, role: str | None = None) -> tuple[str, str]:
        """(user, password) for a logical role: admin | ingest | transform | None.

        `FINANCE_PG_<ROLE>_USER/_PASSWORD` win, then the generic
        `FINANCE_PG_USER/_PASSWORD`. Least privilege is thereby configuration,
        not code: a deployment can hand every step the same role (phase 0) or
        one role per step later.
        """
        prefix = f"FINANCE_PG_{role.upper()}_" if role else None
        user = (prefix and os.environ.get(prefix + "USER")) or os.environ.get("FINANCE_PG_USER", "postgres")
        password = (prefix and os.environ.get(prefix + "PASSWORD")) or os.environ.get("FINANCE_PG_PASSWORD", "")
        return user, password

    def dsn(self, role: str | None = None) -> str:
        user, password = self.credentials(role)
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_database} "
            f"user={user} password={password}"
        )

    def dataset_name(self, qualified: str) -> str:
        """`silver.heartbeat` -> `finance.silver.heartbeat` (dbt-ol's naming)."""
        return f"{self.pg_database}.{qualified}"
