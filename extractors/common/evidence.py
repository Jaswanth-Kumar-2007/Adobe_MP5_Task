import csv
from datetime import date
from pathlib import Path
from typing import Any


EVIDENCE_COLUMNS = [
    "record_id",
    "record_type",
    "extracted_information",
    "pdf_page",
    "source_heading_or_section",
    "exact_supporting_quotation",
    "source_url",
    "retrieved_on",
    "source_type",
]


def create_evidence_record(
    record_id: str,
    record_type: str,
    extracted_information: str,
    pdf_page: int | str,
    quotation: str,
    source_heading: str = "",
    source_url: str = "",
    source_type: str = "official_pdf",
) -> dict[str, Any]:
    """Create a standardized source-evidence record."""

    return {
        "record_id": record_id,
        "record_type": record_type,
        "extracted_information": extracted_information,
        "pdf_page": pdf_page,
        "source_heading_or_section": source_heading,
        "exact_supporting_quotation": quotation,
        "source_url": source_url,
        "retrieved_on": date.today().isoformat(),
        "source_type": source_type,
    }


def save_evidence_csv(
    records: list[dict[str, Any]],
    output_path: str | Path,
) -> None:
    """Save evidence records to CSV."""

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=EVIDENCE_COLUMNS
        )

        writer.writeheader()

        for record in records:

            writer.writerow({
                column: record.get(column, "")
                for column in EVIDENCE_COLUMNS
            })


def append_evidence_csv(
    records: list[dict[str, Any]],
    output_path: str | Path,
) -> None:
    """
    Append evidence records without replacing existing evidence.
    """

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    file_exists = output_path.exists()

    with output_path.open(
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=EVIDENCE_COLUMNS
        )

        if not file_exists:
            writer.writeheader()

        for record in records:

            writer.writerow({
                column: record.get(column, "")
                for column in EVIDENCE_COLUMNS
            })