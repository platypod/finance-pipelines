import datetime as dt
from decimal import Decimal

import pytest

from platypod_pipeline import publish as pub


def income_row(period, **kw):
    row = {c: None for _, c in pub.INCOME_METRICS.values()} | {"leave_cp_balance": None, "leave_rtt_balance": None}
    row.update(period=period, net_to_gross=Decimal("0.7"), **kw)
    return row


def measure(period, name, value, ytd=None, r12=None, item="", side=""):
    return {"period": period, "measure": name, "item": item, "side": side, "value": value, "ytd_value": ytd, "r12_value": r12}


def points(req):
    out = {}
    for m in req.resource_metrics[0].scope_metrics[0].metrics:
        out[m.name] = [(dp.time_unix_nano, dp.as_double, {a.key: a.value.string_value for a in dp.attributes}) for dp in m.gauge.data_points]
    return out


def test_samples_are_mid_month_utc_so_calendar_ranges_never_miss_them():
    ns = pub.sample_time(dt.date(2020, 2, 1))
    assert dt.datetime.fromtimestamp(ns / 1e9, dt.timezone.utc) == dt.datetime(2020, 2, 15, 12, tzinfo=dt.timezone.utc)


def test_every_point_carries_the_owner_and_nulls_are_skipped():
    jan, feb = dt.date(2026, 1, 1), dt.date(2026, 2, 1)
    req, n = pub.build_request(
        "alice",
        [income_row(jan), income_row(feb, leave_rtt_balance=Decimal("4.5"))],
        [
            measure(jan, "gross", Decimal("5000"), ytd=Decimal("5000"), r12=None),
            measure(feb, "gross", Decimal("5100"), ytd=Decimal("10100"), r12=None),
            measure(jan, "employer_cost", None),  # not printed: no point in any view
        ],
    )
    got = points(req)
    assert all(attrs["owner"] == "alice" for series in got.values() for _, _, attrs in series)
    assert [v for _, v, _ in got["finance.payslip.gross_eur"]] == [5000.0, 5100.0]
    assert [v for _, v, _ in got["finance.payslip.ytd_gross_eur"]] == [5000.0, 10100.0]
    assert "finance.payslip.r12_gross_eur" not in got  # NULL until 12 months exist
    assert not any("employer_cost" in name for name in got)
    assert got["finance.payslip.leave_days"] == [(pub.sample_time(feb), 4.5, {"owner": "alice", "kind": "rtt"})]
    assert n == sum(len(v) for v in got.values())


def test_pay_elements_and_contributions_are_published_in_every_view_zeros_included():
    jan = dt.date(2026, 1, 1)
    req, _ = pub.build_request(
        "alice",
        [],
        [
            measure(jan, "pay_element", Decimal("0"), ytd=Decimal("0"), r12=Decimal("1200"), item="bonus"),
            measure(jan, "contribution", Decimal("0"), ytd=Decimal("25"), item="health", side="employee"),
        ],
    )
    got = points(req)
    # a zero is a real sample: without it a carried-forward series would show last month's amount
    assert got["finance.payslip.pay_element_eur"] == [(pub.sample_time(jan), 0.0, {"owner": "alice", "element": "bonus"})]
    assert got["finance.payslip.r12_pay_element_eur"][0][1] == 1200.0
    assert got["finance.payslip.ytd_contribution_eur"] == [(pub.sample_time(jan), 25.0, {"owner": "alice", "category": "health", "side": "employee"})]


@pytest.mark.parametrize("owner", ["", "_shared", "_admin"])
def test_refuses_to_publish_without_a_real_owner(owner):
    with pytest.raises(ValueError):
        pub.build_request(owner, [income_row(dt.date(2026, 1, 1))], [])


def test_unknown_measure_is_an_error_not_a_silent_drop():
    with pytest.raises(ValueError):
        pub.build_request("alice", [], [measure(dt.date(2026, 1, 1), "mystery", Decimal("1"))])


def test_metric_catalog_matches_the_gold_contracts():
    import yaml
    from pathlib import Path

    def columns(name):
        c = yaml.safe_load((Path(__file__).parents[1] / "contracts" / f"{name}.odcs.yaml").read_text())
        return {p["name"] for p in c["schema"][0]["properties"]}

    assert {c for _, c in pub.INCOME_METRICS.values()} | set(pub.LEAVE_COLUMNS.values()) <= columns("gold.income_monthly")
    assert {c for _, c in pub.VIEWS} | {"period", "measure", "item", "side"} <= columns("gold.payslip_measure")
