"""Parser for the 2025-11+ layout ("BULLETIN DE PAIE - EN EUROS").

Page 1 is a visual summary with overlapping text boxes (unusable); the detail table
starts on page 2 and may spill onto page 3. Columns: BASE | TAUX | PART SALARIÉ
MONTANT | PART EMPLOYEUR MONTANT. Below the table sits a two-panel block: PAS and
"other information" on the left, leave balances and year-to-date totals on the right,
so rows there are split at x=400. Footnote markers are smaller than body text and
are dropped by size.
"""

from __future__ import annotations

import re

from .model import MONTHS, Parsed, RawLine
from .words import Page, Row, Token, fold, nearest, rows_of

ANCHORS = {"base": 298, "rate": 352, "emp": 404, "employer": 478}
TOL = 9
LABEL_X_MAX = 292
TABLE_X_MAX = 490
PANEL_SPLIT = 370   # left panel numbers end at x~363, right panel labels start at x~375
MARGIN_X = 31       # rotated section names ("Brut", "Santé", ...) live left of the labels
FOOTNOTE_SIZE = 6.3  # body text is ~6.7pt, footnote markers ~6.0pt
GLYPH_SIZE = 5.8     # rotated section names ("Brut", "Santé", ...) are drawn glyph by glyph at 1.5-5.3pt
# words that only occur in the employee/employer header block (repeated on every page of the 2026-09+ template)
HEADER_WORDS = ("siret", "n° ape", "convention collective", "classification", "emploi :", "categorie", "anciennete",
                "salaire contractuel", "syntec", "minimum coefficient", "remuneration du mois", "duree mensuelle",
                "taux horaire", "debut de contrat", "detail du salarie")
DEDUCTION_WORDS = ("retenue", "titres-restaurant", "titre restaurant", "acompte", "saisie", "mutuelle")


def _strip_footnotes(row: Row) -> Row:
    row.tokens = [
        t for t in row.tokens
        if not (t.text.isdigit() and 0 < t.size < FOOTNOTE_SIZE and len(t.text) <= 2)  # footnote markers
        and not (0 < t.size < GLYPH_SIZE and len(t.text) <= 3)                        # rotated margin glyphs
    ]
    return row


def _cols(tokens: list[Token], anchors: dict[str, float], warnings: list[str], ctx: str, tol: float = TOL) -> dict[str, str]:
    out: dict[str, str] = {}
    for tok in tokens:
        col = nearest(tok.x1, anchors, tol)
        if col is None:
            warnings.append(f"unassigned number {tok.text!r} at x1={tok.x1:.0f} in {ctx[:50]!r}")
        elif col in out:
            warnings.append(f"two numbers in column {col} of {ctx[:50]!r}")
        else:
            out[col] = tok.text
    return out


def parse(pages: list[Page]) -> Parsed:
    res = Parsed(layout="modern")
    s = res.summary
    rows = [_strip_footnotes(r) for r in rows_of(pages)]
    full = fold(" ".join(r.text() for r in rows))
    if m := re.search(r"debut de periode\s*:?\s*(\d{2})/(\d{2})/(\d{4})", full):
        s["period"] = f"{m.group(3)}-{m.group(2)}"
    elif m := re.search(r"\bdu (\d{2})/(\d{2})/(\d{4}) au \d{2}/\d{2}/\d{4}", full):  # 2026-09+: "Du 01/09/2026 au 25/09/2026"
        s["period"] = f"{m.group(3)}-{m.group(2)}"
    elif m := re.search(r"bulletin de paie de ([a-z]+) (\d{4})", full):  # page 1: "Voici votre bulletin de paie de septembre 2026"
        if month := MONTHS.get(m.group(1)):
            s["period"] = f"{m.group(2)}-{month:02d}"
    if m := re.search(r"n.?siret\s*:?\s*(\d{14})", full):
        s["employer_siret"] = m.group(1)
    if m := re.search(r"date de paiement\s*(\d{2}/\d{2}/\d{4})", full):
        s["payment_date"] = m.group(1)

    bottom = False
    leave_cols: list[str] = []
    section = "brut"
    n = 0
    skip_until: dict[int, int] = {}  # page -> index of the last header-block row
    for idx, row in enumerate(rows):
        if row.page == 0:
            continue
        if row.page not in skip_until:
            skip_until[row.page] = _header_end(rows, row.page)
        if idx <= skip_until[row.page]:
            continue
        text = fold(row.text())
        if "soldes de conges" in text and "impot sur le revenu" in text:
            bottom = True
        if bottom:
            leave_cols = _bottom_row(row, s, res.warnings, leave_cols)
            continue
        left = Row([t for t in row.tokens if MARGIN_X <= t.x0 and t.x1 <= TABLE_X_MAX], row.page)
        label = left.text(x_max=LABEL_X_MAX, numbers=False).strip(" |")
        key = fold(label)
        nums = left.numbers()
        if not nums:
            continue
        cols = _cols(nums, ANCHORS, res.warnings, left.text())
        if key.startswith("remuneration brute"):
            s["gross"] = cols.get("emp", "")
            section = "cotisations"
        elif key.startswith("total cotisations") and "salariales" in key:
            s["employee_contributions"] = cols.get("emp", "")
        elif key.startswith("total cotisations") and "patronales" in key:
            s["employer_contributions"] = cols.get("employer", "")
            section = "other"
        elif key.startswith("montant net social"):
            s["net_social"] = cols.get("employer", "")
        elif key.startswith("net a payer avant"):
            s["net_before_tax"] = cols.get("employer", "")
        elif key.startswith("net paye"):
            s["net_paid"] = cols.get("employer", "")
        elif key.startswith("dont evolution"):
            continue
        elif not label:
            res.warnings.append(f"numbers without a label on page {row.page + 1}: {left.text()[:60]!r}")
        else:
            n += 1
            gain = section == "brut" or (section == "other" and not any(w in key for w in DEDUCTION_WORDS))
            res.lines.append(RawLine(
                n, section, label,
                base=cols.get("base"), rate=cols.get("rate"),
                employee_gain=cols.get("emp") if gain else None,
                employee_deduct=None if gain else cols.get("emp"),
                employer_amount=cols.get("employer"),
            ))
    return res


