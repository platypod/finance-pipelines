"""Detect the bank of a statement file, parse it, and cross-check what was read."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import ca
from .model import ParsedBank


def _d(text: str):
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def check(p: ParsedBank) -> None:
    """Sanity checks that make a mis-parse loud. Appends to p.warnings (never raises)."""
    seen = set()
    for a in p.accounts:
        ref = f"…{a.last4}"
        if a.last4 in seen:
            p.warnings.append(f"account {ref} appears twice in one file")
        seen.add(a.last4)
        lo, hi = _d(a.period_from), _d(a.period_to)
        if not (lo and hi) or lo > hi:
            p.warnings.append(f"account {ref}: unreadable period {a.period_from!r}..{a.period_to!r}")
        if not _d(a.balance_date):
            p.warnings.append(f"account {ref}: unreadable balance date {a.balance_date!r}")
        for r in a.rows:
            b = _d(r.booking_date)
            if b is None:
                p.warnings.append(f"account {ref} row {r.line_no}: unreadable date {r.booking_date!r}")
            elif lo and hi and not (lo <= b <= hi):
                p.warnings.append(f"account {ref} row {r.line_no}: dated {r.booking_date}, outside the export's period")
    if not p.accounts:
        p.warnings.append("no account found in the file")


def parse_statement(path: Path) -> ParsedBank | None:
    """Parsed + checked statement, or None when the file is not a known bank export."""
    raw = ca.decode(path.read_bytes())
    if not ca.looks_like_ca(raw):
        return None
    parsed = ca.parse(path)
    check(parsed)
    return parsed
