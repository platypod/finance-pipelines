"""Payslip extraction: PDF -> words -> layout-specific parser -> raw summary + lines."""

# Bump on any parser change; the payslips CronJob re-parses files stored by an older version.
# 1.1.0: a minus sign in front of a thousands-grouped amount (`- 1 020,83`) was dropped.
PARSER_VERSION = "1.1.0"
