"""Payslip extraction: PDF -> words -> layout-specific parser -> raw summary + lines."""

# Bump on any parser change; the payslips CronJob re-parses files stored by an older version.
# 1.1.0: a minus sign in front of a thousands-grouped amount (`- 1 020,83`) was dropped.
# 1.2.0: the 2026-09 template (period as "Du dd/mm/yyyy au dd/mm/yyyy", employee header block repeated on
#        continuation pages, rotated margin glyphs at a new x) -- its first payslip was rejected.
PARSER_VERSION = "1.2.0"
