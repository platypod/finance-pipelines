"""Synthetic Crédit Agricole exports (invented names, numbers and merchants only), in the real layout."""

from __future__ import annotations


def fmt(x: float) -> str:
    s = f"{abs(x):,.2f}".replace(",", " ").replace(".", ",")
    return s


def row(booking, value, label_lines, amount):
    """One operation. label_lines: the card/transfer text as printed on several lines."""
    body = "\n".join(label_lines) + "\n\n\n"
    debit, credit = (fmt(amount), "") if amount < 0 else ("", fmt(amount))
    return f'{booking};{value};"{body}";{debit};{credit};\n'


def card(booking, merchant, purchase, amount, detail=""):
    label = [f"Paiement par carte", f"X9999 {merchant} {purchase}" + (f" - {detail}" if detail else "")]
    return row(booking, booking, label, amount)


def account_block(kind, number, balance, balance_date, period, rows, holder=None):
    lines = ["\n\n"]
    if holder:
        lines.append(f"{holder}\n")
    lines.append(f"{kind} carte n° {number};\n" if kind.startswith("Compte") else f"{kind} carte n° {number}\n")
    lines.append(f"Solde au {balance_date} {fmt(balance)} \n\n")
    lines.append(f"Liste des opérations du compte entre le {period[0]} et le {period[1]};\n\n")
    lines.append("Date;Date valeur;Libellé;Débit euros;Crédit euros;\n")
    lines.extend(rows)
    return "".join(lines)


def export(downloaded, blocks) -> bytes:
    """ISO-8859-1 like the bank's file."""
    text = f"\nTéléchargement du {downloaded};\n\n" + "".join(blocks)
    return text.encode("latin-1")
