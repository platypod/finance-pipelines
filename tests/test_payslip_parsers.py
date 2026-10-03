from decimal import Decimal

from payslip_fixtures import modern_pages, silae_page

from platypod_pipeline.payslips import modern, silae
from platypod_pipeline.payslips.parse import check, detect, num
from platypod_pipeline.payslips.words import Page, Row, Token, rows_of


def test_numbers_french_and_english():
    assert num("5 357,13") == Decimal("5357.13")
    assert num("3 193.44") == Decimal("3193.44")
    assert num("-860,00") == Decimal("-860.00")
    assert num("") is None and num(None) is None and num("abc") is None


def test_thousands_groups_and_detached_minus_are_merged():
    from payslip_fixtures import left, w

    page = Page(595, 842, [left("Base", 40, 10), w("5", 276, 10), left("525,98", 278, 10), left("-", 300, 10), left("28.00", 305, 10)])
    row = rows_of([page])[0]
    assert [t.text for t in row.numbers()] == ["5 525,98", "-28.00"]


def test_minus_in_front_of_a_thousands_grouped_amount_is_kept():
    from platypod_pipeline.payslips.words import Word

    # `-` `1` `020,83` as printed on an absence line (real x positions): the sign precedes the whole number
    page = Page(595, 842, [Word("5,00", 285.5, 298.2, 10), Word("-", 374.8, 376.6, 10), Word("1", 378.3, 382.1, 10), Word("020,83", 383.7, 404.0, 10)])
    assert [t.text for t in rows_of([page])[0].numbers()] == ["5,00", "-1 020,83"]


def test_gross_pay_elements_must_add_up_to_the_printed_gross():
    p = silae.parse([silae_page()])
    check(p, "2099-01")
    assert not any("gross pay elements" in m for m in p.warnings)
    p.lines[0].employee_gain = "3 100.00"  # a mis-read element
    check(p, "2099-01")
    assert any("gross pay elements" in m for m in p.warnings)


def test_layout_detection():
    assert detect([silae_page()]) == "silae"
    assert detect(modern_pages()) == "modern"
    assert detect([Page(595, 842, [])]) is None


def test_silae_summary_and_lines():
    p = silae.parse([silae_page()])
    assert p.layout == "silae"
    s = p.summary
    assert (s["period"], s["employer_siret"], s["payment_date"]) == ("2099-01", "12345678901234", "31/01/2099")
    assert (s["gross"], s["net_before_tax"], s["net_paid"]) == ("3 500.00", "2 962.68", "2 662.68")
    assert (s["employee_contributions"], s["employer_contributions"]) == ("505.32", "324.25")
    assert (s["pas_base"], s["pas_rate"], s["pas_amount"]) == ("3 000.00", "10.0000", "300.00")  # sign stripped
    assert (s["hours"], s["ytd_gross"], s["taxable_net"]) == ("151.67", "10 500.00", "3 012.00")
    assert (s["leave_cp_n1_balance"], s["leave_cp_n_balance"], s["leave_rtt_balance"]) == ("20.00", "12.50", "5.00")
    by = {l.label: l for l in p.lines}
    assert by["Salaire de base"].section == "brut" and by["Salaire de base"].employee_gain == "3 000.00"
    ss = by["Sécurité Sociale plafonnée"]
    assert (ss.section, ss.employee_deduct, ss.employer_amount, ss.employer_rate) == ("cotisations", "241.50", "299.25", "8.5500")
    assert by["Complémentaire - Santé"].employee_deduct == "25.00" == by["Complémentaire - Santé"].employer_amount
    assert by["Titres-restaurant"].section == "other"
    # summary rows are not lines
    assert not {"Salaire brut", "Net payé", "Total des cotisations et contributions"} & set(by)


def test_silae_arithmetic_checks_pass_on_consistent_data_and_catch_a_dropped_digit():
    p = silae.parse([silae_page()])
    check(p, "2099-01")
    assert p.warnings == []
    p.summary["net_paid"] = "662.68"  # what an OCR dropping a leading digit looks like
    check(p, "2099-01")
    assert any("net paid" in m for m in p.warnings)
    check(p, "2099-02")
    assert any("period" in m for m in p.warnings)


def test_modern_summary_lines_and_panels():
    p = modern.parse(modern_pages())
    assert p.layout == "modern"
    s = p.summary
    assert (s["period"], s["employer_siret"]) == ("2099-01", "12345678901234")
    assert (s["gross"], s["employee_contributions"], s["employer_contributions"]) == ("4 200,00", "563,38", "636,43")
    assert (s["net_social"], s["net_before_tax"], s["net_paid"]) == ("3 636,62", "3 572,62", "3 172,62")
    assert (s["pas_base"], s["pas_rate"], s["pas_amount"]) == ("3 900,00", "10,00", "400,00")
    assert (s["total_paid"], s["taxable_net"], s["hours"]) == ("7 000,00", "3 900,00", "154.35")
    assert (s["ytd_gross"], s["ytd_taxable_net"]) == ("12 600,00", "11 700,00")
    assert (s["leave_cp_n1_earned"], s["leave_cp_n_earned"], s["leave_rtt_earned"]) == ("26,00", "6,25", "6,64")
    labels = [l.label for l in p.lines]
    assert labels[0] == "Salaire de base"  # rotated margin letters dropped
    by = {l.label: l for l in p.lines}
    assert by["Salaire de base"].employee_gain == "4 000,00" and by["Salaire de base"].employee_deduct is None
    assert by["Sécurité sociale plafonnée"].employee_deduct == "276,35"
    assert by["Sécurité sociale plafonnée"].employer_amount == "342,43"
    assert by["Titres-restaurant"].section == "other" and by["Titres-restaurant"].employee_deduct == "64,00"
    assert by["Assurance maladie"].employer_amount == "294,00" and by["Assurance maladie"].employee_deduct is None


def test_modern_checks_consistent_data():
    p = modern.parse(modern_pages())
    # the synthetic employee/employer line sums are deliberately partial: only totals and identities are asserted
    check(p, "2099-01")
    assert not any("net paid" in m or "period" in m for m in p.warnings)
