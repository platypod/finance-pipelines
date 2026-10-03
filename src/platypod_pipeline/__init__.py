"""Instrumented, contract-bound pipelines (OpenTelemetry + OpenLineage + ODCS)."""

from .runner import ContractViolation, RunContext, pipeline_run

__all__ = ["ContractViolation", "RunContext", "pipeline_run"]
