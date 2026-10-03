# finance-pipelines — context for Claude

Read [README.md](README.md) first, then the design in
[../docs/plans/finance-data-platform.md](../docs/plans/finance-data-platform.md).

Rules:
- **ODCS contracts in `contracts/` are the only declarative source of truth.** Never
  hand-edit `generated/` or `dbt/models/**/*.yml` — change the contract, run
  `make generate`. `make check` must pass.
- Every job goes through `pipeline_run()` (telemetry + lineage + contract gate); do
  not write jobs that bypass it.
- dbt only fills tables the contract created: `incremental`, `full_refresh=false`,
  `on_schema_change='fail'`; model columns cast to the contract's types.
- Never put real financial data or credentials in the repo or in test fixtures.
