"""Bank statement ingestion: CSV export -> accounts + rows (bronze), then classification and gold in dbt."""

# Bump on any parser change; the bank CronJob re-parses files stored by an older version.
PARSER_VERSION = "1.0.0"
