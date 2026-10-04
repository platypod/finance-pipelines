import re
from pathlib import Path

import pytest
import yaml
from bank_fixtures import account_block, card, export, row

from platypod_pipeline.bank import ca, reference
from platypod_pipeline.bank.parse import check, parse_statement
from platypod_pipeline.config import Settings


@pytest.fixture
def statement(tmp_path):
    blocks = [
        account_block("Compte de Dépôt", "00011111111", 1563.72, "05/02/2026", ("01/01/2026", "05/02/2026"), [
            card("06/01/2026", "CARREFOUR CITY ROUEN", "05/01", -50.0, "Carrefour City"),
            row("10/01/2026", "10/01/2026", ["Virement émis", "WEB ALICE LIVRET"], -500.0),
            row("05/01/2026", "05/01/2026", ["Virement en votre faveur", "ACME PAYROLL 01/26"], 3000.0),
            row("11/01/2026", "11/01/2026", ["Prélèvement", "NETFLIX - Netflix - 123456789 REF"], -1234.5),
        ], holder="MONSIEUR ALICE EXEMPLE"),
        account_block("Compte de Dépôt", "00022222222", 3523.15, "05/02/2026", ("01/01/2026", "05/02/2026"), [
            row("12/01/2026", "12/01/2026", ["Prélèvement", "ENGIE S.A."], -80.0),
        ], holder="MADAME BOB EXEMPLE OU MONSIEUR ALICE EXEMPLE"),
        # savings blocks carry no holder line
        account_block("Livret A", "00033333333", 3000.39, "05/02/2026", ("01/01/2026", "05/02/2026"), [
            row("10/01/2026", "10/01/2026", ["Virement en votre faveur", "DE M ALICE E"], 500.0),
            row("31/01/2026", "31/01/2026", ["Intérêts créditeurs", "DE L'ANNEE TAUX 1,700%"], 10.0),
        ]),
    ]
    p = tmp_path / "CA20260205_100000.csv"
    p.write_bytes(export("05/02/2026", blocks))
    return p


def test_parses_every_account_with_balances_periods_and_multiline_labels(statement):
    p = ca.parse(statement)
    assert p.warnings == [] and p.exported_on == "05/02/2026"
    assert [(a.kind, a.last4, a.number_digits, len(a.rows)) for a in p.accounts] == [
        ("Compte de Dépôt", "1111", 11, 4), ("Compte de Dépôt", "2222", 11, 1), ("Livret A", "3333", 11, 2)]
    a = p.accounts[0]
    assert (a.balance, a.balance_date, a.period_from, a.period_to) == ("1 563,72", "05/02/2026", "01/01/2026", "05/02/2026")
    first = a.rows[0]
    assert first.label == "Paiement par carte X9999 CARREFOUR CITY ROUEN 05/01 - Carrefour City"  # 6 lines -> one clean string
    assert (first.booking_date, first.debit, first.credit) == ("06/01/2026", "50,00", "")
    assert a.rows[3].debit == "1 234,50"  # thousands separated by a space
    assert p.accounts[2].rows[1].label.startswith("Intérêts créditeurs")  # latin-1 accents survive


def test_no_holder_name_or_full_account_number_is_kept(statement):
    p = ca.parse(statement)
    dumped = repr(p)
    assert "EXEMPLE" not in dumped and "00011111111" not in dumped


