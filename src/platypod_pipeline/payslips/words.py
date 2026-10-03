"""Geometry toolkit shared by all layouts: words, rows, tokens, French numbers.

Everything works on *positions*, not on flowing text: a payslip is a table, and
which column a number sits in decides what it means. Positions are in PDF points
(OCR output is rescaled to them), so the same column anchors work for both.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

NUMBER = re.compile(r"^-?\d{1,3}(?:[  ]\d{3})*[.,]\d+$|^-?\d+[.,]\d+$")
THOUSANDS_PREFIX = re.compile(r"^-?\d{1,3}$")
THOUSANDS_TAIL = re.compile(r"^\d{3}[.,]\d+$")


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    size: float = 0.0


@dataclass
class Page:
    width: float
    height: float
    words: list[Word]


@dataclass
class Token:
    text: str
    x0: float
    x1: float
    top: float
    size: float = 0.0

    @property
    def is_number(self) -> bool:
        return bool(NUMBER.match(self.text))


@dataclass
class Row:
    tokens: list[Token] = field(default_factory=list)
    page: int = 0

    @property
    def top(self) -> float:
        return self.tokens[0].top if self.tokens else 0.0

    def text(self, *, x_max: float = 1e9, x_min: float = -1e9, numbers: bool = True) -> str:
        return " ".join(
            t.text for t in self.tokens if x_min <= t.x0 and t.x1 <= x_max and (numbers or not t.is_number)
        )

    def numbers(self, *, x_max: float = 1e9, x_min: float = -1e9) -> list[Token]:
        return [t for t in self.tokens if t.is_number and x_min <= t.x0 and t.x1 <= x_max]


def fold(text: str) -> str:
    """Lower-case, accent-free: layout detection and label matching survive OCR accent loss."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _merge(words: list[Word], gap: float) -> list[Token]:
    """Join thousands groups (`5` + `525,98`), then detached minus signs, into single tokens.

    Two passes because the minus precedes the *whole* number: `-` `1` `020,83` is -1 020,83,
    and a one-pass pairwise merge would see `-` followed by `1` (not yet a number) and lose the sign.
    """
    def close(a: Word | Token, b: Word | Token) -> bool:
        return abs(b.top - a.top) < 3 and 0 <= b.x0 - a.x1 <= gap

    # pass 1: thousands groups
    tokens: list[Token] = []
    i = 0
    while i < len(words):
        w = words[i]
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is not None and close(w, nxt) and THOUSANDS_PREFIX.match(w.text) and THOUSANDS_TAIL.match(nxt.text):
            tokens.append(Token(f"{w.text} {nxt.text}", w.x0, nxt.x1, w.top, nxt.size))
            i += 2
        else:
            tokens.append(Token(w.text, w.x0, w.x1, w.top, w.size))
            i += 1
    # pass 2: a lone minus directly in front of a number
    out: list[Token] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if nxt is not None and t.text in {"-", "\u2212"} and close(t, nxt) and NUMBER.match(nxt.text):
            out.append(Token(f"-{nxt.text}", t.x0, nxt.x1, t.top, nxt.size))
            i += 2
        else:
            out.append(t)
            i += 1
    return out


def rows_of(pages: list[Page], *, row_tol: float = 3.0, merge_gap: float = 6.0) -> list[Row]:
    rows: list[Row] = []
    for pno, page in enumerate(pages):
        words = sorted(page.words, key=lambda w: (round(w.top), w.x0))
        current: list[Word] = []
        anchor = None
        groups: list[list[Word]] = []
        for w in words:
            if anchor is None or abs(w.top - anchor) > row_tol:
                if current:
                    groups.append(current)
                current, anchor = [w], w.top
            else:
                current.append(w)
        if current:
            groups.append(current)
        for g in groups:
            g.sort(key=lambda w: w.x0)
            rows.append(Row(_merge(g, merge_gap), pno))
    return rows


def nearest(x1: float, anchors: dict[str, float], tol: float = 10.0) -> str | None:
    """Column whose anchor is closest to a number's right edge, if within tolerance."""
    name, dist = min(((n, abs(x1 - a)) for n, a in anchors.items()), key=lambda p: p[1])
    return name if dist <= tol else None
