"""Reference data of the bank pipeline: accounts, classification rules, overrides, taxonomy.

The *private* inputs live next to the statements (they describe your life, so they never go in this public repo):

    <BANK_DIR>/accounts.yaml    which statement account is whose, and who may see its figures   (required)
    <BANK_DIR>/rules.yaml       your own classification rules, consulted before the generic ones   (optional)
    <BANK_DIR>/overrides.csv    per-transaction corrections, always win                              (optional)

Generic inputs ship with the image (`reference/taxonomy.yaml`, `reference/default-rules.yaml`). Everything is
validated here and then replaced wholesale in `silver.bank_account|bank_rule|bank_override` on every run, so the
files are the single source of truth and the tables only a queryable copy.
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg
import yaml

from .. import db
from ..config import Settings

LOGIN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
VISIBILITY = re.compile(r"^(group:[a-z0-9][a-z0-9._-]*|[a-z0-9][a-z0-9._-]*)$")
ACCOUNT_KINDS = {"current", "savings"}
FAMILIES = {"card", "direct_debit", "transfer_in", "transfer_out", "cash", "refund", "interest", "fees", "payment", "other"}
RULE_KEYS = {"id", "family", "direction", "label", "amount_min", "amount_max", "account", "set"}


class ReferenceError(ValueError):
    """Invalid reference data; the message lists every problem found."""


def load_taxonomy(settings: Settings) -> dict:
    return yaml.safe_load((settings.root / "reference" / "taxonomy.yaml").read_text())


def _check_set(where: str, s: dict, tax: dict, errors: list[str]) -> None:
    cat, sub, nec = s.get("category"), s.get("subcategory"), s.get("necessity")
    if cat not in tax["categories"]:
        errors.append(f"{where}: unknown category {cat!r}")
    elif sub not in tax["categories"][cat]:
        errors.append(f"{where}: {sub!r} is not a subcategory of {cat!r} (allowed: {', '.join(tax['categories'][cat])})")
    if nec is not None and nec not in tax["necessity"]:
        errors.append(f"{where}: unknown necessity {nec!r} (allowed: {', '.join(tax['necessity'])})")


def load_accounts(path: Path) -> list[dict]:
    if not path.exists():
        raise ReferenceError(f"{path.name} is missing: it maps each statement account (bank + last 4 digits) to a person")
    doc = yaml.safe_load(path.read_text()) or {}
    errors: list[str] = []
    out, aliases, keys = [], set(), set()
    for i, a in enumerate(doc.get("accounts", []), 1):
        where = f"accounts[{i}]"
        alias = str(a.get("alias", "")).strip()
        bank, last4 = str(a.get("bank", "")).strip().lower(), str(a.get("last4", "")).strip()
        if not alias or alias in aliases:
            errors.append(f"{where}: alias missing or duplicated ({alias!r})")
        if bank != "ca":
            errors.append(f"{where}: unsupported bank {bank!r} (supported: ca)")
        if not re.fullmatch(r"\d{4}", last4):
            errors.append(f"{where}: last4 must be exactly 4 digits (quote it in YAML)")
        if (bank, last4) in keys:
            errors.append(f"{where}: ({bank}, {last4}) is mapped twice")
        if a.get("kind") not in ACCOUNT_KINDS:
            errors.append(f"{where}: kind must be one of {sorted(ACCOUNT_KINDS)}")
        person = str(a.get("person", "")).strip()
        if not LOGIN.match(person):
            errors.append(f"{where}: person {person!r} must be a lower-case login-like name (use 'joint' for a shared account)")
        visibility = str(a.get("visibility", "")).strip()
        if not VISIBILITY.match(visibility):
            errors.append(f"{where}: visibility must be a login or group:<name>, got {visibility!r}")
        holders = a.get("holders") or [person]
        aliases.add(alias)
        keys.add((bank, last4))
        out.append({"alias": alias, "bank": bank, "last4": last4, "kind": a.get("kind"), "person": person,
                    "holders": ",".join(str(h) for h in holders), "visibility": visibility})
    if not out:
        errors.append("no accounts listed")
    if errors:
        raise ReferenceError(f"{path.name}:\n  " + "\n  ".join(errors))
    return out


def _rules_from(path: Path, origin: str, tax: dict, errors: list[str]) -> list[dict]:
    doc = yaml.safe_load(path.read_text()) or {}
    out = []
    for i, r in enumerate(doc.get("rules", []), 1):
        where = f"{path.name} rule {r.get('id', i)!r}"
        extra = set(r) - RULE_KEYS
        if extra:
            errors.append(f"{where}: unknown keys {sorted(extra)}")
        if r.get("family") is not None and r["family"] not in FAMILIES:
            errors.append(f"{where}: unknown family {r['family']!r} (allowed: {', '.join(sorted(FAMILIES))})")
        if r.get("direction") not in (None, "debit", "credit"):
            errors.append(f"{where}: direction must be debit or credit")
        if not any(r.get(k) is not None for k in ("family", "label", "direction", "amount_min", "amount_max", "account")):
            errors.append(f"{where}: a rule with no condition would match everything")
        _check_set(where, r.get("set") or {}, tax, errors)
        s = r.get("set") or {}
        out.append({"rule_id": str(r.get("id", f"{origin}-{i}")), "family": r.get("family"), "direction": r.get("direction"),
                    "label_regex": r.get("label"), "amount_min": r.get("amount_min"), "amount_max": r.get("amount_max"),
                    "account": r.get("account"), "category": s.get("category"), "subcategory": s.get("subcategory"),
                    "necessity": s.get("necessity"), "origin": origin})
    return out


def load_rules(private: Path | None, default: Path, tax: dict) -> list[dict]:
    errors: list[str] = []
    rules = (_rules_from(private, "private", tax, errors) if private and private.exists() else []) + _rules_from(default, "default", tax, errors)
    if errors:
        raise ReferenceError("rules:\n  " + "\n  ".join(errors))
    for n, r in enumerate(rules, 1):  # file order is priority: private rules first, then the generic ones
        r["priority"] = n
    return rules


def _parse_date(text: str) -> date | None:
    text = text.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unreadable date {text!r} (use YYYY-MM-DD or DD/MM/YYYY)")


def load_overrides(path: Path | None, tax: dict) -> list[dict]:
    if not path or not path.exists():
        return []
    errors: list[str] = []
    out = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), 2):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            if not row or not any(row.values()):
                continue
            where = f"{path.name} line {n}"
            try:
                d = _parse_date(row.get("date", ""))
                amt = Decimal(row["amount"].replace(" ", "").replace(",", ".")) if row.get("amount") else None
            except (ValueError, InvalidOperation) as exc:
                errors.append(f"{where}: {exc}")
                continue
            if not (row.get("txn_id") or d or amt is not None or row.get("label_contains")):
                errors.append(f"{where}: needs txn_id, or at least one of date / amount / label_contains")
            _check_set(where, {**row, "necessity": row.get("necessity") or None}, tax, errors)
            out.append({"line_no": n, "txn_id": row.get("txn_id") or None, "account": row.get("account") or None,
                        "booking_date": d, "amount": abs(amt) if amt is not None else None,
                        "label_contains": row.get("label_contains") or None, "category": row.get("category"),
                        "subcategory": row.get("subcategory"), "necessity": row.get("necessity") or None})
    if errors:
        raise ReferenceError("overrides:\n  " + "\n  ".join(errors))
    return out


def write_reference(settings: Settings, accounts: list[dict], rules: list[dict], overrides: list[dict]) -> None:
    """Replace the three reference tables in one transaction (after checking every regex compiles in Postgres)."""
    with db.connect(settings, "transform", autocommit=False) as conn:
        bad = []
        for r in rules:
            if r["label_regex"]:
                try:
                    conn.execute("select '' ~* %s", (r["label_regex"],)).fetchone()
                except psycopg.Error as exc:
                    conn.rollback()
                    bad.append(f"rule {r['rule_id']!r}: invalid regex {r['label_regex']!r}: {str(exc).splitlines()[0]}")
        if bad:
            raise ReferenceError("rules:\n  " + "\n  ".join(bad))
        for t in ("silver.bank_account", "silver.bank_rule", "silver.bank_override"):
            conn.execute(f"delete from {t}")
        for a in accounts:
            conn.execute(
                "insert into silver.bank_account (alias, bank, last4, kind, person, holders, visibility)"
                " values (%(alias)s, %(bank)s, %(last4)s, %(kind)s, %(person)s, %(holders)s, %(visibility)s)", a)
        for r in rules:
            conn.execute(
                "insert into silver.bank_rule (priority, rule_id, family, direction, label_regex, amount_min, amount_max,"
                " account, category, subcategory, necessity, origin) values (%(priority)s, %(rule_id)s, %(family)s,"
                " %(direction)s, %(label_regex)s, %(amount_min)s, %(amount_max)s, %(account)s, %(category)s,"
                " %(subcategory)s, %(necessity)s, %(origin)s)", r)
        for o in overrides:
            conn.execute(
                "insert into silver.bank_override (line_no, txn_id, account, booking_date, amount, label_contains,"
                " category, subcategory, necessity) values (%(line_no)s, %(txn_id)s, %(account)s, %(booking_date)s,"
                " %(amount)s, %(label_contains)s, %(category)s, %(subcategory)s, %(necessity)s)", o)
        conn.commit()
