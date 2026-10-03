"""OpenTelemetry setup: traces, metrics and logs over OTLP/HTTP.

Export is enabled by the standard `OTEL_EXPORTER_OTLP_ENDPOINT` env var (in the
cluster: the observability OTel gateway). Without it everything still works,
telemetry just goes nowhere — a pipeline must never fail because the collector
is down. `PP_OTEL_CONSOLE=1` prints spans to stdout (local debugging).
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.context import Context
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_providers: dict[str, object] = {}
_last_success: dict[str, float] = {}


def setup(service_name: str) -> None:
    """Idempotent. Installs global tracer/meter/logger providers."""
    if _providers:
        return
    resource = Resource.create({"service.name": service_name, "service.namespace": "platypod"})
    exporting = bool(
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )

    tracer_provider = TracerProvider(resource=resource)
    meter_readers = []
    logger_provider = LoggerProvider(resource=resource)
    if exporting:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        meter_readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=15000))
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    if os.environ.get("PP_OTEL_CONSOLE"):
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    meter_provider = MeterProvider(resource=resource, metric_readers=meter_readers)
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)
    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(LoggingHandler(logger_provider=logger_provider))
    logging.getLogger().setLevel(logging.INFO)

    meter = metrics.get_meter("platypod.pipeline")
    meter.create_observable_gauge(
        "pipeline_last_success_timestamp_seconds",
        callbacks=[lambda _o: [metrics.Observation(ts, {"job": job}) for job, ts in _last_success.items()]],
        unit="s",
        description="Unix time of the last successful run, per job (freshness alerts)",
    )
    _providers.update(tracer=tracer_provider, meter=meter_provider, logger=logger_provider)


_instruments: dict[str, object] = {}


def _instrument(kind: str, name: str, **kw):
    if name not in _instruments:
        meter = metrics.get_meter("platypod.pipeline")
        _instruments[name] = getattr(meter, kind)(name, **kw)
    return _instruments[name]


def record_run(job: str, *, status: str, seconds: float, rows_written: int, violations: int) -> None:
    attrs = {"job": job, "status": status}
    _instrument("create_histogram", "pipeline_run_duration_seconds", unit="s").record(seconds, attrs)
    _instrument("create_counter", "pipeline_rows_written").add(rows_written, {"job": job})
    _instrument("create_counter", "pipeline_contract_violations").add(violations, {"job": job})
    _instrument("create_counter", "pipeline_runs").add(1, attrs)
    if status == "success":
        _last_success[job] = time.time()


def parent_context() -> Context | None:
    """Continue a trace handed over by an orchestrator via TRACEPARENT, if any."""
    traceparent = os.environ.get("TRACEPARENT")
    if not traceparent:
        return None
    return TraceContextTextMapPropagator().extract({"traceparent": traceparent})


def current_traceparent() -> str | None:
    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier)
    return carrier.get("traceparent")


def trace_id_hex() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return f"{ctx.trace_id:032x}" if ctx.is_valid else None


@contextmanager
def span(name: str, *, context: Context | None = None, **attributes) -> Iterator[trace.Span]:
    with trace.get_tracer("platypod.pipeline").start_as_current_span(
        name, context=context, attributes=attributes
    ) as s:
        yield s


def shutdown() -> None:
    """Flush everything; call before the process exits (short-lived Jobs)."""
    for key in ("tracer", "meter", "logger"):
        provider = _providers.get(key)
        if provider is not None:
            try:
                provider.force_flush()
                provider.shutdown()
            except Exception:  # noqa: BLE001 - telemetry must never break the job
                pass
    _providers.clear()
    _instruments.clear()
