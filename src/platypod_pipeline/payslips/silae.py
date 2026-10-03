"""Parser for the Silae-generated layout (Feb 2020 -> Oct 2025).

One table: `Eléments de paie | Base | Taux | A déduire | A payer | Charges patronales`
(employer side = base/taux/montant). Multi-page payslips repeat the header on each
page and the table simply continues. Numbers are bucketed by their right edge into
columns whose x positions are constant across every file seen (all producers).
"""

from __future__ import annotations

import re

from .model import MONTHS, Parsed, RawLine
from .words import Page, Row, fold, nearest, rows_of

ANCHORS = {"base": 282, "rate": 324, "deduct": 372, "gain": 426, "e_base": 474, "e_rate": 516, "e_amount": 552}
TOTALS = {"hours": 90, "overtime": 148, "gross": 205, "ceiling": 263, "taxable_net": 320,
          "employer_charges": 378, "employer_cost": 436, "total_paid": 493, "allowances": 537}
LEAVE = {"cp_n1": 90, "cp_n": 148, "rtt": 205}
TOL = 9
LABEL_X_MAX = 272  # labels end before the Base column


def _cols(row: Row, anchors: dict[str, float], warnings: list[str], *, tol: float = TOL) -> dict[str, str]:
    out: dict[str, str] = {}
    for tok in row.numbers():
        col = nearest(tok.x1, anchors, tol)
        if col is None:
            warnings.append(f"unassigned number {tok.text!r} at x1={tok.x1:.0f} in {row.text()[:50]!r}")
        elif col in out:
            warnings.append(f"two numbers in column {col} of {row.text()[:50]!r}")
        else:
            out[col] = tok.text
    return out


def _period(rows: list[Row], s: dict[str, str]) -> None:
    """`Période : Juin 2020` — tolerant of glued colons and OCR noise between the words."""
    for row in rows:
        text = fold(row.text())
        if "periode" in text:
            words = re.findall(r"[a-z]+|\d{4}", text)
            month = next((MONTHS[w] for w in words if w in MONTHS), None)
            year = next((w for w in words if re.fullmatch(r"20\d\d", w)), None)
            if month and year:
                s["period"] = f"{year}-{month:02d}"
                return


def parse(pages: list[Page]) -> Parsed:
    res = Parsed(layout="silae")
    s = res.summary
    all_rows = rows_of(pages)
    full = fold(" ".join(r.text() for r in all_rows))
    _period(all_rows, s)
    if m := re.search(r"siret\s*:?\s*(\d{14})", full):
        s["employer_siret"] = m.group(1)
    if m := re.search(r"paiement le (\d{2}/\d{2}/\d{4})", full):
        s["payment_date"] = m.group(1)

    section = "brut"
    n = 0
    for pno in range(len(pages)):
        rows = [r for r in all_rows if r.page == pno]
        try:
            start = next(i for i, r in enumerate(rows) if "elements de paie" in fold(r.text()))
        except StopIteration:
            continue
        end = next(
            # the totals header; "heures suppl." alone also matches a legitimate table line
            (i for i, r in enumerate(rows) if i > start and "heures" in fold(r.text()) and "plafond" in fold(r.text())),
            len(rows),
        )
        for row in rows[start + 1 : end]:
            label = row.text(x_max=LABEL_X_MAX, numbers=False).strip(" |")
            if not row.numbers():
                continue
            key = fold(label)
            cols = _cols(row, ANCHORS, res.warnings)
            if key.startswith("salaire brut"):
                s["gross"] = cols.get("gain", "")
                section = "cotisations"
            elif key.startswith("total des retenues") and "deductibles" in key:
                continue  # sub-totals some months print before the grand total
            elif key.startswith(("total des cotisations", "total des retenues")):
                s["employee_contributions"] = cols.get("deduct", "")
                s["employer_contributions"] = cols.get("e_amount", "")
                section = "other"
            elif re.match(r"net\s*\S?\s*payer avant", key):
                s["net_before_tax"] = cols.get("gain", "")
            elif key.startswith("montant net social"):
                s["net_social"] = next(iter(cols.values()), "")
            elif re.match(r"imp.{1,2}t sur le revenu preleve", key):
                s["pas_base"] = cols.get("base", "")
                s["pas_rate"] = cols.get("rate", "").lstrip("-").strip()
                s["pas_amount"] = cols.get("deduct", "")
            elif re.match(r"imp.{1,2}t sur le revenu\s*:\s*cumul", key):
                s["pas_ytd"] = cols.get("base", "")
            elif key.startswith("net paye"):
                s.setdefault("net_paid", cols.get("gain", ""))
            elif key.startswith(("suppression des cotisations", "dont evolution", "taux personnalise")):
                continue
            elif not label:
                res.warnings.append(f"numbers without a label on page {pno + 1}: {row.text()[:60]!r}")
            else:
                n += 1
                res.lines.append(RawLine(
                    n, section, label,
                    base=cols.get("base"), rate=cols.get("rate"),
                    employee_gain=cols.get("gain"), employee_deduct=cols.get("deduct"),
                    employer_base=cols.get("e_base"), employer_rate=cols.get("e_rate"),
                    employer_amount=cols.get("e_amount"),
                ))
        # bottom blocks: monthly/annual totals, leave balances
        for row in rows[end:]:
            head = fold(row.text(x_max=60, numbers=False))
            if head.startswith(("mensuel", "annuel")):
                if not row.numbers():
                    continue
                prefix = "" if head.startswith("mensuel") else "ytd_"
                for col, val in _cols(row, TOTALS, res.warnings, tol=12).items():
                    s[prefix + col] = val
            elif head.startswith(("acquis", "pris", "solde")):
                kind = {"acquis": "earned", "pris": "taken", "solde": "balance"}[next(k for k in ("acquis", "pris", "solde") if head.startswith(k))]
                for col, val in _cols(row, LEAVE, res.warnings, tol=14).items():
                    s[f"leave_{col}_{kind}"] = val
    return res
