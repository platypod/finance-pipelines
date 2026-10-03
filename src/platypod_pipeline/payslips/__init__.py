"""Payslip extraction: PDF -> words -> layout-specific parser -> raw summary + lines."""

# Bump on any parser change; `PAYSLIPS_REPARSE=1` re-parses files stored by an older version.
PARSER_VERSION = "1.0.1"
