from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BankRow:
    line_no: int
    booking_date: str  # dd/mm/yyyy, as printed
    value_date: str
    label: str  # multi-line in the export, whitespace collapsed
    debit: str  # "10,50" or ""
    credit: str


@dataclass
class BankAccount:
    kind: str  # "Compte de Dépôt", "Livret A", "LDD Solidaire", ...
    last4: str  # the only part of the account number that is ever kept
    number_digits: int
    balance: str  # as printed, at balance_date
    balance_date: str
    period_from: str
    period_to: str
    rows: list[BankRow] = field(default_factory=list)


@dataclass
class ParsedBank:
    bank: str
    exported_on: str | None
    accounts: list[BankAccount] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
