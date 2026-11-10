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

ELIGIBILITY_KEYWORDS = re.compile(
    r"\b("
    r"eligible|eligibility|restricted|restriction|"
    r"only\s+for|not\s+for|open\s+elective|"
    r"programme\s+elective|program\s+elective|"
    r"departmental\s+elective|"
    r"prerequisite|pre-requisite|"
    r"students\s+of|"
    r"offered\s+to|"
    r"not\s+allowed"
    r")\b",
    re.IGNORECASE
)

ELIGIBILITY_COLUMNS = [
    "course_code",
    "programme",
    "eligibility_status",
    "conditions",
    "source_url",
    "retrieved_on",
    "source_type",
]

REVIEW_COLUMNS = [
    "course_code",
    "source_page",
    "source_text",
    "review_reason",
]


def normalize_course_code(match: re.Match) -> str:

    return (
        match.group(1).upper()
        + match.group(2)
    )


def extract_eligibility(
    pdf_path: Path,
    output_dir: Path,
    source_url: str = "",
) -> None:

    pages = read_pdf_pages(pdf_path)

    eligibility_records = []
    review_records = []
    evidence_records = []

    seen = set()

    for page in pages:

        page_number = page["page_number"]

        text = clean_pdf_text(page["text"])

        lines = split_into_lines(text)

        for line in lines:

            if not ELIGIBILITY_KEYWORDS.search(line):
                continue

            matches = list(COURSE_CODE_PATTERN.finditer(line))

            if not matches:
                continue

            for match in matches:

                course_code = normalize_course_code(match)

                key = (
                    course_code,
                    line
                )

                if key in seen:
                    continue

                seen.add(key)

                record = {
                    "course_code": course_code,
                    "programme": "",
                    "eligibility_status": "needs_review",
                    "conditions": line,
                    "source_url": source_url,
                    "retrieved_on": date.today().isoformat(),
                    "source_type": "official_pdf",
                }

                eligibility_records.append(record)

                review_records.append({
                    "course_code": course_code,
                    "source_page": page_number,
                    "source_text": line,
                    "review_reason": (
                        "Eligibility wording detected. "
                        "Confirm programme, status and conditions "
                        "against the original source."
                    ),
                })

                evidence_records.append(
                    create_evidence_record(
                        record_id=course_code,
                        record_type="course_eligibility",
                        extracted_information=line,
                        pdf_page=page_number,
                        quotation=line,
                        source_url=source_url,
                    )
                )

    output_dir.mkdir(parents=True, exist_ok=True)

    save_csv(
        eligibility_records,
        output_dir / "course_eligibility.csv",
        ELIGIBILITY_COLUMNS,
    )

    save_csv(
        review_records,
        output_dir / "course_eligibility_review.csv",
        REVIEW_COLUMNS,
    )

    save_evidence_csv(
        evidence_records,
        output_dir / "course_eligibility_evidence.csv",
    )

    print(f"PDF: {pdf_path}")
    print(f"Eligibility candidates found: {len(eligibility_records)}")
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
        description="Extract course-eligibility candidates from an official PDF."
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to the original eligibility or programme PDF."
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

    extract_eligibility(
        pdf_path=Path(args.pdf),
        output_dir=Path(args.out_dir),
        source_url=args.source_url,
    )


if __name__ == "__main__":
    main()