#!/usr/bin/env python3

"""
UG Manual PDF Extractor
----------------------

Extracts academic-rule candidates from the IIT Bhilai UG Manual.

Outputs:
1. rules.csv
2. source_evidence.csv
3. ug_manual_review.csv

IMPORTANT:
- Extracted paragraphs are candidates, not confirmed academic rules.
- Every candidate retains its PDF page and section.
- Numeric limits are not automatically interpreted.
- No DSAI/OE/PE eligibility is inferred.
"""

import argparse
import csv
import hashlib
import re
from datetime import date
from pathlib import Path

import pdfplumber


RULE_COLUMNS = [
    "id",
    "category",
    "text",
    "numeric_limit",
    "unit",
    "applies_to",
    "source_url",
    "retrieved_on",
    "source_type",
]

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

REVIEW_COLUMNS = [
    "candidate_id",
    "pdf_page",
    "section",
    "category",
    "candidate_text",
    "review_status",
    "review_note",
]


DEFAULT_SOURCE_URL = (
    "https://www.iitbhilai.ac.in/index.php?pid=ug_manual"
)


# Detect numbered headings such as:
# 1 Introduction
# 2. Academic Regulations
# 2.1 Registration
# 2.1.1 Course Registration
HEADING_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)*\.?)\s+([A-Z][A-Za-z0-9 ,&()/\-:]{2,120})$"
)


def clean_text(text):
    """Remove unnecessary whitespace while preserving the text."""

    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def generate_id(section, page, text):
    """Generate a stable ID for an extracted candidate."""

    raw = f"{section}|{page}|{text}"

    digest = hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:12]

    return f"UGRULE_{digest}"


def identify_category(section, heading, text):
    """
    Assign a broad category using keywords.

    This is only a preliminary label.
    Human review is required.
    """

    combined = (
        f"{section} {heading} {text}"
    ).lower()

    if any(word in combined for word in [
        "open elective",
        "professional elective",
        "elective course",
        "elective",
    ]):
        return "electives"

    if any(word in combined for word in [
        "prerequisite",
        "pre-requisite",
        "pre requisite",
    ]):
        return "prerequisites"

    if any(word in combined for word in [
        "credit",
        "credits",
        "credit requirement",
    ]):
        return "credits"

    if any(word in combined for word in [
        "attendance",
        "shortage of attendance",
        "minimum attendance",
    ]):
        return "attendance"

    if any(word in combined for word in [
        "registration",
        "add/drop",
        "course withdrawal",
    ]):
        return "registration"

    if any(word in combined for word in [
        "grading",
        "grade",
        "cgpa",
        "sgpa",
        "probation",
        "academic standing",
    ]):
        return "grading_academic_standing"

    if any(word in combined for word in [
        "branch change",
        "programme change",
        "program change",
        "honours",
        "minor",
    ]):
        return "programme_options"

    if any(word in combined for word in [
        "b.tech",
        "btech",
        "programme requirement",
        "program requirement",
    ]):
        return "programme_requirements"

    return "general_academic_rule"


def is_heading(line):
    """Check whether a line looks like a numbered section heading."""

    return bool(HEADING_PATTERN.match(line.strip()))


def parse_heading(line):
    match = HEADING_PATTERN.match(line.strip())

    if not match:
        return None

    section = match.group(1).rstrip(".")
    heading = match.group(2).strip()

    return section, heading


def extract_pdf_pages(pdf_path):
    """Extract text page by page using pdfplumber."""

    extracted_pages = []

    with pdfplumber.open(pdf_path) as pdf:

        for page_number, page in enumerate(
            pdf.pages,
            start=1
        ):

            text = page.extract_text() or ""

            extracted_pages.append({
                "page": page_number,
                "text": text,
            })

    return extracted_pages


