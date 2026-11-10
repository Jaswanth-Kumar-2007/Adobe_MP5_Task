import argparse
import csv
import re

from pathlib import Path
from datetime import date

import pdfplumber


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PDF = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "List_of_courses_V4.pdf"
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "extracted"
)

RETRIEVED_ON = date.today().isoformat()

SOURCE_TYPE = "official_pdf"

TARGET_PROGRAMME = "DSAI"


# ============================================================
# OUTPUT SCHEMAS
# ============================================================

CATALOGUE_COLUMNS = [
    "course_code",
    "course_title",
    "credits",
    "discipline",
    "programme",
    "remarks",
    "source_page",
    "source_url",
    "retrieved_on",
    "source_type",
]

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
    "source_page",
    "course_code",
    "course_title",
    "raw_row",
    "review_reason",
]


# ============================================================
# REGULAR EXPRESSIONS
# ============================================================

COURSE_CODE_PATTERN = re.compile(
    r"\b[A-Z]{2,5}\s*-?\s*\d{3}\b",
    re.IGNORECASE
)

CREDIT_PATTERN = re.compile(
    r"^\d+(?:\.\d+)?$"
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value):
    """Normalize whitespace in extracted PDF text."""

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def normalize_course_code(code):
    """Normalize a course code."""

    return re.sub(
        r"[\s-]+",
        "",
        code
    ).upper()


def extract_course_codes(text):
    """
    Extract course codes from a catalogue cell.

    Multiple codes are preserved as separate identifiers.
    """

    matches = COURSE_CODE_PATTERN.findall(
        clean_text(text).upper()
    )

    return list(dict.fromkeys(
        normalize_course_code(code)
        for code in matches
    ))


def normalize_header(value):
    """Normalize a table header for column identification."""

    value = clean_text(value).casefold()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# HEADER DETECTION
# ============================================================

HEADER_ALIASES = {

    "course_code": {
        "course code",
        "course",
        "code",
        "subject code",
        "course id",
    },

    "course_title": {
        "course name",
        "course title",
        "title",
        "subject name",
        "name of course",
    },

    "credits": {
        "credits",
        "credit",
        "total credits",
    },

    "discipline": {
        "discipline",
        "department",
        "dept",
        "school",
    },

    "programme": {
        "programme",
        "program",
        "programme name",
        "program name",
    },

    "remarks": {
        "remarks",
        "remark",
        "comments",
        "eligibility",
        "remarks eligibility",
    },
}


def identify_columns(row):
    """
    Identify column positions using the table header.

    Returns None if the row does not look like a header.
    """

    positions = {}

    for index, cell in enumerate(row):

        header = normalize_header(cell)

        for field, aliases in HEADER_ALIASES.items():

            if header in aliases:
                positions[field] = index

    if (
        "course_code" in positions
        and "course_title" in positions
    ):
        return positions

    return None


# ============================================================
# TABLE ROW EXTRACTION
# ============================================================

def get_cell(row, positions, field):
    """Safely retrieve a table cell."""

    index = positions.get(field)

    if index is None or index >= len(row):
        return ""

    return clean_text(row[index])


def is_repeated_header(row):
    """Detect repeated table headers."""

    combined = " ".join(
        normalize_header(cell)
        for cell in row
    )

    return (
        "course code" in combined
        or "course name" in combined
        or "subject code" in combined
    )


