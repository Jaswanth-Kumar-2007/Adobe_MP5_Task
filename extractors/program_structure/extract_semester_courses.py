import argparse
import csv
import re

from pathlib import Path
from datetime import date

import pdfplumber


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SEMESTERS = {
    "I", "II", "III", "IV",
    "V", "VI", "VII", "VIII"
}

COURSE_CODE_PATTERN = re.compile(
    r"\b([A-Z]{2,5})\s*-?\s*(\d{3})\b",
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
    "semester",
    "slot",
    "source_page",
    "source_text",
    "review_reason",
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


def clean_cell(value):
    """Normalize text extracted from a PDF table."""

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def normalize_semester(value):
    """Return a valid Roman-numeral semester."""

    value = clean_cell(value).upper()

    value = value.replace("SEMESTER", "")
    value = value.replace("SEM", "")
    value = value.strip(" :-")

    if value in SEMESTERS:
        return value

    return ""


def extract_course_codes(text):
    """
    Extract and normalize all course codes from one table cell.

    Example:
    CYP102 / PHP102 -> ['CYP102', 'PHP102']
    """

    matches = COURSE_CODE_PATTERN.findall(
        clean_cell(text).upper()
    )

    return list(dict.fromkeys(
        prefix.upper() + number
        for prefix, number in matches
    ))


def classify_requirement(text):
    """
    Identify programme requirements without fixed course codes.
    """

    normalized = clean_cell(text).casefold()

    if normalized in {"pe", "professional elective"}:
        return "PE"

    if normalized in {"oe", "open elective"}:
        return "OE"

    if normalized in {"la courses", "la course"}:
        return "LA Courses"

    return ""


def save_csv(records, output_path, columns):

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
            fieldnames=columns,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(records)


def extract_semester_courses(
    pdf_path,
    output_dir,
    source_name
):

    plan_records = []
    review_records = []
    evidence_records = []

    seen = set()

    retrieved_on = date.today().isoformat()

    current_semester = ""

    with pdfplumber.open(pdf_path) as pdf:

        for page_number, page in enumerate(
            pdf.pages,
            start=1
        ):

            page_text = page.extract_text() or ""

            # Ignore pages that do not contain the
            # relevant DSAI programme table.
            if (
                "Data Science and Artificial Intelligence"
                not in page_text
            ):
                continue

            print(
                f"Checking programme table on page {page_number}"
            )

            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 4,
                    "join_tolerance": 4,
                    "intersection_tolerance": 5,
                }
            )

            if not tables:
                review_records.append({
                    "semester": "",
                    "slot": "",
                    "source_page": page_number,
                    "source_text": page_text[:500],
                    "review_reason": (
                        "DSAI heading found, but no table "
                        "was detected. Check PDF table extraction."
                    ),
                })

                continue

            for table in tables:

                if not table:
                    continue

                # Expected structure:
                # Semester | Course-1 ... Course-7 | Credits
                #
                # Therefore, we expect approximately 9 columns.
                if len(table[0]) < 9:
                    continue

                for row in table:

                    if not row or len(row) < 9:
                        continue

                    cells = [
                        clean_cell(cell)
                        for cell in row
                    ]

                    # First column contains semester labels.
                    detected_semester = normalize_semester(
                        cells[0]
                    )

                    if detected_semester:
                        current_semester = detected_semester

                    # Skip table headers.
                    if cells[0].casefold() == "semester":
                        continue

                    if not current_semester:
                        continue

                    # Columns 1 through 7 are Course-1 ... Course-7.
                    for column_index in range(1, 8):

                        cell_text = cells[column_index]

                        if not cell_text:
                            continue

                        slot = f"Course-{column_index}"

                        codes = extract_course_codes(
                            cell_text
                        )

                        # ----------------------------------
                        # Fixed course entries
                        # ----------------------------------

                        if codes:

                            for code in codes:

                                key = (
                                    current_semester,
                                    slot,
                                    code
                                )

                                if key in seen:
                                    continue

                                seen.add(key)

                                plan_records.append({
                                    "semester": current_semester,
                                    "course_code": code,
                                    "slot": slot,
                                    "source_url": source_name,
                                    "retrieved_on": retrieved_on,
                                    "source_type": "official_pdf",
                                })

                                evidence_records.append({

                                    "record_id": (
                                        f"{current_semester}_"
                                        f"{slot}_{code}"
                                    ),

                                    "record_type": "program_plan",

                                    "extracted_information": (
                                        f"{code} is listed in "
                                        f"Semester {current_semester}, "
                                        f"{slot}."
                                    ),

                                    "pdf_page": page_number,

                                    "source_heading_or_section": (
                                        "BTech in Data Science "
                                        "and Artificial Intelligence"
                                    ),

                                    "exact_supporting_quotation": (
                                        cell_text
                                    ),

                                    "source_url": source_name,

                                    "retrieved_on": retrieved_on,

                                    "source_type": "official_pdf",
                                })

                            # Multiple codes in one cell
                            # represent alternatives.
                            if len(codes) > 1:

                                review_records.append({
                                    "semester": current_semester,
                                    "slot": slot,
                                    "source_page": page_number,
                                    "source_text": cell_text,
                                    "review_reason": (
                                        "Multiple course codes "
                                        "appear in one slot. "
                                        "Verify alternative-course "
                                        "interpretation."
                                    ),
                                })

                            continue

                        # ----------------------------------
                        # Elective and LA requirements
                        # ----------------------------------

                        requirement = classify_requirement(
                            cell_text
                        )

                        if requirement:

                            key = (
                                current_semester,
                                slot,
                                requirement
                            )

                            if key in seen:
                                continue

                            seen.add(key)

                            plan_records.append({
                                "semester": current_semester,
                                "course_code": "",
                                "slot": (
                                    f"{slot}: {requirement}"
                                ),
                                "source_url": source_name,
                                "retrieved_on": retrieved_on,
                                "source_type": "official_pdf",
                            })

                            evidence_records.append({

                                "record_id": (
                                    f"{current_semester}_"
                                    f"{slot}_{requirement.replace(' ', '_')}"
                                ),

                                "record_type": "program_plan",

                                "extracted_information": (
                                    f"{requirement} requirement "
                                    f"in Semester {current_semester}, "
                                    f"{slot}."
                                ),

                                "pdf_page": page_number,

                                "source_heading_or_section": (
                                    "BTech in Data Science "
                                    "and Artificial Intelligence"
                                ),

                                "exact_supporting_quotation": (
                                    cell_text
                                ),

                                "source_url": source_name,

                                "retrieved_on": retrieved_on,

                                "source_type": "official_pdf",
                            })

    # --------------------------------------------------
    # Export
    # --------------------------------------------------

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    save_csv(
        plan_records,
        output_dir / "program_plan.csv",
        PLAN_COLUMNS
    )

    save_csv(
        review_records,
        output_dir / "program_plan_review.csv",
        REVIEW_COLUMNS
    )

    save_csv(
        evidence_records,
        output_dir / "program_plan_evidence.csv",
        EVIDENCE_COLUMNS
    )

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    print("\n========== SEMESTER EXTRACTION ==========")

    print(f"PDF: {pdf_path}")

    print(f"Course/requirement records: {len(plan_records)}")

    print(f"Review records: {len(review_records)}")

    print("\nSemester-wise course counts:")

    for semester in [
        "I", "II", "III", "IV",
        "V", "VI", "VII", "VIII"
    ]:

        count = sum(
            row["semester"] == semester
            and bool(row["course_code"])
            for row in plan_records
        )

        print(f"Semester {semester}: {count}")

    print("\nGenerated:")
    print(output_dir / "program_plan.csv")
    print(output_dir / "program_plan_review.csv")
    print(output_dir / "program_plan_evidence.csv")


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Extract semester-wise DSAI course mappings "
            "from the official Course of Study PDF."
        )
    )

    parser.add_argument(
        "--pdf",
        default="data/raw/Course_of_Study.pdf"
    )

    parser.add_argument(
        "--out-dir",
        default="data/extracted"
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    output_dir = Path(args.out_dir)

    if not pdf_path.is_absolute():
        pdf_path = PROJECT_ROOT / pdf_path

    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    extract_semester_courses(
        pdf_path=pdf_path,
        output_dir=output_dir,
        source_name=pdf_path.name
    )


if __name__ == "__main__":
    main()