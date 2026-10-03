import datetime as dt
from decimal import Decimal

import pytest

from platypod_pipeline import publish as pub


def income_row(period, **kw):
    row = {c: None for _, c in pub.INCOME_METRICS.values()} | {"leave_cp_balance": None, "leave_rtt_balance": None}
    row.update(period=period, gross_amount=Decimal("5000.00"), net_paid=Decimal("3500.00"), **kw)
    return row


def points(req):
    out = {}
    for m in req.resource_metrics[0].scope_metrics[0].metrics:
        out[m.name] = [(dp.time_unix_nano, dp.as_double, {a.key: a.value.string_value for a in dp.attributes}) for dp in m.gauge.data_points]
    return out


def test_samples_are_mid_month_utc_so_calendar_ranges_never_miss_them():
    ns = pub.sample_time(dt.date(2020, 2, 1))
    assert dt.datetime.fromtimestamp(ns / 1e9, dt.timezone.utc) == dt.datetime(2020, 2, 15, 12, tzinfo=dt.timezone.utc)


def test_every_point_carries_the_owner_and_nulls_are_skipped():
    req, n = pub.build_request(
        "alice",
        [income_row(dt.date(2026, 1, 1)), income_row(dt.date(2026, 2, 1), leave_rtt_balance=Decimal("4.5"))],
        [{"period": dt.date(2026, 1, 1), "category": "health", "employee_amount": Decimal("25"), "employer_amount": Decimal("0")}],
    )
    got = points(req)
    assert set(got) == {"finance.payslip.gross_eur", "finance.payslip.net_paid_eur", "finance.payslip.leave_days", "finance.payslip.contribution_eur"}
    assert all(attrs["owner"] == "alice" for series in got.values() for _, _, attrs in series)
    assert len(got["finance.payslip.gross_eur"]) == 2 and n == sum(len(v) for v in got.values())
    assert got["finance.payslip.leave_days"] == [(pub.sample_time(dt.date(2026, 2, 1)), 4.5, {"owner": "alice", "kind": "rtt"})]
    # a zero employer amount is not published, the employee one is
    assert [(a["side"], v) for _, v, a in got["finance.payslip.contribution_eur"]] == [("employee", 25.0)]


@pytest.mark.parametrize("owner", ["", "_shared", "_admin"])
def test_refuses_to_publish_without_a_real_owner(owner):
    with pytest.raises(ValueError):
        pub.build_request(owner, [income_row(dt.date(2026, 1, 1))], [])


def test_metric_catalog_matches_gold_columns():
    # every column the publisher reads must be in the gold contract
    import yaml
    from pathlib import Path

    contract = yaml.safe_load((Path(__file__).parents[1] / "contracts" / "gold.income_monthly.odcs.yaml").read_text())
    columns = {p["name"] for p in contract["schema"][0]["properties"]}
    assert {c for _, c in pub.INCOME_METRICS.values()} | set(pub.LEAVE_COLUMNS.values()) <= columns