def extract_table_records(pdf_path):

    catalogue_records = []
    review_records = []

    with pdfplumber.open(pdf_path) as pdf:

        print(f"Total PDF pages: {len(pdf.pages)}")

        for page_number, page in enumerate(
            pdf.pages,
            start=1
        ):

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
                continue

            print(
                f"Page {page_number}: "
                f"{len(tables)} table(s) detected"
            )

            for table in tables:

                if not table:
                    continue

                positions = None

                for row in table:

                    if not row:
                        continue

                    row = [
                        clean_text(cell)
                        for cell in row
                    ]

                    # Find the header.
                    detected_positions = identify_columns(row)

                    if detected_positions:
                        positions = detected_positions
                        continue

                    if positions is None:
                        continue

                    if is_repeated_header(row):
                        continue

                    raw_row = " | ".join(row)

                    code_text = get_cell(
                        row,
                        positions,
                        "course_code"
                    )

                    title = get_cell(
                        row,
                        positions,
                        "course_title"
                    )

                    credits = get_cell(
                        row,
                        positions,
                        "credits"
                    )

                    discipline = get_cell(
                        row,
                        positions,
                        "discipline"
                    )

                    programme = get_cell(
                        row,
                        positions,
                        "programme"
                    )

                    remarks = get_cell(
                        row,
                        positions,
                        "remarks"
                    )

                    codes = extract_course_codes(
                        code_text
                    )

                    # Ignore empty or non-course rows.
                    if not codes:

                        if code_text or title:

                            review_records.append({

                                "source_page": page_number,

                                "course_code": code_text,

                                "course_title": title,

                                "raw_row": raw_row,

                                "review_reason": (
                                    "Course code could not "
                                    "be identified."
                                ),
                            })

                        continue

                    if not title:

                        review_records.append({

                            "source_page": page_number,

                            "course_code": code_text,

                            "course_title": "",

                            "raw_row": raw_row,

                            "review_reason": (
                                "Course title is empty."
                            ),
                        })

                        continue

                    if credits and not CREDIT_PATTERN.fullmatch(
                        credits
                    ):

                        review_records.append({

                            "source_page": page_number,

                            "course_code": code_text,

                            "course_title": title,

                            "raw_row": raw_row,

                            "review_reason": (
                                "Credit value needs manual review."
                            ),
                        })

                    # Create one record per course code.
                    for code in codes:

                        catalogue_records.append({

                            "course_code": code,

                            "course_title": title,

                            "credits": credits,

                            "discipline": discipline,

                            "programme": programme,

                            "remarks": remarks,

                            "source_page": page_number,

                            "source_url": pdf_path.name,

                            "retrieved_on": RETRIEVED_ON,

                            "source_type": SOURCE_TYPE,
                        })

    return catalogue_records, review_records


# ============================================================
# DISCIPLINE NORMALIZATION
# ============================================================

KNOWN_DISCIPLINES = {
    "ALL",
    "BSBM",
    "CS&DS&EE&ECE&M T&MA",
    "CSE",
    "CSE & DSAI",
    "CSE & DSAI & MT",
    "CSE & DSAI/MA",
    "CSE - DSAI",
    "CSE - DSAI/MT",
    "CSE/MA",
    "CSE/MT",
    "CY",
    "ECE",
    "ECE (OLD)",
    "ECE - CSP",
    "ECE - VLSI",
    "EE",
    "EE & MT",
    "EE - CI",
    "EE - CI & MT",
    "EE - EVT",
    "EE - PSPE",
    "LA",
    "MA",
    "ME",
    "ME & MT",
    "ME - DM",
    "ME - DM & TF",
    "ME - TF",
    "ME/MSME",
    "MSME",
    "MT",
    "PH",
}


def normalize_discipline(discipline):
    """Normalize discipline text without changing its meaning."""

    return re.sub(
        r"\s+",
        " ",
        clean_text(discipline).upper()
    ).strip()


def extract_discipline_tokens(discipline):
    """
    Split combined discipline values into individual identifiers.

    Examples:

        CSE & DSAI
        -> {"CSE", "DSAI"}

        CSE - DSAI/MA
        -> {"CSE", "DSAI", "MA"}

        CSE & DSAI & MT
        -> {"CSE", "DSAI", "MT"}

        CS&DS&EE&ECE&M T&MA
        -> {"CS", "DS", "EE", "ECE", "MT", "MA"}
    """

    normalized = normalize_discipline(discipline)

    parts = re.split(
        r"\s*[&/,]\s*|\s+-\s+",
        normalized
    )

    tokens = set()

    for part in parts:

        token = re.sub(
            r"[^A-Z0-9]",
            "",
            part
        )

        if token:
            tokens.add(token)

    return tokens


# ============================================================
# DSAI ELIGIBILITY EXTRACTION
# ============================================================

def determine_dsai_eligibility(discipline):
    """
    Determine whether DSAI students can take a course.

    Rules:

        ALL:
            Eligible for every branch.

        DSAI:
            Explicitly eligible.

        DS:
            Treated as Data Science, according to
            the supplied catalogue convention.

        Other known disciplines:
            Not eligible for DSAI.

        Missing or unknown discipline:
            Needs manual review.
    """

    normalized = normalize_discipline(discipline)

    if not normalized:
        return "needs_review"

    if normalized not in KNOWN_DISCIPLINES:
        return "needs_review"

    if normalized == "ALL":
        return "eligible"

    tokens = extract_discipline_tokens(normalized)

    if tokens.intersection({
        "DS",
        "DSAI",
    }):
        return "eligible"

    return "not_eligible"