def extract_candidates(pages):
    """
    Extract paragraph candidates while preserving section context.

    The current section heading is carried across page boundaries.
    """

    candidates = []

    current_section = ""
    current_heading = ""

    buffer = []
    buffer_page = 1

    def save_buffer():

        nonlocal buffer

        text = clean_text(" ".join(buffer))

        buffer = []

        # Ignore short fragments such as isolated page numbers.
        if len(text) < 35:
            return

        category = identify_category(
            current_section,
            current_heading,
            text
        )

        candidates.append({
            "page": buffer_page,
            "section": current_section,
            "heading": current_heading,
            "category": category,
            "text": text,
        })

    for page_data in pages:

        page_number = page_data["page"]

        lines = page_data["text"].splitlines()

        for raw_line in lines:

            line = clean_text(raw_line)

            if not line:
                continue

            # Ignore isolated page numbers.
            if re.fullmatch(r"\d+", line):
                continue

            # A numbered heading starts a new section.
            if is_heading(line):

                save_buffer()

                parsed = parse_heading(line)

                if parsed:
                    current_section, current_heading = parsed

                buffer_page = page_number

                continue

            # Start a new candidate paragraph when a bullet begins.
            if re.match(
                r"^([-•▪●]|\(?[a-zivx]+\))\s+",
                line,
                re.IGNORECASE
            ) and buffer:

                save_buffer()
                buffer_page = page_number

            if not buffer:
                buffer_page = page_number

            buffer.append(line)

        # Flush at page end, but retain the current section heading.
        save_buffer()

    # Remove exact duplicate paragraphs.
    unique_candidates = []
    seen = set()

    for candidate in candidates:

        key = (
            candidate["section"],
            candidate["text"].casefold()
        )

        if key in seen:
            continue

        seen.add(key)
        unique_candidates.append(candidate)

    return unique_candidates


def write_csv(file_path, columns, rows):

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        file_path,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=columns
        )

        writer.writeheader()
        writer.writerows(rows)


def main():

    parser = argparse.ArgumentParser(
        description="Extract academic-rule candidates from UG Manual."
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to the UG Manual PDF."
    )

    parser.add_argument(
        "--out-dir",
        default="data/extracted/ug_manual",
        help="Output directory."
    )

    parser.add_argument(
        "--source-url",
        default=DEFAULT_SOURCE_URL,
        help="Official source URL of the manual."
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    output_dir = Path(args.out_dir)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"UG Manual PDF not found: {pdf_path}"
        )

    print("Reading UG Manual PDF...")

    pages = extract_pdf_pages(pdf_path)

    print(f"Read {len(pages)} pages.")

    candidates = extract_candidates(pages)

    print(
        f"Extracted {len(candidates)} candidate paragraphs."
    )

    retrieved_on = date.today().isoformat()

    rules = []
    evidence = []
    review = []

    for candidate in candidates:

        text = candidate["text"]
        section = candidate["section"]
        heading = candidate["heading"]
        page = candidate["page"]

        record_id = generate_id(
            section,
            page,
            text
        )

        rules.append({
            "id": record_id,
            "category": candidate["category"],
            "text": text,

            # Leave these blank for human verification.
            "numeric_limit": "",
            "unit": "",

            "applies_to": "UG",
            "source_url": args.source_url,
            "retrieved_on": retrieved_on,
            "source_type": "official_ug_manual_pdf",
        })

        evidence.append({
            "record_id": record_id,
            "record_type": "rule",
            "extracted_information": text,
            "pdf_page": page,
            "source_heading_or_section": (
                f"{section} {heading}".strip()
            ),
            "exact_supporting_quotation": text,
            "source_url": args.source_url,
            "retrieved_on": retrieved_on,
            "source_type": "official_ug_manual_pdf",
        })

        review.append({
            "candidate_id": record_id,
            "pdf_page": page,
            "section": section,
            "category": candidate["category"],
            "candidate_text": text,
            "review_status": "needs_human_review",
            "review_note": "",
        })

    write_csv(
        output_dir / "rules.csv",
        RULE_COLUMNS,
        rules
    )

    write_csv(
        output_dir / "source_evidence.csv",
        EVIDENCE_COLUMNS,
        evidence
    )

    write_csv(
        output_dir / "ug_manual_review.csv",
        REVIEW_COLUMNS,
        review
    )

    print("\nExtraction completed.")

    print(f"Rules: {len(rules)}")
    print(f"Evidence records: {len(evidence)}")

    print(f"\nOutput: {output_dir.resolve()}")

    print(
        "\nIMPORTANT: Review ug_manual_review.csv "
        "before merging the candidates into your main rules.csv."
    )


if __name__ == "__main__":
    main()