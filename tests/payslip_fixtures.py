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


def modern_pages_2026_09() -> list[Page]:
    """The 2026-09+ template: period as `Du dd/mm/yyyy au dd/mm/yyyy`, labels at x0=45 with the rotated
    section letters drawn at x0=36 (tiny), and the employee header block repeated on page 3."""
    def header_block(top0):
        words, t = [], top0
        def row(text, x0=31, **kw):
            nonlocal t
            t += 10
            words.extend(label(text, t, x0, **kw))
        words += label("Bulletin de paie", top0 - 20, 40)
        words += label("Du 01/09/2099 au 25/09/2099", top0 - 10, 463)
        row("N° SIRET : 12345678901234 Minimum coefficient")
        row("N° APE : 6202A Début de contrat : 10/02/2020")
        row("TECHNIQUES, CABINETS Catégorie : Ingénieurs et Cadres", 116)
        # "- 100 - 1.2": the value that used to be read as a table number (x1=373, minus detached)
        words += [left("-", 360.0, t), w("1.2", 373, t)]
        row("(SYNTEC) - 1486", 141)
        return words, t

    p1 = Page(596, 842, [*label("Voici votre bulletin de paie de septembre 2099", 20)])
    words, t = header_block(40)
    t += 10
    words += label("DÉSIGNATION BASE", t, 150)
    def row(lbl, glyph=None, **cols):
        nonlocal t
        t += 10
        anchors = dict(base=298, rate=352, emp=404, employer=478)
        if glyph:
            words.append(Word(glyph, 36.2, 36.2 + 1.5, t, 3.3))  # rotated margin letter, tiny
        words.extend(label(lbl, t, 45))
        for c, v in cols.items():
            words.append(w(v, anchors[c], t))
    row("Salaire de base", base="151,67", rate="26,0000", emp="4 000,00")
    row("Indemnité compensatrice de Congés Payés", glyph="u", emp="6 000,00")
    row("Prime de commission", emp="1 000,00")
    row("Rémunération brute", emp="11 000,00")
    row("Base", glyph="e", base="11 000,00", employer="400,00")
    row("TOTAL COTISATIONS & CONTRIBUTIONS SALARIALES", emp="100,00")
    row("TOTAL COTISATIONS & CONTRIBUTIONS PATRONALES", employer="400,00")
    row("Net à payer avant impôt sur le revenu", employer="10 900,00")
    row("Net payé en euros ( Virement )", employer="9 900,00")
    p2 = Page(596, 842, words)
    words3, t3 = header_block(40)
    t3 += 10
    words3 += label("Impôt sur le revenu", t3, 31) + label("Soldes de congés", t3, 375)
    t3 += 10
    words3 += label("Impôt sur le revenu prélevé à la source", t3, 33) + [w("10 900,00", 224, t3), w("10,00", 287, t3), w("1 000,00", 363, t3)]
    return [p1, p2, Page(596, 842, words3)]


def matmut_page() -> Page:
    """2026-10+ layout. Right edges: base 315, rate 366, salary amount 441, employer rate 496, employer amount 573.
    Invented figures that satisfy every cross-check: gross 2600.00 = 3000 + 100 - 500; employee 358.80; employer 643.90."""
    words = [*label("BULLETIN DE SALAIRE OCTOBRE 2099", 20, 200), *label("Date début paie : 01/10/2099 Date fin paie : 31/10/2099", 40, 30),
             *label("SIRET : 12345678901234", 60, 30),
             *label("BASE OU PART SALARIALE PART PATRONALE", 251, 280), *label("LIBELLE", 263, 40),
             *label("NOMBRE Taux Montant Taux Montant", 263, 300)]
    t = 270
    cols = dict(base=315, rate=366, emp=441, e_rate=496, employer=573)

    def row(lbl, dup=False, **vals):
        nonlocal t
        t += 9
        words.extend(label(lbl, t))
        for c, v in vals.items():
            words.append(w(v, cols[c], t))
            if dup and c == "emp":  # the PDF prints some rows twice on top of each other
                words.append(w(v, cols[c], t))

    row("Salaire de base forf. 213 jours", emp="3000.00")
    row("Prime exceptionnelle", emp="100.00")
    row("Abs. Congé sans solde du 05-10-99 au 09-10-99", base="5.00", rate="100.000", emp="-500.00")
    row("Salaire brut", emp="2600.00")
    row("COTISATIONS ET CONTRIBUTIONS")
    row("SANTE")
    row("Sécurité Sociale-Maladie Maternité Invalidité")
    row("Décès", base="2600.00", e_rate="13.000", employer="338.00")  # the label wraps: the numbers sit on the 2nd row
    row("Complémentaire garanties frais de santé", emp="4.40", employer="83.60")
    row("RETRAITE")
    row("Sécurité Sociale plafonnée", base="2600.00", rate="6.900", emp="179.40", e_rate="8.550", employer="222.30")
    row("CSG déductible de l'impôt sur le revenu", dup=True, base="2554.00", rate="6.800", emp="175.00")
    row("TOTAL DES COTISATIONS ET", dup=True, emp="358.80", employer="643.90")
    row("CONTRIBUTIONS OBLIGATOIRES")
    row("MONTANT NET SOCIAL", emp="2241.20")
    row("REMBOURSEMENTS ET DÉDUCTIONS DIVERSES")
    row("Restaurant Exemple mois précédent", emp="-5.00")
    row("Montant net à payer avant impôt sur le revenu", emp="2236.20")
    row("IR PRÉLEVÉ À LA SOURCE (taux non perso)", base="2300.00", rate="5.000", emp="-115.00")
    words += label("Date de paiement : 28/10/2099", 650, 30)
    words += label("NET À PAYER :", 680, 30) + label("Réglé par", 691, 30) + [w("2121.20", 559, 691)]
    words += label("Total versé par Allègement de", 712, 30) + [w("4 000.00", 491, 729), w("0.00", 553, 729)]
    words += label("Brut mensuel Net fiscal mensuel Plafond mensuel PAS annuel", 745, 30)
    words += [w("2600.00", 77, 758), w("2300.00", 156, 758), w("1550.00", 235, 758), w("115.00", 308, 758)]
    words += label("Brut cumulé Net fiscal cumulé Plafond cumulé HC/HS exo. mensuel net HC/HS exo.annuel net", 772, 30)
    words += [w("2600.00", 77, 783), w("2300.00", 156, 783), w("1950.00", 235, 783), w("0.00", 306, 783), w("0.00", 386, 783)]
    return Page(595.0, 842.0, words)
