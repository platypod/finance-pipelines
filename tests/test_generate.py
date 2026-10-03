from platypod_pipeline import contracts
from platypod_pipeline.generate import generate


def test_generated_files_are_in_sync_with_contracts(project):
    assert generate(project, check=True) == []


def test_drift_is_detected_and_repaired(project):
    ddl = project.ddl_dir / "silver.heartbeat.sql"
    ddl.write_text(ddl.read_text() + "-- hand edit\n")
    assert generate(project, check=True) == [ddl]
    assert generate(project) == [ddl]
    assert generate(project, check=True) == []


def test_ddl_is_qualified_idempotent_and_documented(project):
    ddl = (project.ddl_dir / "silver.heartbeat.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS silver.heartbeat" in ddl
    assert "primary key" in ddl.lower()
    assert "numeric(12,3)" in ddl
    assert "COMMENT ON COLUMN silver.heartbeat.beat_id" in ddl


def test_dbt_yaml_uses_postgres_types_not_snowflake_ones(project):
    yml = (project.dbt_dir / "models" / "silver" / "heartbeat.yml").read_text()
    assert "numeric(12,3)" in yml and "NUMBER" not in yml


def test_bronze_has_ddl_but_no_dbt_model(project):
    assert (project.ddl_dir / "bronze.heartbeat_raw.sql").exists()
    assert not list((project.dbt_dir / "models").glob("bronze/*"))


def test_logical_server_is_bound_to_the_live_database(project, monkeypatch):
    monkeypatch.setenv("FINANCE_PG_HOST", "finance-db")
    monkeypatch.setenv("FINANCE_PG_PORT", "5432")
    from platypod_pipeline.config import Settings

    s = Settings()
    path = contracts.contract_path(s, "silver.heartbeat")
    text = contracts.bound_yaml(s, path)
    assert "host: finance-db" in text and "placeholder" not in text
    assert contracts.layer_and_table(path, s) == ("silver", "heartbeat")
