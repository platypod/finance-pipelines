"""Crédit Agricole "Liste des opérations" CSV export.

One file holds several accounts (current accounts, Livret A, LDD, ...). Per account:

    <holder line, optional>
    <kind> carte n° <number>[;]
    Solde au dd/mm/yyyy <amount>
    Liste des opérations du compte entre le dd/mm/yyyy et le dd/mm/yyyy;
    Date;Date valeur;Libellé;Débit euros;Crédit euros;
    dd/mm/yyyy;dd/mm/yyyy;"label over
    several lines";10,50;;

ISO-8859-1, `;`-separated, decimal commas, thousands separated by spaces. There is no running balance per
row, only the balance at download time. The window is rolling (about 13 months), so consecutive exports
overlap. The holder line is deliberately not parsed: it carries names that have no business in a database.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from .model import BankAccount, BankRow, ParsedBank

TABLE_HEADER = re.compile(r"^Date;Date valeur;Libell[ée];D[ée]bit euros;Cr[ée]dit euros;\s*$", re.M)
ACCOUNT_LINE = re.compile(r"^(?P<kind>[^\n;]*?)\s*carte n°\s*(?P<number>\d+)\s*;?\s*$", re.M)
BALANCE = re.compile(r"^Solde au (?P<date>\d{2}/\d{2}/\d{4})\s+(?P<amount>-?[\d  ]+,\d{2})", re.M)
PERIOD = re.compile(r"entre le (?P<a>\d{2}/\d{2}/\d{4}) et le (?P<b>\d{2}/\d{2}/\d{4})")
EXPORTED = re.compile(r"T[ée]l[ée]chargement du (\d{2}/\d{2}/\d{4})")
DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
AMOUNT = re.compile(r"^\d{1,3}(?: \d{3})*,\d{2}$|^\d+,\d{2}$")


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def looks_like_ca(text: str) -> bool:
    return bool(TABLE_HEADER.search(text))


def parse(path: Path) -> ParsedBank:
    text = decode(path.read_bytes()).replace("\r\n", "\n").replace("\xa0", " ")
    res = ParsedBank(bank="ca", exported_on=None)
    if m := EXPORTED.search(text):
        res.exported_on = m.group(1)
    headers = list(TABLE_HEADER.finditer(text))
    if not headers:
        res.warnings.append("no 'Date;Date valeur;Libellé;…' table header found")
        return res
    for k, hm in enumerate(headers):
        before_start = headers[k - 1].end() if k else 0
        heading = text[before_start : hm.start()]
        table_end = headers[k + 1].start() if k + 1 < len(headers) else len(text)
        table = text[hm.end() : table_end]

        acct = list(ACCOUNT_LINE.finditer(heading))
        if not acct:
            res.warnings.append(f"table {k + 1}: no account line before it")
            continue
        a = acct[-1]  # the nearest one; earlier matches belong to the previous table's tail
        bal = list(BALANCE.finditer(heading))
        per = list(PERIOD.finditer(heading))
        account = BankAccount(
            kind=re.sub(r"\s+", " ", a.group("kind")).strip(),
            last4=a.group("number")[-4:],
            number_digits=len(a.group("number")),
            balance=bal[-1].group("amount").strip() if bal else "",
            balance_date=bal[-1].group("date") if bal else "",
            period_from=per[-1].group("a") if per else "",
            period_to=per[-1].group("b") if per else "",
        )
        if not bal:
            res.warnings.append(f"account …{account.last4}: no 'Solde au' line")
        if not per:
            res.warnings.append(f"account …{account.last4}: no period line")
        n = 0
        for rec in csv.reader(io.StringIO(table), delimiter=";", quotechar='"'):
            if len(rec) < 5 or not DATE.match(rec[0].strip()):
                continue  # heading text of the next account, blank lines
            n += 1
            row = BankRow(n, rec[0].strip(), rec[1].strip(), re.sub(r"\s+", " ", rec[2]).strip(), rec[3].strip(), rec[4].strip())
            problems = []
            if not DATE.match(row.value_date):
                problems.append("value date")
            if bool(row.debit) == bool(row.credit):
                problems.append("exactly one of debit/credit expected")
            for col, v in (("debit", row.debit), ("credit", row.credit)):
                if v and not AMOUNT.match(v):
                    problems.append(f"{col} {v!r}")
            if problems:
                res.warnings.append(f"account …{account.last4} row {n}: {', '.join(problems)}")
            account.rows.append(row)
        res.accounts.append(account)
    return res