def test_not_a_known_export_is_none(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a;b;c\n1;2;3\n")
    assert parse_statement(f) is None


def test_warnings_make_a_misread_loud(tmp_path):
    blocks = [account_block("Compte de Dépôt", "00011111111", 10.0, "05/02/2026", ("01/01/2026", "05/02/2026"), [
        row("06/03/2026", "06/03/2026", ["Prélèvement", "LATE"], -5.0),            # outside the period
        '07/01/2026;07/01/2026;"Prélèvement\nBOTH";5,00;5,00;\n',                   # debit AND credit
        '08/01/2026;08/01/2026;"Prélèvement\nBAD AMOUNT";5.00;;\n',                 # not a French amount
    ])]
    f = tmp_path / "bad.csv"
    f.write_bytes(export("05/02/2026", blocks))
    msgs = " | ".join(parse_statement(f).warnings)
    assert "outside the export's period" in msgs and "exactly one of debit/credit" in msgs and "debit '5.00'" in msgs


# ---------------------------------------------------------------- reference data
def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_accounts_yaml_is_validated(tmp_path):
    good = write(tmp_path, "ok.yaml", """accounts:
  - {alias: a, bank: ca, last4: "1111", kind: current, person: alice, visibility: "group:finance"}
  - {alias: j, bank: ca, last4: "2222", kind: current, person: joint, holders: [alice, bob], visibility: "group:finance"}
""")
    assert [a["person"] for a in reference.load_accounts(good)] == ["alice", "joint"]
    bad = write(tmp_path, "bad.yaml", """accounts:
  - {alias: a, bank: ca, last4: 1111, kind: current, person: alice, visibility: "group:finance"}
  - {alias: a, bank: xx, last4: "22", kind: gold, person: Alice, visibility: "_shared"}
""")
    with pytest.raises(reference.ReferenceError) as exc:
        reference.load_accounts(bad)
    msg = str(exc.value)
    for needle in ("duplicated", "unsupported bank", "exactly 4 digits", "kind must be", "person", "visibility"):
        assert needle in msg
    with pytest.raises(reference.ReferenceError):
        reference.load_accounts(tmp_path / "missing.yaml")


def test_rules_are_validated_against_the_taxonomy(tmp_path):
    tax = reference.load_taxonomy(Settings())
    default = Path(Settings().root) / "reference" / "default-rules.yaml"
    assert len(reference.load_rules(None, default, tax)) >= 30  # the shipped rules are valid
    bad = write(tmp_path, "rules.yaml", """rules:
  - {id: a, label: 'x', set: {category: nonsense, subcategory: y}}
  - {id: b, label: 'x', set: {category: food, subcategory: car_wash}}
  - {id: c, set: {category: food, subcategory: groceries}}
  - {id: d, label: 'x', family: weird, set: {category: food, subcategory: groceries, necessity: fancy}}
""")
    with pytest.raises(reference.ReferenceError) as exc:
        reference.load_rules(bad, default, tax)
    msg = str(exc.value)
    for needle in ("unknown category", "not a subcategory", "no condition", "unknown family", "unknown necessity"):
        assert needle in msg
    # private rules come first, then the generic ones: priority is the order
    private = write(tmp_path, "p.yaml", "rules:\n  - {id: mine, label: 'carrefour', set: {category: food, subcategory: restaurants}}\n")
    rules = reference.load_rules(private, default, tax)
    assert rules[0]["rule_id"] == "mine" and rules[0]["priority"] == 1 and rules[0]["origin"] == "private"


def test_overrides_are_validated(tmp_path):
    tax = reference.load_taxonomy(Settings())
    ok = write(tmp_path, "overrides.csv", "txn_id,account,date,amount,label_contains,category,subcategory,necessity,note\n"
                                          ",,2026-01-06,-50.00,ZORBA,food,restaurants,luxury,birthday\n")
    o = reference.load_overrides(ok, tax)
    assert o[0]["amount"] == 50 and str(o[0]["booking_date"]) == "2026-01-06" and o[0]["necessity"] == "luxury"
    bad = write(tmp_path, "bad.csv", "txn_id,account,date,amount,label_contains,category,subcategory,necessity,note\n"
                                     ",,not-a-date,,,food,restaurants,,\n,,,,,food,groceries,,\n,,,,x,nope,y,,\n")
    with pytest.raises(reference.ReferenceError) as exc:
        reference.load_overrides(bad, tax)
    assert "unreadable date" in str(exc.value) and "needs txn_id" in str(exc.value) and "unknown category" in str(exc.value)


def test_taxonomy_contracts_and_sql_agree():
    """The taxonomy file is the vocabulary; the contracts and gold SQL embed copies. They must not drift."""
    root = Path(Settings().root)
    tax = yaml.safe_load((root / "reference" / "taxonomy.yaml").read_text())
    pairs = {(c, s) for c, subs in tax["categories"].items() for s in subs}
    for contract in ("silver.bank_rule", "silver.bank_override", "silver.bank_transaction_category"):
        text = (root / "contracts" / f"{contract}.odcs.yaml").read_text()
        embedded = set(re.findall(r"\('([a-z_]+)', *'([a-z_]+)'\)", text))
        assert embedded == pairs, contract
    excluded = {tuple(e) for e in tax["excluded"]}
    # the gold model and contract hard-code the exclusion: transfers (whole category) and savings/investment
    assert {c for c, _ in excluded if c == "transfers"} == {"transfers"} and ("savings", "investment") in excluded
    assert {s for c, s in excluded if c == "transfers"} == set(tax["categories"]["transfers"])
    gold = (root / "dbt" / "models" / "gold" / "bank_measure.sql").read_text()
    assert "category <> 'transfers'" in gold and "category = 'savings' and subcategory = 'investment'" in gold
