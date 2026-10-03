"""Synthetic payslip pages: words placed where each layout puts them. Invented numbers only."""

from platypod_pipeline.payslips.words import Page, Word

CH = 4.0  # approx. glyph width in points


def w(text, x1, top, size=6.7):
    """Word whose right edge is x1 (numbers are right-aligned in the real layouts)."""
    return Word(text, x1 - CH * len(text), x1, top, size)


def left(text, x0, top, size=6.7):
    return Word(text, x0, x0 + CH * len(text), top, size)


def label(text, top, x0=40, size=6.7):
    out, x = [], x0
    for part in text.split():
        out.append(left(part, x, top, size))
        x += CH * len(part) + 3
    return out


def silae_page() -> Page:
    """Anchors: base 282, rate 324, deduct 372, gain 426, e_base 474, e_rate 516, e_amount 552."""
    words = [*label("Période : Janvier 2099", 30, 317), *label("Siret : 12345678901234", 54, 6),
             *label("Eléments de paie", 110, 121), left("Base", 262, 110)]
    t = 130
    def row(lbl, **cols):
        nonlocal t
        t += 10
        anchors = dict(base=282, rate=324, deduct=372, gain=426, e_base=474, e_rate=516, e_amount=552)
        words.extend(label(lbl, t))
        for c, v in cols.items():
            if v.startswith("- "):  # the real PDFs print the minus as a separate word
                words.append(w(v[2:], anchors[c], t))
                words.append(w("-", anchors[c] - CH * len(v[2:]) - 4, t))
            else:
                words.append(w(v, anchors[c], t))
    row("Salaire de base", base="151.67", rate="20.0000", gain="3 000.00")
    row("Prime de mission", gain="500.00")
    row("Salaire brut", gain="3 500.00")
    row("Sécurité Sociale plafonnée", base="3 500.00", rate="6.9000", deduct="241.50", e_base="3 500.00", e_rate="8.5500", e_amount="299.25")
    row("Complémentaire - Santé", deduct="25.00", e_amount="25.00")
    row("CSG déduct. de l'impôt sur le revenu", base="3 512.00", rate="6.8000", deduct="238.82")
    row("Total des cotisations et contributions", deduct="505.32", e_amount="324.25")
    row("Titres-restaurant", base="10.00", rate="3.2000", deduct="32.00", e_base="10.00", e_rate="4.8000", e_amount="48.00")
    row("Net à payer avant impôt sur le revenu", gain="2 962.68")
    row("Impôt sur le revenu prélevé à la source - PAS", base="3 000.00", rate="- 10.0000", deduct="300.00")
    row("Net payé", gain="2 662.68")
    # totals + leave
    words += label("Heures Heures suppl. Brut Plafond S.S. Net imposable", 300, 52) + [left("Plafond", 215, 300)]
    for lbl, y in (("Mensuel", 310), ("Annuel", 320)):
        words += label(lbl, y, 4)
        for col, x, v in (("hours", 90, "151.67"), ("gross", 205, "3 500.00"), ("taxable_net", 320, "3 012.00")):
            words.append(w(v if lbl == "Mensuel" else "10 500.00", x, y))
    words += label("Acquis", 340, 7) + [w("25.00", 90, 340), w("12.50", 148, 340), w("5.00", 205, 340)]
    words += label("Solde", 350, 7) + [w("20.00", 90, 350), w("12.50", 148, 350), w("5.00", 205, 350)]
    words += label("Paiement le 31/01/2099 par Virement", 360, 411)
    return Page(595, 842, words)


def modern_pages() -> list[Page]:
    """Anchors: base 298, rate 352, emp 404, employer 478. Page 1 is ignored by the parser."""
    p1 = Page(596, 842, [*label("EN EUROS - janvier 2099", 20)])
    words = [*label("N° SIRET: 12345678901234 Début de période: 01/01/2099", 40, 40), *label("DÉSIGNATION BASE", 60, 40)]
    t = 100
    def row(lbl, margin="", **cols):
        nonlocal t
        t += 10
        anchors = dict(base=298, rate=352, emp=404, employer=478)
        if margin:
            words.append(left(margin, 22, t))
        words.extend(label(lbl, t, 34))
        for c, v in cols.items():
            words.append(w(v, anchors[c], t))
    row("Salaire de base", margin="r", base="151,67", rate="26,0000", emp="4 000,00")
    row("Prime de mission", emp="200,00")
    row("Rémunération brute", emp="4 200,00")
    words.append(left("1", 100, t, size=6.0))  # footnote marker
    row("Assurance maladie", base="4 200,00", employer="294,00")
    row("Sécurité sociale plafonnée", base="4 005,00", rate="6,9000", emp="276,35", employer="342,43")
    row("CSG déductible de l'impôt sur le revenu", base="4 221,00", rate="6,8000", emp="287,03")
    row("TOTAL COTISATIONS & CONTRIBUTIONS SALARIALES", emp="563,38")
    row("TOTAL COTISATIONS & CONTRIBUTIONS PATRONALES", employer="636,43")
    row("Titres-restaurant", base="20,00", rate="3,2000", emp="64,00", employer="96,00")
    row("Montant net social", employer="3 636,62")
    row("Net à payer avant impôt sur le revenu", employer="3 572,62")
    row("Net payé en euros ( Virement )", employer="3 172,62")
    # bottom two-panel block
    t += 10
    words += label("Impôt sur le revenu", t, 22) + label("Soldes de congés", t, 375)
    t += 10
    words += label("Montant", t, 337) + label("CP N-1 CP N RTT", t, 438)
    t += 10
    words += label("Impôt sur le revenu prélevé à la source", t, 22) + [w("3 900,00", 224, t), w("10,00", 287, t), w("400,00", 363, t)]
    words += label("Acquis", t, 375) + [w("26,00", 457, t), w("6,25", 505, t), w("6,64", 554, t)]
    t += 10
    words += label("Total versé par l'employeur", t, 22) + [w("7 000,00", 363, t)] + label("Salaire brut", t, 375) + [w("12 600,00", 571, t)]
    t += 10
    words += label("Net imposable", t, 22) + [w("3 900,00", 363, t)] + label("Net imposable", t, 375) + [w("11 700,00", 571, t)]
    t += 10
    words += label("Temps travaillé ce mois", t, 22) + [w("154.35", 357, t)]
    return [p1, Page(596, 842, words)]