# ============================================================
# ELIGIBILITY EXTRACTION
# ============================================================

def extract_eligibility(catalogue_records):

    eligibility_records = []
    review_records = []

    seen = set()

    for course in catalogue_records:

        code = course["course_code"]

        discipline = clean_text(
            course.get("discipline", "")
        )

        status = determine_dsai_eligibility(
            discipline
        )

        key = (
            code,
            TARGET_PROGRAMME,
            normalize_discipline(discipline),
        )

        if key in seen:
            continue

        seen.add(key)

        # Unknown or missing discipline requires review.
        if status == "needs_review":

            review_records.append({

                "source_page": course["source_page"],

                "course_code": code,

                "course_title": course["course_title"],

                "raw_row": discipline,

                "review_reason": (
                    "Missing or unrecognized discipline. "
                    "DSAI eligibility requires manual review."
                ),
            })

        eligibility_records.append({

            "course_code": code,

            "programme": TARGET_PROGRAMME,

            "eligibility_status": status,

            "conditions": (
                f"Official catalogue discipline: {discipline}"
                if discipline
                else "Discipline not specified; manual review required."
            ),

            "source_url": course["source_url"],

            "retrieved_on": RETRIEVED_ON,

            "source_type": SOURCE_TYPE,
        })

    return eligibility_records, review_records


# ============================================================
# CSV EXPORT
# ============================================================

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

    print(
        f"Generated: {output_path} "
        f"({len(records)} records)"
    )


# ============================================================
# MAIN EXTRACTION
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Extract the official course catalogue "
            "and DSAI branch eligibility."
        )
    )

    parser.add_argument(
        "--pdf",
        default=str(DEFAULT_PDF)
    )

    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUTPUT_DIR)
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

    print("\n======================================")
    print("COURSE CATALOGUE EXTRACTION")
    print("======================================")

    print(f"Source: {pdf_path}")

    print(f"Output: {output_dir}")

    # --------------------------------------------------------
    # Step 1: Extract catalogue.
    # --------------------------------------------------------

    catalogue, catalogue_review = extract_table_records(
        pdf_path
    )

    # Remove exact duplicate catalogue records.
    unique_catalogue = {}

    for record in catalogue:

        key = (
            record["course_code"],
            record["course_title"],
            record["source_page"]
        )

        unique_catalogue[key] = record

    catalogue = list(
        unique_catalogue.values()
    )

    # --------------------------------------------------------
    # Step 2: Extract DSAI eligibility from discipline.
    # --------------------------------------------------------

    eligibility, eligibility_review = extract_eligibility(
        catalogue
    )

    # --------------------------------------------------------
    # Step 3: Export.
    # --------------------------------------------------------

    save_csv(
        catalogue,
        output_dir / "course_catalogue.csv",
        CATALOGUE_COLUMNS
    )

    save_csv(
        eligibility,
        output_dir / "course_eligibility.csv",
        ELIGIBILITY_COLUMNS
    )

    save_csv(
        catalogue_review,
        output_dir / "course_catalogue_review.csv",
        REVIEW_COLUMNS
    )

    save_csv(
        eligibility_review,
        output_dir / "course_eligibility_review.csv",
        REVIEW_COLUMNS
    )

    # --------------------------------------------------------
    # Step 4: Summary.
    # --------------------------------------------------------

    print("\n======================================")
    print("EXTRACTION SUMMARY")
    print("======================================")

    print(
        f"Catalogue records: {len(catalogue)}"
    )

    print(
        f"DSAI eligibility records: {len(eligibility)}"
    )

    print(
        f"Catalogue review records: {len(catalogue_review)}"
    )

    print(
        f"Eligibility review records: {len(eligibility_review)}"
    )

    from collections import Counter

    status_counts = Counter(
        row["eligibility_status"]
        for row in eligibility
    )

    print("\nEligibility status counts:")

    for status, count in sorted(status_counts.items()):
        print(f"{status}: {count}")

    print("\nExtraction completed.")


if __name__ == "__main__":
    main()