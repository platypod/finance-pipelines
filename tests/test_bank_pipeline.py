"""Bank pipeline end to end on SYNTHETIC statements (invented merchants, numbers and people)."""

import pytest
from bank_fixtures import account_block, card, export, row

from platypod_pipeline import db
from platypod_pipeline.config import Settings
from platypod_pipeline.migrate import migrate
from platypod_pipeline.pipelines import bank
from platypod_pipeline.pipelines.payslips import NeedsAttention
from platypod_pipeline.runner import ContractViolation

pytestmark = pytest.mark.integration
TABLES = ["gold.bank_transaction_detail", "gold.bank_measure", "silver.bank_transaction_category", "silver.bank_transaction", "silver.bank_balance",
          "silver.bank_override", "silver.bank_rule", "silver.bank_account", "bronze.bank_transaction_raw", "bronze.bank_file"]

ACCOUNTS = """accounts:
  - {alias: alice-current, bank: ca, last4: "1111", kind: current, person: alice, visibility: "group:finance"}
  - {alias: alice-livret, bank: ca, last4: "3333", kind: savings, person: alice, visibility: alice}
"""
RULES = """rules:
  - {id: payroll, label: 'acme payroll', set: {category: income, subcategory: salary}}
  - {id: bakery, label: 'boulangerie', set: {category: food, subcategory: groceries, necessity: essential}}
"""


def current_rows(*extra):
    return [
        row("05/01/2026", "05/01/2026", ["Virement en votre faveur", "ACME PAYROLL 01/26"], 3000.0),
        card("06/01/2026", "BOULANGERIE DUPONT", "05/01", -4.5),
        card("06/01/2026", "BOULANGERIE DUPONT", "05/01", -4.5),  # same label, day and amount: two real purchases
        row("10/01/2026", "10/01/2026", ["Virement émis", "WEB LIVRET"], -500.0),
        *extra,
    ]


def livret_rows():
    return [row("10/01/2026", "10/01/2026", ["Virement en votre faveur", "DE M ALICE E"], 500.0),
            row("31/01/2026", "31/01/2026", ["Intérêts créditeurs", "DE L'ANNEE TAUX 1,700%"], 10.0)]


def write_export(d, name, downloaded, period_to, current_balance, extra=(), livret_balance=1010.0, with_livret=True):
    blocks = [account_block("Compte de Dépôt", "00011111111", current_balance, period_to, ("01/01/2026", period_to), current_rows(*extra))]
    if with_livret:
        blocks.append(account_block("Livret A", "00033333333", livret_balance, period_to, ("01/01/2026", period_to), livret_rows()))
    (d / name).write_bytes(export(downloaded, blocks))


@pytest.fixture(scope="module")
def settings():
    s = Settings()
    migrate(s)
    yield s
    with db.connect(s, "admin") as conn:
        for t in TABLES:
            conn.execute(f"delete from {t}")


@pytest.fixture
def statements(tmp_path, settings, monkeypatch):
    with db.connect(settings, "admin") as conn:
        for t in TABLES:
            conn.execute(f"delete from {t}")
    (tmp_path / "accounts.yaml").write_text(ACCOUNTS)
    (tmp_path / "rules.yaml").write_text(RULES)
    monkeypatch.setenv("BANK_DIR", str(tmp_path))
    return tmp_path


def q(settings, sql, *args):
    with db.connect(settings, "transform") as conn:
        return conn.execute(sql, args).fetchall()


def two_exports(statements):
    first = 3000 - 9 - 500
    write_export(statements, "a.csv", "05/02/2026", "05/02/2026", first)
    write_export(statements, "b.csv", "15/02/2026", "15/02/2026", first - 100, extra=[
        row("12/02/2026", "12/02/2026", ["Prélèvement", "ENGIE S.A."], -80.0),
        row("13/02/2026", "13/02/2026", ["Prélèvement", "ZORBA MYSTERY"], -20.0)])


