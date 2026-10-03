"""PDF -> pages of words. pdfplumber for text PDFs, tesseract for print-to-PDF scans.

Five of the 79 historical payslips carry no text layer at all (printed to PDF as
outlines), so OCR is part of the pipeline, not an afterthought. OCR needs the
`pdftoppm` and `tesseract` binaries (installed in the image); without them such a
file is reported as `needs_ocr` instead of failing the run.
"""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import pdfplumber

from .words import Page, Word

OCR_VARIANTS = [(300, 6), (400, 6), (300, 4), (400, 4), (500, 6), (300, 11)]  # (dpi, tesseract psm), tried in turn
MIN_WORDS = 40  # a payslip page that parses to fewer words has no usable text layer


class NeedsOcr(RuntimeError):
    """No text layer and no OCR tooling available."""


def extract(path: Path) -> tuple[list[Page], str]:
    """Returns (pages, source) with source in {"text", "ocr"}."""
    pages = _text_pages(path)
    if sum(len(p.words) for p in pages) >= MIN_WORDS:
        return pages, "text"
    return ocr_pages(path, *OCR_VARIANTS[0]), "ocr"


def _text_pages(path: Path) -> list[Page]:
    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            words = [
                Word(w["text"], w["x0"], w["x1"], w["top"], w.get("size", 0.0))
                for w in p.extract_words(extra_attrs=["size"])
            ]
            pages.append(Page(float(p.width), float(p.height), words))
    return pages


def ocr_pages(path: Path, dpi: int, psm: int) -> list[Page]:
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        raise NeedsOcr(f"{path.name}: no text layer and pdftoppm/tesseract are not installed")
    lang = "fra" if "fra" in subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout else "eng"
    scale = 72.0 / dpi
    pages: list[Page] = []
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(path), f"{tmp}/p"], check=True)
        for img in sorted(Path(tmp).glob("p-*.png")):
            out = subprocess.run(
                ["tesseract", str(img), "-", "-l", lang, "--psm", str(psm), "tsv"],
                capture_output=True, text=True, check=True,
            ).stdout
            words = []
            for r in csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE):
                text = (r.get("text") or "").strip()
                if not text or float(r.get("conf") or -1) < 0:
                    continue
                left, top, w, h = (float(r[k]) for k in ("left", "top", "width", "height"))
                words.append(Word(text, left * scale, (left + w) * scale, top * scale, h * scale))
            pages.append(Page(595.0, 842.0, words))
    return pages
