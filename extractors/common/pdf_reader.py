from pathlib import Path
from typing import Any

import pdfplumber


def read_pdf_pages(pdf_path: str | Path) -> list[dict[str, Any]]:
    """
    Extract text from every page of a PDF.

    Returns:
        [
            {
                "page_number": 1,
                "text": "...",
            },
            ...
        ]
    """

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file: {pdf_path}")

    pages = []

    try:
        with pdfplumber.open(pdf_path) as pdf:

            for page_number, page in enumerate(pdf.pages, start=1):

                text = page.extract_text(
                    x_tolerance=2,
                    y_tolerance=3
                ) or ""

                pages.append({
                    "page_number": page_number,
                    "text": text
                })

    except Exception as exc:
        raise RuntimeError(
            f"Failed to read PDF {pdf_path}: {exc}"
        ) from exc

    return pages


def read_pdf_tables(pdf_path: str | Path) -> list[dict[str, Any]]:
    """
    Extract tables from all PDF pages.

    Returns:
        [
            {
                "page_number": 1,
                "tables": [...]
            },
            ...
        ]
    """

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    results = []

    try:
        with pdfplumber.open(pdf_path) as pdf:

            for page_number, page in enumerate(pdf.pages, start=1):

                tables = page.extract_tables() or []

                cleaned_tables = []

                for table in tables:

                    cleaned_rows = []

                    for row in table:

                        cleaned_rows.append([
                            str(cell).strip() if cell is not None else ""
                            for cell in row
                        ])

                    cleaned_tables.append(cleaned_rows)

                results.append({
                    "page_number": page_number,
                    "tables": cleaned_tables
                })

    except Exception as exc:
        raise RuntimeError(
            f"Failed to extract PDF tables: {exc}"
        ) from exc

    return results


def get_pdf_page_count(pdf_path: str | Path) -> int:
    """Return the total number of pages in a PDF."""

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)