def test_overlapping_exports_dedupe_pair_classify_and_reconcile(settings, statements):
    two_exports(statements)
    # the 2nd export repeats every row of the 1st and adds two; ZORBA matches no rule: the run still succeeds
    bank.run(settings)
    bank.run(settings)  # idempotent: nothing new to load, dbt + contracts still pass

    # 4 distinct operations on the current account (the 2 identical bakery purchases are kept) + 2 new; 2 on the livret
    counts = dict(q(settings, "select account, count(*) from silver.bank_transaction group by 1"))
    assert counts == {"alice-current": 6, "alice-livret": 2}
    cat = {(c, s): n for c, s, n in q(settings, "select category, subcategory, count(*) from silver.bank_transaction_category group by 1, 2")}
    assert cat[("food", "groceries")] == 2 and cat[("income", "salary")] == 1
    assert cat[("transfers", "internal")] == 2  # the transfer to the livret, paired with its credit on the other account
    assert cat[("income", "interest")] == 1 and cat[("uncategorized", "uncategorized")] == 1  # ZORBA; ENGIE is caught by a generic rule
    assert cat[("home", "utilities")] == 1

    # spend excludes internal transfers; the whole-month figure is 9 (bakery) in January, 100 in February
    spend = {str(p)[:7]: float(v) for p, v in q(settings, "select period, sum(value) from gold.bank_measure where measure='spend' group by 1")}
    assert spend["2026-01"] == 9.0 and spend["2026-02"] == 100.0
    income = {str(p)[:7]: float(v) for p, v in q(settings, "select period, sum(value) from gold.bank_measure where measure='income' group by 1")}
    assert income["2026-01"] == 3010.0  # salary + interest, not the 500 moved between the person's own accounts
    # views: January's year-to-date equals the month; February accumulates; r12 needs twelve months
    (ytd, r12) = q(settings, "select sum(ytd_value), sum(r12_value) from gold.bank_measure where measure='spend' and period='2026-02-01'")[0]
    assert float(ytd) == 109.0 and r12 is None
    # who sees what: the current account is for the finance group, the livret for alice only
    owners = dict(q(settings, "select item1, owner from gold.bank_measure where measure='balance' group by 1, 2"))
    assert owners == {"alice-current": "group:finance", "alice-livret": "alice"}
    # the month-end balance of the last (partial) month is the bank's own figure
    (bal,) = q(settings, "select value from gold.bank_measure where measure='balance' and item1='alice-current' and period='2026-02-01'")[0]
    assert float(bal) == 2391.0
    # the detail view flags what nothing decided (ZORBA), not what a rule or a pair decided
    review = q(settings, "select label, amount from gold.bank_transaction_detail where needs_review")
    assert [(l.split()[0], float(a)) for l, a in review] == [("Prélèvement", -20.0)] and "ZORBA" in review[0][0]
    (run_status,) = q(settings, "select status from ops.pipeline_run where job=%s order by started_at desc limit 1", bank.JOB)[0]
    assert run_status == "success"


def test_overrides_beat_rules_and_the_transfer_pairing(settings, statements):
    two_exports(statements)
    bank.run(settings)
    (statements / "overrides.csv").write_text(
        "txn_id,account,date,amount,label_contains,category,subcategory,necessity,note\n"
        ",,2026-02-13,-20.00,ZORBA,food,restaurants,luxury,birthday dinner\n"
        ",,2026-01-05,,ACME PAYROLL,income,reimbursement,,reclassified\n")
    bank.run(settings)
    got = {l.split()[-2] if "ZORBA" in l else "ACME": (c, s, n) for l, c, s, n in q(settings, "select t.label_clean, c.category, c.subcategory, c.necessity from silver.bank_transaction t "
                                                       "join silver.bank_transaction_category c using (txn_id) where t.label_clean ~* 'zorba|acme'")}
    assert got["ZORBA"] == ("food", "restaurants", "luxury")
    assert got["ACME"][:2] == ("income", "reimbursement")


def test_a_balance_that_does_not_follow_from_the_operations_fails_the_gate(settings, statements):
    write_export(statements, "a.csv", "05/02/2026", "05/02/2026", 2491.0)
    # the later anchor ignores a -80 operation it lists: a missing or duplicated row somewhere
    write_export(statements, "b.csv", "15/02/2026", "15/02/2026", 2491.0, extra=[row("12/02/2026", "12/02/2026", ["Prélèvement", "ENGIE S.A."], -80.0)])
    with pytest.raises(ContractViolation) as exc:
        bank.run(settings)
    assert any("balance" in (c.name or "") or "continuity" in (c.name or "") or "balance" in str(c.model or "") for c in exc.value.result.failures)


def test_an_account_missing_from_accounts_yaml_fails_after_the_rest_is_loaded(settings, statements):
    (statements / "accounts.yaml").write_text(ACCOUNTS.split("  - {alias: alice-livret")[0])  # the livret is not mapped
    two_exports(statements)
    with pytest.raises(NeedsAttention) as exc:
        bank.run(settings)
    assert "…3333" in str(exc.value) and "not in accounts.yaml" in str(exc.value)
    # nothing is dropped silently: the mapped account is loaded and published-ready
    assert q(settings, "select count(*) from silver.bank_transaction")[0][0] == 6


def test_an_unreadable_file_is_flagged_not_ignored(settings, statements):
    two_exports(statements)
    (statements / "notes.csv").write_text("hello;world\n")
    (statements / "._a.csv").write_bytes(b"AppleDouble debris")
    with pytest.raises(NeedsAttention) as exc:
        bank.run(settings)
    assert "notes.csv" in str(exc.value) and "unsupported" in str(exc.value) and "._a" not in str(exc.value)
