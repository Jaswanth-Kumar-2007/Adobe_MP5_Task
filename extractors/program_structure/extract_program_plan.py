import argparse
import csv
import re
import sys

from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from extractors.common.pdf_reader import read_pdf_pages
from extractors.common.text_cleaner import clean_pdf_text, split_into_lines
from extractors.common.evidence import create_evidence_record, save_evidence_csv


COURSE_CODE_PATTERN = re.compile(
    r"\b([A-Z]{2,5})\s*-?\s*(\d{3})\b",
    re.IGNORECASE
)

SEMESTER_PATTERN = re.compile(
    r"\b(?:semester|sem)\s*[-:]?\s*"
    r"(I{1,3}|IV|V|VI|VII|VIII|IX|X|1[0-2]|[1-9])\b",
    re.IGNORECASE
)

PLAN_COLUMNS = [
    "semester",
    "course_code",
    "slot",
    "source_url",
    "retrieved_on",
    "source_type",
]

REVIEW_COLUMNS = [
    "course_code",
    "semester",
    "source_page",
    "source_text",
    "review_reason",
]


def normalize_course_code(match: re.Match) -> str:
    """Convert a course-code match into a standardized code."""

    return (
        match.group(1).upper()
        + match.group(2)
    )


def extract_semester(text: str) -> str:
    """Extract an explicitly stated semester from text."""

    match = SEMESTER_PATTERN.search(text)

    if not match:
        return ""

    return match.group(1).upper()


def extract_program_plan(
    pdf_path: Path,
    output_dir: Path,
    source_url: str = "",
) -> None:

    pages = read_pdf_pages(pdf_path)

    plan_records = []
    review_records = []
    evidence_records = []

    seen = set()

    current_semester = ""

    for page in pages:

        page_number = page["page_number"]

        cleaned_text = clean_pdf_text(page["text"])

        lines = split_into_lines(cleaned_text)

        for line in lines:

            # Update semester context when a heading is found.
            semester_in_line = extract_semester(line)

            if semester_in_line:
                current_semester = semester_in_line

            matches = list(COURSE_CODE_PATTERN.finditer(line))

            if not matches:
                continue

            for match in matches:

                course_code = normalize_course_code(match)

                key = (
                    current_semester,
                    course_code
                )

                if key in seen:
                    continue

                seen.add(key)

                record = {
                    "semester": current_semester,
                    "course_code": course_code,
                    "slot": "",
                    "source_url": source_url,
                    "retrieved_on": date.today().isoformat(),
                    "source_type": "official_pdf",
                }

                plan_records.append(record)

                reason = ""

                if not current_semester:
                    reason = "Course found, but semester heading was not identified."

                elif len(matches) > 1:
                    reason = "Multiple course codes found on one line; verify table structure."

                if reason:

                    review_records.append({
                        "course_code": course_code,
                        "semester": current_semester,
                        "source_page": page_number,
                        "source_text": line,
                        "review_reason": reason,
                    })

                evidence_records.append(
                    create_evidence_record(
                        record_id=course_code,
                        record_type="program_plan",
                        extracted_information=(
                            f"Course {course_code}; "
                            f"semester {current_semester or 'not identified'}"
                        ),
                        pdf_page=page_number,
                        quotation=line,
                        source_heading=(
                            f"Semester {current_semester}"
                            if current_semester else ""
                        ),
                        source_url=source_url,
                    )
                )

    output_dir.mkdir(parents=True, exist_ok=True)

    save_csv(
        plan_records,
        output_dir / "program_plan.csv",
        PLAN_COLUMNS,
    )

    save_csv(
        review_records,
        output_dir / "program_plan_review.csv",
        REVIEW_COLUMNS,
    )

    save_evidence_csv(
        evidence_records,
        output_dir / "program_plan_evidence.csv",
    )

    print(f"PDF: {pdf_path}")
    print(f"Course records found: {len(plan_records)}")
    print(f"Records requiring review: {len(review_records)}")
    print(f"Output directory: {output_dir}")


def save_csv(records, output_path, columns):

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=columns
        )

        writer.writeheader()
        writer.writerows(records)


def main():

    parser = argparse.ArgumentParser(
        description="Extract programme-plan candidates from an official PDF."
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to the original programme-structure PDF."
    )

    parser.add_argument(
        "--out-dir",
        default="data/extracted",
        help="Output directory."
    )

    parser.add_argument(
        "--source-url",
        default="",
        help="Official source URL, if available."
    )

    args = parser.parse_args()

    extract_program_plan(
        pdf_path=Path(args.pdf),
        output_dir=Path(args.out_dir),
        source_url=args.source_url,
    )


if __name__ == "__main__":
    main()