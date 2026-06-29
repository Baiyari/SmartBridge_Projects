"""
PDF ingestion for RBI / SEBI / FEMA regulatory circulars.

Uses PyMuPDF (fitz) to extract clean text and lightweight metadata
(circular number, date, regulator) from any PDF layout, with no
external server or OCR dependency required for native-text PDFs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

_CIRCULAR_NO_PATTERNS = [
    re.compile(r"(RBI/\d{4}-\d{2,4}/\d+)", re.IGNORECASE),
    re.compile(r"(SEBI/HO/[A-Z\-/]+/\d+)", re.IGNORECASE),
    re.compile(r"Circular\s*No[.:]?\s*([A-Za-z0-9/\-\.]+)", re.IGNORECASE),
]

_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{4})\b"
)


@dataclass
class ParsedCircular:
    """Structured representation of a parsed regulatory PDF."""

    source_path: str
    circular_number: str | None
    circular_date: str | None
    regulator: str
    page_count: int
    full_text: str
    pages: list[str] = field(default_factory=list)


def _detect_regulator(text: str) -> str:
    upper = text.upper()
    if "RESERVE BANK OF INDIA" in upper or "RBI/" in upper:
        return "RBI"
    if "SECURITIES AND EXCHANGE BOARD OF INDIA" in upper or "SEBI" in upper:
        return "SEBI"
    if "FOREIGN EXCHANGE MANAGEMENT ACT" in upper or "FEMA" in upper:
        return "FEMA"
    return "UNKNOWN"


def _extract_circular_number(text: str) -> str | None:
    for pattern in _CIRCULAR_NO_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _extract_circular_date(text: str) -> str | None:
    match = _DATE_PATTERN.search(text)
    return match.group(1) if match else None


def parse_pdf(pdf_path: str | Path) -> ParsedCircular:
    """Parse a single regulatory circular PDF into structured text + metadata.

    Raises:
        FileNotFoundError: if pdf_path does not exist.
        ValueError: if the PDF has no extractable text (e.g. scanned image
            without OCR), since obligation extraction requires real text.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pages.append(page.get_text("text"))
        page_count = doc.page_count

    full_text = "\n".join(pages).strip()
    if not full_text:
        raise ValueError(
            f"No extractable text found in {pdf_path.name}. "
            f"This file may be a scanned image requiring OCR, which is "
            f"outside RegIntel's current free-tier pipeline."
        )

    # Only the first ~2 pages are needed for header metadata detection.
    header_text = "\n".join(pages[:2])

    return ParsedCircular(
        source_path=str(pdf_path),
        circular_number=_extract_circular_number(header_text),
        circular_date=_extract_circular_date(header_text),
        regulator=_detect_regulator(header_text),
        page_count=page_count,
        full_text=full_text,
        pages=pages,
    )


def parse_directory(directory: str | Path) -> list[ParsedCircular]:
    """Parse every PDF in a directory. Skips files that fail to parse,
    printing a warning rather than aborting the whole batch."""
    directory = Path(directory)
    results: list[ParsedCircular] = []
    for pdf_file in sorted(directory.glob("*.pdf")):
        try:
            results.append(parse_pdf(pdf_file))
        except (ValueError, RuntimeError) as exc:
            print(f"[ingestion] Skipping {pdf_file.name}: {exc}")
    return results
