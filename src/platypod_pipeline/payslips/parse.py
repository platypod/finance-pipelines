"""Layout detection + parse + sanity checks. `parse_pdf` is the only entry point."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import modern, silae
from .extract import OCR_VARIANTS, extract, ocr_pages
from .model import Parsed
from .words import fold, rows_of


def detect(pages) -> str | None:
    text = fold(" ".join(r.text() for r in rows_of(pages)))
    if "eléments de paie".encode("ascii", "ignore").decode() in text or "elements de paie" in text:
        return "silae"
    if "designation" in text and "en euros" in text:
        return "modern"
    return None


def num(text: str | None) -> Decimal | None:
    """French (`5 357,13`) or English (`3 193.44`) number -> Decimal; None if absent/garbled."""
    if not text:
        return None
    try:
        return Decimal(re.sub(r"[  ]", "", text).replace(",", "."))
    except InvalidOperation:
        return None


def check(p: Parsed, expected_period: str) -> None:
    """Cross-checks that make a mis-parse loud. Appends to p.warnings (never raises)."""
    s, w = p.summary, p.warnings
    if s.get("period") != expected_period:
        w.append(f"period {s.get('period')!r} != filename {expected_period!r}")
    for key in ("gross", "employee_contributions", "net_before_tax", "net_paid"):
        if num(s.get(key)) is None:
            w.append(f"missing or unreadable {key}")
    tol = Decimal("0.05")
    emp = [num(l.employee_deduct) for l in p.lines if l.section == "cotisations"]
    ec = num(s.get("employee_contributions"))
    if ec is not None and abs(sum(v for v in emp if v) - ec) > tol:
        w.append(f"employee contribution lines sum to {sum(v for v in emp if v)} but total is {ec}")
    er = [num(l.employer_amount) for l in p.lines if l.section == "cotisations"]
    erc = num(s.get("employer_contributions"))
    if erc is not None and abs(sum(v for v in er if v) - erc) > tol:
        w.append(f"employer contribution lines sum to {sum(v for v in er if v)} but total is {erc}")
    nbt, pas, paid = num(s.get("net_before_tax")), num(s.get("pas_amount")), num(s.get("net_paid"))
    if None not in (nbt, pas, paid) and abs(nbt - pas - paid) > tol:
        w.append(f"net paid {paid} != net before tax {nbt} - PAS {pas}")


def _parse_pages(pages) -> Parsed | None:
    layout = detect(pages)
    if layout is None:
        return None
    return (silae if layout == "silae" else modern).parse(pages)


def parse_pdf(path: Path, expected_period: str) -> tuple[Parsed | None, str]:
    """Returns (parsed or None, source) with source "text" or "ocr".

    A scan is OCR'd with several tesseract settings until the arithmetic checks pass
    (a dropped digit is the typical failure); the least-bad attempt is kept otherwise.
    """
    pages, source = extract(path)
    best = _parse_pages(pages)
    if best is not None:
        check(best, expected_period)
    if source == "ocr":
        for dpi, psm in OCR_VARIANTS[1:]:
            if best is not None and not best.warnings:
                break
            cand = _parse_pages(ocr_pages(path, dpi, psm))
            if cand is None:
                continue
            check(cand, expected_period)
            if best is None or len(cand.warnings) < len(best.warnings):
                best = cand
    return best, source
