"""Publish gold figures (payslips, bank) as OTLP gauges so the *shared* Grafana can show them.

Postgres stays the source of truth. The published copy lives in the `finance` Mimir
tenant, where every series carries `owner=<login>`: the observability scope shim then
shows each person only their own series (the same mechanism Jellyfin uses). Admins see
all owners by design of that shim.

Facts that shape this module:
- One sample per payslip and view (month / year to date / rolling 12 months), stamped mid-month (the 15th, 12:00 UTC). Prometheus windows
  are left-open, so a sample exactly at a month boundary would fall out of
  `sum_over_time(x[$__range])` for calendar ranges; mid-month never does.
- Samples carry explicit historical timestamps, which the Python OTel SDK cannot emit,
  hence raw OTLP protobuf. The `finance` tenant accepts old samples (per-tenant Mimir
  limits); the gateway routes `finance.*` to that tenant and drops any finance series
  without a concrete owner.
- Mimir rejects a different value for an already-stored (series, timestamp), so a
  corrected historical figure cannot overwrite the old one: wipe the tenant and republish
  (see stack/src/finance/README.md). Re-publishing identical values is harmless.
- OTLP success means the gateway accepted the request, not that Mimir stored it.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from decimal import Decimal

import requests
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource

from . import db
from .config import Settings

log = logging.getLogger(__name__)

# From gold.income_monthly: the ratios, the printed withholding rate and the leave balances. (Every flow
# figure comes from gold.payslip_measure below, in its three views.)
INCOME_METRICS: dict[str, tuple[str, str]] = {
    "finance.payslip.tax_rate_percent": ("%", "pas_rate"),
    "finance.payslip.net_to_gross_ratio": ("1", "net_to_gross"),
    "finance.payslip.contributions_to_gross_ratio": ("1", "contributions_to_gross"),
}
LEAVE_METRIC = "finance.payslip.leave_days"  # {kind="cp"|"rtt"}
LEAVE_COLUMNS = {"cp": "leave_cp_balance", "rtt": "leave_rtt_balance"}

# From gold.payslip_measure. One metric per measure and view, named
#   finance.payslip.[ytd_|r12_]<measure>_eur        (flows; pay_element{element}, contribution{category,side})
# so that a dashboard can switch Monthly / Year to date / Rolling 12 months by the metric-name prefix.
FLOW_MEASURES = (
    "gross", "net_before_tax", "net_paid", "tax_withheld", "taxable_net",
    "employee_contributions", "employer_contributions", "employer_cost",
)
VIEWS = (("", "value"), ("ytd_", "ytd_value"), ("r12_", "r12_value"))  # (name prefix, gold column)


def sample_time(period: dt.date) -> int:
    """Mid-month, 12:00 UTC, in nanoseconds."""
    ts = dt.datetime(period.year, period.month, 15, 12, tzinfo=dt.timezone.utc)
    return int(ts.timestamp()) * 1_000_000_000


def _kv(key: str, value: str) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(string_value=value))


def _check_owner(owner: str) -> None:
    if not owner or owner.startswith("_"):
        raise ValueError(f"refusing to publish with owner={owner!r}: must be a login or group:<name>")


class _Builder:
    def __init__(self):
        self.request = ExportMetricsServiceRequest()
        rm = self.request.resource_metrics.add()
        rm.resource.CopyFrom(Resource(attributes=[_kv("service.name", "finance-payslips")]))
        self.scope = rm.scope_metrics.add()
        self.scope.scope.name = "platypod.finance"
        self.metrics: dict[str, object] = {}
        self.points = 0
        self.skipped_future = 0

    def add(self, name: str, unit: str, period: dt.date, value, *, owner: str, **attrs: str) -> None:
        if value is None:
            return
        _check_owner(owner)
        if sample_time(period) > time.time_ns() - 3600 * 10**9:
            # Mimir rejects a sample stamped in the future (err-mimir-too-far-in-future) and the gateway then drops the
            # whole request: a month whose mid-month stamp has not come yet is simply not published yet.
            self.skipped_future += 1
            return
        metric = self.metrics.get(name)
        if metric is None:
            metric = self.scope.metrics.add()
            metric.name, metric.unit = name, unit
            self.metrics[name] = metric
        dp = metric.gauge.data_points.add()
        dp.time_unix_nano = sample_time(period)
        dp.as_double = float(value if not isinstance(value, Decimal) else float(value))
        dp.attributes.append(_kv("owner", owner))
        for k, v in attrs.items():
            dp.attributes.append(_kv(k, v))
        self.points += 1


def build_request(owner: str, income: list[dict], measures: list[dict]) -> tuple[ExportMetricsServiceRequest, int]:
    """Payslips. income: gold.income_monthly rows; measures: gold.payslip_measure rows.

    A payslip is personal: the series' owner (who may see it) and its person (whose it is, the dashboards'
    filter) are both the login of the person it belongs to.
    """
    _check_owner(owner)
    b = _Builder()
    who = {"owner": owner, "person": owner}
    for row in income:
        for name, (unit, column) in INCOME_METRICS.items():
            b.add(name, unit, row["period"], row[column], **who)
        for kind, column in LEAVE_COLUMNS.items():
            b.add(LEAVE_METRIC, "d", row["period"], row[column], kind=kind, **who)
    for row in measures:
        measure, item, side = row["measure"], row["item"], row["side"]
        if measure in FLOW_MEASURES:
            base, attrs = f"{measure}_eur", {}
        elif measure == "pay_element":
            base, attrs = "pay_element_eur", {"element": item}
        elif measure == "contribution":
            base, attrs = "contribution_eur", {"category": item, "side": side}
        else:
            raise ValueError(f"unknown measure {measure!r} in gold.payslip_measure")
        for prefix, column in VIEWS:
            b.add(f"finance.payslip.{prefix}{base}", "EUR", row["period"], row[column], **who, **attrs)
    return b.request, b.points


SETTLE_DAYS = 5  # a month is published once it has been over for this long: card operations still land after month end


def settled(period: dt.date, today: dt.date | None = None) -> bool:
    """Samples are immutable in Mimir (a later, different value for the same timestamp is rejected), so a month is only
    published when it is complete and its late-booked operations have arrived."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    nxt = (period.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    return today >= nxt + dt.timedelta(days=SETTLE_DAYS)


