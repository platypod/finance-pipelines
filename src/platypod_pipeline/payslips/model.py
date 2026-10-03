from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawLine:
    """One table row, values exactly as printed (French/English number formats, spaces)."""

    line_no: int
    section: str  # brut | cotisations | other
    label: str
    base: str | None = None
    rate: str | None = None
    employee_gain: str | None = None
    employee_deduct: str | None = None
    employer_base: str | None = None
    employer_rate: str | None = None
    employer_amount: str | None = None


@dataclass
class Parsed:
    layout: str  # silae | modern
    summary: dict[str, str] = field(default_factory=dict)  # canonical key -> raw text
    lines: list[RawLine] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}