def _header_end(rows: list[Row], page: int) -> int:
    """Index (in `rows`) of the last row of the header block of `page`, so the table starts after it.

    Pages that carry the table header use it ("DÉSIGNATION  BASE"). Continuation pages repeat the
    employee/employer block but not that header, so the block ends at its last header-ish row in
    the upper part of the page. Without either, nothing is skipped.
    """
    page_rows = [(i, r) for i, r in enumerate(rows) if r.page == page]
    for i, r in page_rows:
        t = fold(r.text())
        if "designation" in t and "base" in t:
            return i
    last = -1
    for i, r in page_rows:
        if r.top > 400:  # header blocks live in the upper half of an A4 page
            break
        if any(w in fold(r.text()) for w in HEADER_WORDS):
            last = i
    return last


def _leave_header(right: Row) -> list[str] | None:
    """`CP N-2  CP N-1  CP N  RTT` -> ["cp_n2", "cp_n1", "cp_n", "rtt"] (column set varies by month)."""
    text = right.text()
    if "CP" not in text or "RTT" not in text:
        return None
    return [
        "rtt" if m.group(1) == "RTT" else "cp_" + (m.group(2) or "").lower().replace("-", "")
        for m in re.finditer(r"(CP|RTT)\s*(N-?\d?)?", text)
    ]


def _bottom_row(row: Row, s: dict[str, str], warnings: list[str], leave_cols: list[str]) -> list[str]:
    left = Row([t for t in row.tokens if t.x0 < PANEL_SPLIT], row.page)
    right = Row([t for t in row.tokens if t.x0 >= PANEL_SPLIT], row.page)
    lkey = fold(left.text(numbers=False))
    nums = [t.text for t in left.numbers()]
    if lkey.startswith("impot sur le revenu") and "source" in lkey and len(nums) >= 3:
        s["pas_base"], s["pas_rate"], s["pas_amount"] = nums[0], nums[1], nums[2]
    elif lkey.startswith("total verse par l"):
        s["total_paid"] = nums[0] if nums else ""
    elif lkey.startswith("allegement"):
        s["allowances"] = nums[0] if nums else ""
    elif lkey.startswith("net imposable"):
        s["taxable_net"] = nums[0] if nums else ""
    elif lkey.startswith("temps travaille ce mois"):
        s["hours"] = nums[0] if nums else ""
    rkey = fold(right.text(numbers=False))
    rnums = right.numbers()
    if header := _leave_header(right):
        leave_cols = header
    elif rkey.startswith(("acquis", "pris", "solde")) and rnums:
        kind = {"acquis": "earned", "pris": "taken", "solde": "balance"}[next(k for k in ("acquis", "pris", "solde") if rkey.startswith(k))]
        if len(rnums) == len(leave_cols):
            for col, tok in zip(leave_cols, rnums):
                s[f"leave_{col}_{kind}"] = tok.text
        else:
            warnings.append(f"{len(rnums)} leave values for columns {leave_cols}")
    elif rkey.startswith("net imposable") and rnums:
        s["ytd_taxable_net"] = rnums[-1].text
    elif rkey.startswith("salaire brut") and rnums:
        s["ytd_gross"] = rnums[-1].text
    elif rkey.startswith("prelevement a la source") and rnums:
        s["ytd_pas"] = rnums[-1].text
    elif rkey.startswith("temps travaille"):
        if m := re.search(r"(\d+[.,]\d+)\s*h", right.text()):
            s["ytd_hours"] = m.group(1)
    return leave_cols