def build_bank_request(measures: list[dict], today: dt.date | None = None) -> tuple[ExportMetricsServiceRequest, int]:
    """Bank. measures: gold.bank_measure rows. Each row carries its own owner (visibility) and person.
    Only settled months are published (see `settled`)."""
    b = _Builder()
    for row in measures:
        if not settled(row["period"], today):
            continue
        measure, who = row["measure"], {"owner": row["owner"], "person": row["person"]}
        if measure == "balance":
            b.add("finance.bank.balance_eur", "EUR", row["period"], row["value"], account=row["item1"], **who)
            continue
        if measure in ("spend", "income"):
            base, attrs = f"{measure}_eur", {"category": row["item1"], "subcategory": row["item2"]}
        elif measure == "spend_necessity":
            base, attrs = "spend_necessity_eur", {"necessity": row["item1"]}
        else:
            raise ValueError(f"unknown measure {measure!r} in gold.bank_measure")
        for prefix, column in VIEWS:
            b.add(f"finance.bank.{prefix}{base}", "EUR", row["period"], row[column], **who, **attrs)
    return b.request, b.points


def _rows(settings: Settings, sql: str) -> list[dict]:
    with db.connect(settings, "transform") as conn:
        cur = conn.execute(sql)
        names = [d.name for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def _send(settings: Settings, request: ExportMetricsServiceRequest, points: int, what: str, timeout: float) -> int:
    if not settings.otlp_endpoint:
        raise RuntimeError("OTEL_EXPORTER_OTLP_ENDPOINT is not set")
    url = settings.otlp_endpoint.rstrip("/") + "/v1/metrics"
    resp = requests.post(url, data=request.SerializeToString(), headers={"Content-Type": "application/x-protobuf"}, timeout=timeout)
    resp.raise_for_status()
    reply = ExportMetricsServiceResponse()
    reply.ParseFromString(resp.content)
    if reply.partial_success.rejected_data_points:
        raise RuntimeError(
            f"gateway rejected {reply.partial_success.rejected_data_points} of {points} data points: "
            f"{reply.partial_success.error_message}"
        )
    log.info("published %d %s data points (%d metrics)", points, what, len(request.resource_metrics[0].scope_metrics[0].metrics))
    return points


def publish_payslips(settings: Settings, *, timeout: float = 30.0) -> int:
    """Read the payslip gold tables, push to the gateway. Returns the number of data points sent."""
    if not settings.owner:
        raise RuntimeError("FINANCE_OWNER is not set")
    income = _rows(settings, "select * from gold.income_monthly order by period")
    measures = _rows(settings, "select * from gold.payslip_measure order by period, measure, item, side")
    request, points = build_request(settings.owner, income, measures)
    return _send(settings, request, points, f"payslip (owner {settings.owner})", timeout)


publish = publish_payslips  # historical name


def publish_bank(settings: Settings, *, timeout: float = 30.0) -> int:
    measures = _rows(settings, "select * from gold.bank_measure order by period, measure, person, item1, item2")
    request, points = build_bank_request(measures)
    return _send(settings, request, points, "bank", timeout)
