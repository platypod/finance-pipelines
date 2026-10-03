"""Optional: parse the real payslip archive (PAYSLIPS_DIR) and require every file to pass every check.

Reads personal data but asserts only structure/identities and prints nothing from it.
"""

import os
from pathlib import Path

import pytest

from platypod_pipeline.payslips.parse import parse_pdf
from platypod_pipeline.pipelines.payslips import discover

ROOT = os.environ.get("PAYSLIPS_DIR")
pytestmark = pytest.mark.skipif(not ROOT or not Path(ROOT).is_dir(), reason="set PAYSLIPS_DIR to the real archive")


def test_every_real_payslip_parses_clean():
    bad = {}
    files = discover(Path(ROOT))
    assert files, "no payslips found"
    for path, period in files:
        parsed, _source = parse_pdf(path, period)
        if parsed is None or parsed.warnings:
            bad[period] = "no layout" if parsed is None else parsed.warnings[:2]
    assert not bad, bad
