"""Parser for the 2026-10+ layout ("BULLETIN DE SALAIRE <MOIS> <ANNÉE>", new employer).

One table `LIBELLE | BASE (ou nombre) | TAUX | PART SALARIALE montant | TAUX | PART PATRONALE montant`, repeated
on every page (header block + table header on each). Amounts are printed with decimal points and, unlike the other
layouts, signed in place: an absence is `-3272.73` in the salary column. Totals sit in two small tables at the
bottom of the last page, each a header row followed by one row of numbers. Some rows are printed twice on top of
each other (the same number twice at the same x): duplicates are dropped. A few labels wrap onto two rows and the
number sits on the second one (`Sécurité Sociale-Maladie Maternité Invalidité` / `Décès ...`): inside the
contributions section the label-only rows above are joined to the label, so classification sees the whole name.
"""

from __future__ import annotations

import re

from .model import MONTHS, Parsed, RawLine
from .words import Page, Row, Token, fold, nearest, rows_of

ANCHORS = {"base": 315, "rate": 366, "emp": 441, "e_rate": 496, "employer": 573}
TOL = 9
LABEL_X_MAX = 300
# printed bottom tables: header row -> one row of numbers (right edges as found in the real PDFs)
MONTHLY = ["gross_month", "taxable_net", "ceiling", "pas_annual"]
CUMULATIVE = ["ytd_gross", "ytd_taxable_net", "ceiling_ytd", "hc_hs_month", "hc_hs_year"]
HEADINGS = {"sante", "retraite", "cotisations et contributions", "sociales obligatoires", "sociales facultatives",
            "contributions obligatoires", "autres", "remboursements et deductions diverses", "libelle"}


def _dedupe(row: Row) -> Row:
    seen: list[Token] = []
    for t in row.tokens:
        if any(t.text == u.text and abs(t.x1 - u.x1) < 1.5 and abs(t.top - u.top) < 1.5 for u in seen):
            continue
        seen.append(t)
    row.tokens = seen
    return row


def _cols(row: Row, warnings: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for tok in row.numbers():
        col = nearest(tok.x1, ANCHORS, TOL)
        if col is None:
            warnings.append(f"unassigned number {tok.text!r} at x1={tok.x1:.0f} in {row.text()[:50]!r}")
        elif col in out:
            warnings.append(f"two numbers in column {col} of {row.text()[:50]!r}")
        else:
            out[col] = tok.text
    return out


def _unsigned(text: str) -> str:
    return text.lstrip("-").strip()


def parse(pages: list[Page]) -> Parsed:
    res = Parsed(layout="matmut")
    s = res.summary
    rows = [_dedupe(r) for r in rows_of(pages)]
    full = fold(" ".join(r.text() for r in rows))
    if m := re.search(r"date debut paie\s*:?\s*(\d{2})/(\d{2})/(\d{4})", full):
        s["period"] = f"{m.group(3)}-{m.group(2)}"
    elif m := re.search(r"bulletin de salaire ([a-z]+) (\d{4})", full):
        if month := MONTHS.get(m.group(1)):
            s["period"] = f"{m.group(2)}-{month:02d}"
    if m := re.search(r"siret\s*:?\s*(\d{14})", full):
        s["employer_siret"] = m.group(1)
    if m := re.search(r"date de paiement\s*:?\s*(\d{2}/\d{2}/\d{4})", full):
        s["payment_date"] = m.group(1)

    section, n = "brut", 0
    in_table, carry = False, []
    pending_totals: list[str] | None = None
    for row in rows:
        text = fold(row.text())
        if "nombre" in text and "taux" in text and "montant" in text:  # table header: the table starts below it
            in_table, carry = True, []
            continue
        if "date de paiement" in text and "net a payer" not in text:
            in_table = False
        if "net a payer" in text and "avant" not in text:
            in_table = False
        # bottom: the payment row and the two totals tables
        if "regle par" in text and row.numbers():
            s["net_paid"] = row.numbers()[-1].text
        elif text.startswith("total verse par"):
            pending_totals = ["total_paid", "allowances"]
        elif text.startswith("brut mensuel"):
            pending_totals = MONTHLY
        elif text.startswith("brut cumule"):
            pending_totals = CUMULATIVE
        elif pending_totals is not None and row.numbers() and not row.text(numbers=False).strip():
            for key, tok in zip(pending_totals, row.numbers()):
                s[key] = tok.text
            pending_totals = None
        if not in_table:
            continue
        label = row.text(x_max=LABEL_X_MAX, numbers=False).strip(" |")
        key = fold(label)
        if not row.numbers():
            if label and key not in HEADINGS and section == "cotisations":
                carry.append(label)
            continue
        cols = _cols(row, res.warnings)
        full_label = label
        if section == "cotisations" and carry and not key.startswith(("total ", "csg", "famille", "apec")):
            full_label = " ".join([*carry, label]).strip()
        carry = []
        fkey = fold(full_label)
        if fkey.startswith("salaire brut"):
            s["gross"] = cols.get("emp", "")
            section = "cotisations"
        elif fkey.startswith("total des cotisations"):
            s["employee_contributions"] = cols.get("emp", "")
            s["employer_contributions"] = cols.get("employer", "")
            section = "other"
        elif fkey.startswith("montant net social"):
            s["net_social"] = cols.get("emp", "")
        elif re.match(r"montant net a payer avant", fkey):
            s["net_before_tax"] = cols.get("emp", "")
        elif fkey.startswith("ir preleve a la source"):
            s["pas_base"], s["pas_rate"] = cols.get("base", ""), cols.get("rate", "")
            s["pas_amount"] = _unsigned(cols.get("emp", ""))
        elif not label:
            res.warnings.append(f"numbers without a label on page {row.page + 1}: {row.text()[:60]!r}")
        else:
            n += 1
            emp = cols.get("emp")
            if section == "brut":                      # signed in place: an absence is negative
                gain, deduct = emp, None
            elif section == "other" and emp is not None and emp.startswith("-"):
                gain, deduct = None, _unsigned(emp)    # a deduction printed as a negative amount
            elif section == "other":
                gain, deduct = emp, None
            else:
                gain, deduct = None, emp
            res.lines.append(RawLine(
                n, section, full_label,
                base=cols.get("base"), rate=cols.get("rate"),
                employee_gain=gain, employee_deduct=deduct,
                employer_rate=cols.get("e_rate"), employer_amount=cols.get("employer"),
            ))
    return res
