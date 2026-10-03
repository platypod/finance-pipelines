"""Payslip pipeline end to end on SYNTHETIC data (the parser is stubbed; no real payslip is used)."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from payslip_fixtures import silae_page

from platypod_pipeline import db
from platypod_pipeline.config import Settings
from platypod_pipeline.migrate import migrate
from platypod_pipeline.payslips import silae
from platypod_pipeline.payslips.parse import check
from platypod_pipeline.pipelines import payslips
from platypod_pipeline.runner import ContractViolation

pytestmark = pytest.mark.integration
PERIODS = ("2099-01", "2099-02", "2099-04")  # 2099-03 is deliberately absent


@pytest.fixture(scope="module")
def settings():
    s = Settings()
    migrate(s)
    yield s
    with db.connect(s, "admin") as conn:
        for table in ("silver.payslip_line", "silver.payslip", "gold.income_monthly", "gold.contributions_monthly", "gold.payslip_measure"):
            conn.execute(f"delete from {table} where period >= '2099-01-01'")
        conn.execute("delete from bronze.payslip_line_raw where sha256 in (select sha256 from bronze.payslip_file where period >= '2099-01-01')")
        conn.execute("delete from bronze.payslip_file where period >= '2099-01-01'")


def fake_parse(path, expected_period):
    parsed = silae.parse([silae_page()])
    parsed.summary["period"] = expected_period
    if expected_period == "2099-03":
        parsed.summary["net_paid"] = "1.00"  # fails the arithmetic check -> status "review"
    check(parsed, expected_period)
    return parsed, "text"


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    for period in (*PERIODS, "2099-03"):
        year, month = period.split("-")
        d = tmp_path / year
        d.mkdir(exist_ok=True)
        (d / f"{year}{month}.pdf").write_bytes(f"not a real pdf {period}".encode())
    (tmp_path / "2099" / "._209901.pdf").write_bytes(b"AppleDouble debris")
    (tmp_path / "@eaDir" / "x").mkdir(parents=True)
    (tmp_path / "@eaDir" / "x" / "209905.pdf").write_bytes(b"Synology debris")
    monkeypatch.setenv("PAYSLIPS_DIR", str(tmp_path))
    monkeypatch.setattr(payslips, "parse_pdf", fake_parse)
    return tmp_path


def q(settings, sql, *args):
    with db.connect(settings) as conn:
        return conn.execute(sql, args).fetchall()


def test_discovery_skips_os_debris(corpus):
    found = [(p.name, period) for p, period in payslips.discover(corpus)]
    assert found == [("209901.pdf", "2099-01"), ("209902.pdf", "2099-02"), ("209903.pdf", "2099-03"), ("209904.pdf", "2099-04")]


def test_review_files_stay_out_of_silver_and_the_gap_fails_the_run(settings, corpus):
    # 2099-03 parses with warnings -> status "review" -> not in silver -> the "no missing month" rule fires
    with pytest.raises(ContractViolation) as exc:
        payslips.run(settings)
    assert any("missing" in (c.name or "") for c in exc.value.result.failures)
    statuses = dict(q(settings, "select to_char(period,'YYYY-MM'), status from bronze.payslip_file where period >= '2099-01-01'"))
    assert statuses == {"2099-01": "parsed", "2099-02": "parsed", "2099-03": "review", "2099-04": "parsed"}
    assert q(settings, "select count(*) from silver.payslip where period >= '2099-01-01'")[0][0] == 3
    (status,) = q(settings, "select status from ops.pipeline_run where job=%s order by started_at desc limit 1", payslips.JOB)[0]
    assert status == "failed"


def test_fixed_month_completes_the_series_and_reruns_are_idempotent(settings, corpus, monkeypatch):
    def good(path, period):
        parsed, src = fake_parse(path, period)
        if period == "2099-03":
            parsed.summary["net_paid"] = "2 662.68"
            parsed.warnings.clear()
            check(parsed, period)
        return parsed, src

    monkeypatch.setattr(payslips, "parse_pdf", good)
    monkeypatch.setenv("PAYSLIPS_REPARSE", "0")
    # the review row is keyed by file content; make the "fixed" file a different file
    (corpus / "2099" / "209903.pdf").write_bytes(b"corrected payslip 2099-03")
    payslips.run(settings)
    payslips.run(settings)  # second run: nothing new to load, dbt + contracts still pass

    assert q(settings, "select count(*) from silver.payslip where period >= '2099-01-01'")[0][0] == 4
    lines = q(settings, "select category, count(*) from silver.payslip_line where period = '2099-01-01' group by 1 order by 1")
    assert dict(lines) == {"base_salary": 1, "bonus": 1, "csg_crds": 1, "health": 1, "meal_vouchers": 1, "retirement": 1}
    (gross, net, ytd) = q(settings, "select gross_amount, net_paid, ytd_gross from gold.income_monthly where period = '2099-02-01'")[0]
    assert (float(gross), float(net), float(ytd)) == (3500.0, 2662.68, 7000.0)  # YTD is computed from the months
    cats = {c: (float(e), float(r)) for c, e, r in q(settings, "select category, employee_amount, employer_amount from gold.contributions_monthly where period = '2099-01-01'")}
    assert cats["health"] == (25.0, 25.0) and cats["meal_vouchers"] == (32.0, 48.0)
    # the gross split: base + bonus add up to gross; the other pay elements are real zero rows (dense)
    els = {i: (float(v), float(y)) for i, v, y in q(settings, "select item, value, ytd_value from gold.payslip_measure where measure='pay_element' and period='2099-02-01'")}
    assert els["base_salary"] == (3000.0, 6000.0) and els["bonus"] == (500.0, 1000.0)
    assert els["time_off"] == (0.0, 0.0) and set(els) == {"base_salary", "bonus", "time_off", "back_pay", "other_pay", "bonus_exempt"}
    # views: month, calendar year to date (resets in January), rolling 12 months (NULL until 12 months exist)
    (m, y, r) = q(settings, "select value, ytd_value, r12_value from gold.payslip_measure where measure='gross' and period='2099-04-01'")[0]
    assert (float(m), float(y), r) == (3500.0, 14000.0, None)
    # lineage: the run reads the payslip share and writes seven datasets
    (outs,) = q(settings, "select jsonb_array_length(payload->'outputs') from ops.openlineage_event where job_name=%s and event_type='COMPLETE' order by id desc limit 1", payslips.JOB)[0]
    assert outs == 7


class _Capture(BaseHTTPRequestHandler):
    bodies: list[bytes] = []

    def do_POST(self):  # noqa: N802
        _Capture.bodies.append(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.end_headers()  # empty body = a valid, empty ExportMetricsServiceResponse

    def log_message(self, *a):
        pass


def test_publish_step_sends_owner_stamped_historical_points_after_the_gate(settings, corpus, monkeypatch):
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest

    # reuse the "fixed" corpus of the previous test: every month present, so the gate passes
    def good(path, period):
        parsed, src = fake_parse(path, period)
        if period == "2099-03":
            parsed.summary["net_paid"] = "2 662.68"
            parsed.warnings.clear()
            check(parsed, period)
        return parsed, src

    monkeypatch.setattr(payslips, "parse_pdf", good)
    (corpus / "2099" / "209903.pdf").write_bytes(b"corrected payslip 2099-03")
    server = HTTPServer(("127.0.0.1", 0), _Capture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _Capture.bodies.clear()
    monkeypatch.setenv("FINANCE_OWNER", "alice")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://127.0.0.1:{server.server_port}")
    try:
        payslips.run(Settings())
    finally:
        server.shutdown()

    finance = []
    for body in _Capture.bodies:  # the run's own telemetry is not exported here; only the publisher posts
        req = ExportMetricsServiceRequest()
        req.ParseFromString(body)
        finance.extend(m for rm in req.resource_metrics for sm in rm.scope_metrics for m in sm.metrics if m.name.startswith("finance."))
    assert finance, "no finance.* metrics were posted"
    gross = next(m for m in finance if m.name == "finance.payslip.gross_eur")
    stamps = sorted(dp.time_unix_nano for dp in gross.gauge.data_points)
    import datetime as dt

    assert [dt.datetime.fromtimestamp(t / 1e9, dt.timezone.utc).strftime("%Y-%m-%d") for t in stamps][:2] == ["2099-01-15", "2099-02-15"]
    assert {a.value.string_value for m in finance for dp in m.gauge.data_points for a in dp.attributes if a.key == "owner"} == {"alice"}
    names = {m.name for m in finance}
    assert {"finance.payslip.ytd_pay_element_eur", "finance.payslip.pay_element_eur", "finance.payslip.ytd_contribution_eur"} <= names
