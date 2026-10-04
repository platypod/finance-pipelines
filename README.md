# finance-pipelines

Instrumented, contract-bound data pipelines for the platypod finance platform.
Design: [`../docs/plans/finance-data-platform.md`](../docs/plans/finance-data-platform.md).
Deployed by [`stack/src/finance`](../stack/src/finance/README.md).

```
contracts/*.odcs.yaml   ODCS contracts — THE source of truth (hand-written)
migrations/*.sql        schemas, grants, ops tables (hand-written plumbing)
dbt/models/**/*.sql     transformation logic, one SELECT per dataset (hand-written)
generated/ddl/*.sql     \
dbt/models/**/*.yml     / GENERATED from the contracts — never edited (`make check` fails on drift)
src/platypod_pipeline/  the wrapper: OTel + OpenLineage + contract tests around every job
```

## How a pipeline runs

`pp run <name>` → `pipeline_run()` opens an OTel trace, emits OpenLineage
START/COMPLETE/FAIL (stored in `ops.openlineage_event`, optionally POSTed to
`OPENLINEAGE_URL`), logs the run in `ops.pipeline_run`, runs steps, runs `dbt-ol`
nested under its OpenLineage run, then `datacontract test`s the outputs; a violation
fails the run. Orchestrator-agnostic: CronJob, Kestra or a shell all work (pass
`TRACEPARENT` to continue a trace).

## Payslips (phase 1)

`pp run payslips` reads `<year>/<YYYYMM>.pdf` under `PAYSLIPS_DIR` (read-only NAS mount),
parses each new file (SHA-256 key) into `bronze.payslip_file` / `bronze.payslip_line_raw`,
runs the dbt models (`silver.payslip`, `silver.payslip_line`, `gold.income_monthly`,
`gold.contributions_monthly`) and gates on the contracts. Dashboard:
`pp run payslips` ends with a **publish** step (`publish.py`): once the contracts pass, the gold figures
are pushed as `finance.payslip.*` gauges (one sample per payslip, mid-month, `owner=$FINANCE_OWNER`) to the
OTel gateway, which routes them to the `finance` Mimir tenant, where the shared Grafana shows them per user
(dashboard: `stack/src/observability/files/dashboards/finance/payslips.json`, PromQL). The step is skipped
unless `FINANCE_OWNER` and `OTEL_EXPORTER_OTLP_ENDPOINT` are set. An optional SQL dashboard for a dedicated
Grafana lives in `stack/src/finance/files/dashboards/payslips.json`. Metric catalogue: `INCOME_METRICS`,
`LEAVE_METRIC`, `CONTRIBUTION_METRIC` in `publish.py` (names, units, source gold columns; guarded by a test).

Parsing facts (79 files, 2020-02 → 2026-08, one employer):
- **Two layouts**: `silae` (66 files, incl. multi-page ones whose table continues over
  pages) and `modern` (10 files since 2025-11; page 1 is an unreadable visual summary, the
  table is on pages 2+). Numbers are bucketed into columns by their right edge, so the
  parsers work on word *positions* (`payslips/words.py`), not flowing text.
- **5 files have no text layer** (printed to PDF as outlines): OCR via `pdftoppm` +
  `tesseract` (image installs `fra`), retried with other dpi/psm until the arithmetic
  checks pass (one needed it). Without the binaries such a file is `needs_ocr`.
- **Self-checking**: every file must satisfy period == file name, contribution lines sum
  to the printed totals, and `net paid = net before tax - PAS`. A failing file is stored
  as `status='review'` and kept out of silver. A review file in the middle of the series trips the silver "no
  missing month" rule; one at the END is not a gap, so the run explicitly fails (`NeedsAttention`) after loading
  and publishing everything else, until a parsed file exists for that period. Year-to-date gross printed on the
  payslips matches the figure recomputed from the months for all 74 payslips that print it.
- **Privacy**: parsers read only finance fields. NIR, IBAN and address are never extracted
  (they are present in the PDFs). Tests use invented numbers; the real archive is only
  touched by the optional corpus test (`PAYSLIPS_DIR=… pytest tests/test_payslips_corpus.py`).
- Parser change → bump `PARSER_VERSION`; with `PAYSLIPS_REPARSE=1` (set in the CronJob) files stored by an older version are re-parsed.
- **Gross decomposition**: the gross-section elements are classified as `base_salary`, `bonus` (primes, commissions), `time_off` (leave/RTT payouts and the absence lines that offset them, sick pay), `back_pay` (rappels), `other_pay`; the value-sharing bonus, printed outside the gross, is `bonus_exempt`. A contract rule and a parser check require the elements to add up to the printed gross (this caught a dropped minus sign on `- 1 020,83` lines in two 2026 months).
- **Views**: `gold.payslip_measure` holds every flow (gross, net, tax, contributions, employer cost, pay elements, contributions by category) as the month, the calendar year to date and the rolling 12 months, dense (zero months are rows) and NULL where a window has an unprinted figure. The dashboard's View switch (`dashboards/build_payslips_dashboard.py`) selects the metric-name prefix `` / `ytd_` / `r12_`.
- Known gaps: the 5 OCR'd months lack some totals-table fields (`taxable_net`, hours,
  employer cost), and the employer cost is no longer printed after 2025-10 (columns are
  nullable). `Prime de partage de la valeur` / `Indemnités non soumises` stay in category
  `other`.

## Releasing

CI (`.github/workflows`): `test.yml` on every push/PR (contracts valid, generated files in sync, unit + integration
tests against a Postgres service); `build.yml` on a `vX.Y.Z` tag (tests first, then a multi-arch amd64/arm64 image
to `ghcr.io/platypod/finance-pipelines`, public). Release = `git tag vX.Y.Z && git push origin vX.Y.Z`, then bump
`finance.image` in `stack/apps/base/values/finance.yaml` (no Flux image automation yet).

Gotcha: a global `*.sql` gitignore silently dropped the dbt models and migrations on the first import (CI on a clean
checkout caught it); `.gitignore` now re-includes the SQL that is source.

## Dev loop

```sh
make install            # venv + editable install
make check              # contracts valid + generated files in sync
make test               # unit tests (no DB)
make test-integration   # throwaway Postgres: heartbeat + payslip pipeline (synthetic data), lineage, violations
```

Adding a dataset: write `contracts/<layer>.<name>.odcs.yaml` → `make generate` →
write `dbt/models/<layer>/<name>.sql` (`incremental`, `unique_key`,
`on_schema_change='fail'`, `full_refresh=false`; cast columns to the contract's
types) → add a pipeline under `src/platypod_pipeline/pipelines/`.

## Gotchas (found the hard way)

- The contract exporter must be given the server (`pp generate` does) or dbt types
  come out Snowflake-style (`NUMBER(10,2)`).
- Model columns must match the contract's types exactly (`numeric(12,3)`, not bare
  `numeric`) — `on_schema_change='fail'` refuses otherwise. That is the point.
- `datacontract` needs the `[postgres]` extra and `DATACONTRACT_POSTGRES_*` env (set
  by the wrapper from the role credentials).
- DDL is create-only: a changed contract on an existing table needs a hand-written
  migration (shows up as schema drift in `pp test`).
