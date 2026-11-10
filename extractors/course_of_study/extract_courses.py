from __future__ import annotations

import argparse
import csv
import re

from collections import defaultdict
from datetime import date
from pathlib import Path

import pdfplumber


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PDF = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Course_of_Study.pdf"
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "extracted"
)

RETRIEVED_ON = date.today().isoformat()

SOURCE_TYPE = "official_pdf"

TARGET_DEPARTMENT = "DSAI"

DEPARTMENT_PREFIXES = {
    "D": "DSAI",
    "C": "CSE",
    "M": "Mechanical Engineering",
    "E": "Electrical Engineering",
}


# ============================================================
# OUTPUT SCHEMAS
# ============================================================

COURSE_COLUMNS = [
    "code",
    "title",
    "dept",
    "credits",
    "lecture",
    "tutorial",
    "practical",
    "semesters",
    "course_type",
    "mode",
    "objectives",
    "syllabus",
    "prereq_text",
    "source_url",
    "retrieved_on",
    "source_type",
]

PREREQUISITE_COLUMNS = [
    "course",
    "requires",
    "kind",
    "group",
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
    "course_code",
    "pdf_page",
    "missing_fields",
    "review_status",
]


# ============================================================
# REGULAR EXPRESSIONS
# ============================================================

COURSE_HEADER_PATTERN = re.compile(
    r"^\s*([A-Z]{2,5}\s*-?\s*\d{3})\s+(.+?)\s*$",
    re.IGNORECASE,
)

COURSE_CODE_PATTERN = re.compile(
    r"\b[A-Z]{2,5}\s*-?\s*\d{3}\b",
    re.IGNORECASE,
)

CREDIT_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s+Credits?\s*"
    r"\(\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*\)",
    re.IGNORECASE,
)

PREREQUISITE_LABEL = re.compile(
    r"^\s*pre[\s-]*requisites?\s*"
    r"(?:\([^)]*\))?\s*[:\-]?\s*(.*)$",
    re.IGNORECASE,
)

OBJECTIVE_LABEL = re.compile(
    r"^\s*(?:course\s+)?objectives?\s*[:\-]?\s*(.*)$",
    re.IGNORECASE,
)

SYLLABUS_LABEL = re.compile(
    r"^\s*(?:detailed\s+)?(?:course\s+)?"
    r"(?:syllabus|contents?|outline)\s*[:\-]?\s*(.*)$",
    re.IGNORECASE,
)

OVERLAP_LABEL = re.compile(
    r"^\s*overlap\s+with\b\s*[:\-]?\s*(.*)$",
    re.IGNORECASE,
)

CREDIT_LABEL = re.compile(
    r"^\s*\d+(?:\.\d+)?\s+Credits?\b",
    re.IGNORECASE,
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value: str | None) -> str:
    """Normalize whitespace in extracted text."""

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def correct_source_ocr(code: str, value: str) -> str:
    """Correct a verified OCR artifact in the DSP301 source text."""

    if code != "DSP301":
        return value

    return re.sub(
        r"\bAl\b",
        "AI",
        value,
    )


def normalize_course_code(code: str) -> str:
    """Normalize a course code."""

    return re.sub(
        r"[\s-]+",
        "",
        code,
    ).upper()


def department_from_code(code: str) -> str:
    """Determine the department using the course-code prefix."""

    if not code:
        return ""

    prefix = code[0].upper()

    return DEPARTMENT_PREFIXES.get(
        prefix,
        "",
    )


def is_course_header(line: str) -> bool:
    """
    Check whether a line represents a new course.

    Avoid treating prerequisite text such as
    'DSL201 or equivalent' as a course header.
    """

    match = COURSE_HEADER_PATTERN.match(line)

    if not match:
        return False

    title = clean_text(match.group(2))

    if not title:
        return False

    if re.match(
        r"^(?:or|and)?\s*equivalent\b",
        title,
        re.IGNORECASE,
    ):
        return False

    if title.casefold() in {
        "or",
        "and",
        "equivalent",
    }:
        return False

    return True


def should_include_department(
    course_code: str,
    target_department: str,
) -> bool:
    """Check whether a course belongs to the requested department."""

    if target_department.upper() == "ALL":
        return True

    department = department_from_code(course_code)

    return department.casefold() == target_department.casefold()


# ============================================================
# PDF READING
# ============================================================

def read_pdf_pages(pdf_path: Path):
    """
    Read PDF text page by page.

    Each line retains its original PDF page number.
    """

    pages = []

    with pdfplumber.open(pdf_path) as pdf:

        print(f"Total PDF pages: {len(pdf.pages)}")

        for page_number, page in enumerate(
            pdf.pages,
            start=1,
        ):

            text = page.extract_text()

            if not text:
                continue

            lines = text.splitlines()

            for line in lines:

                cleaned = line.strip()

                if cleaned:
                    pages.append({
                        "page": page_number,
                        "text": cleaned,
                    })

    return pages


# ============================================================
# COURSE BLOCK EXTRACTION
# ============================================================

def split_course_blocks(pages):
    """
    Split the PDF into individual course blocks.

    A new course header closes the previous course block.

    Blocks can continue across PDF pages.
    """

    blocks = []

    current_block = None

    for item in pages:

        line = item["text"]
        page_number = item["page"]

        if is_course_header(line):

            # Save the previous course.
            if current_block is not None:
                blocks.append(current_block)

            match = COURSE_HEADER_PATTERN.match(line)

            code = normalize_course_code(
                match.group(1)
            )

            title = correct_source_ocr(
                code,
                clean_text(match.group(2)),
            )

            current_block = {
                "code": code,
                "title": title,
                "page": page_number,
                "lines": [],
            }

            continue

        if current_block is not None:

            current_block["lines"].append({
                "page": page_number,
                "text": line,
            })

    # Save the final course.
    if current_block is not None:
        blocks.append(current_block)

    return blocks


# ============================================================
# CREDIT EXTRACTION
# ============================================================

def extract_credits(block):
    """Extract credits and lecture/tutorial/practical values."""

    for item in block["lines"]:

        line = item["text"]

        match = CREDIT_PATTERN.search(line)

        if not match:
            continue

        credits = match.group(1)
        lecture = match.group(2)
        tutorial = match.group(3)
        practical = match.group(4)

        return {
            "credits": credits,
            "lecture": lecture,
            "tutorial": tutorial,
            "practical": practical,
        }

    return {
        "credits": "",
        "lecture": "",
        "tutorial": "",
        "practical": "",
    }


# ============================================================
# METADATA EXTRACTION
# ============================================================

def extract_prerequisite_text(block):
    """
    Extract prerequisite information.

    Example:
        Prerequisite(s): DSL201

    Returns:
        DSL201
    """

    for item in block["lines"]:

        line = item["text"]

        match = PREREQUISITE_LABEL.match(line)

        if match:

            return clean_text(
                match.group(1)
            )

    return ""


def extract_overlap_text(block):
    """Extract overlap information for evidence."""

    for item in block["lines"]:

        line = item["text"]

        match = OVERLAP_LABEL.match(line)

        if match:

            return clean_text(
                match.group(1)
            )

    return ""


# ============================================================
# OBJECTIVE EXTRACTION
# ============================================================

def extract_objectives(block):
    """
    Extract objectives when an explicit objectives heading exists.

    If the PDF has no objectives heading, return an empty string.
    """

    lines = block["lines"]

    objective_parts = []

    collecting = False

    for item in lines:

        line = item["text"]

        objective_match = OBJECTIVE_LABEL.match(line)

        if objective_match:

            collecting = True

            initial_text = clean_text(
                objective_match.group(1)
            )

            if initial_text:
                objective_parts.append(initial_text)

            continue

        if collecting:

            if (
                SYLLABUS_LABEL.match(line)
                or OVERLAP_LABEL.match(line)
                or PREREQUISITE_LABEL.match(line)
                or CREDIT_LABEL.match(line)
            ):
                break

            objective_parts.append(line)

    return clean_text(
        " ".join(objective_parts)
    )


# ============================================================
# SYLLABUS EXTRACTION
# ============================================================

def extract_syllabus(block):
    """
    Extract the descriptive course content.

    Typical Course of Study format:

        LAL246 Positive Psychology
        1 Credits (1-0-0)
        Prerequisite(s): None
        Overlap with: NA
        Introduction and brief overview: ...
        History of well-being research...
        ...
        LAL247 Applied Positive Psychology

    The course block has already been separated from
    the next course by split_course_blocks().

    Therefore, descriptive content is collected after
    the metadata lines.
    """

    lines = block["lines"]

    metadata_indices = []

    explicit_syllabus_index = None

    for index, item in enumerate(lines):

        line = item["text"]

        if CREDIT_LABEL.match(line):
            metadata_indices.append(index)

        elif PREREQUISITE_LABEL.match(line):
            metadata_indices.append(index)

        elif OVERLAP_LABEL.match(line):
            metadata_indices.append(index)

        syllabus_match = SYLLABUS_LABEL.match(line)

        if syllabus_match:
            explicit_syllabus_index = index

    # If an explicit syllabus heading exists,
    # extract content after that heading.
    if explicit_syllabus_index is not None:

        syllabus_parts = []

        heading_line = lines[
            explicit_syllabus_index
        ]["text"]

        heading_match = SYLLABUS_LABEL.match(
            heading_line
        )

        initial_text = clean_text(
            heading_match.group(1)
        )

        if initial_text:
            syllabus_parts.append(initial_text)

        for item in lines[explicit_syllabus_index + 1:]:

            line = item["text"]

            if (
                CREDIT_LABEL.match(line)
                or PREREQUISITE_LABEL.match(line)
                or OVERLAP_LABEL.match(line)
            ):
                continue

            syllabus_parts.append(line)

        return clean_text(
            " ".join(syllabus_parts)
        )

    # Otherwise, use the descriptive content after metadata.
    if not metadata_indices:
        return ""

    content_start = max(metadata_indices) + 1

    syllabus_parts = []

    for item in lines[content_start:]:

        line = item["text"]

        # Do not include metadata if it appears again.
        if CREDIT_LABEL.match(line):
            continue

        if PREREQUISITE_LABEL.match(line):
            continue

        if OVERLAP_LABEL.match(line):
            continue

        if OBJECTIVE_LABEL.match(line):
            continue

        syllabus_parts.append(line)

    return clean_text(
        " ".join(syllabus_parts)
    )


# ============================================================
# PREREQUISITE RELATIONSHIP EXTRACTION
# ============================================================

def extract_prerequisite_records(
    course_code,
    prerequisite_text,
    source_url,
):
    """
    Convert prerequisite course codes into relationships.

    Example:
        DSL201

    produces:
        DSL251 -> DSL201

    Example:
        Either CSL304 or DSL501

    produces two alternatives with group OR.
    """

    records = []

    if not prerequisite_text:
        return records

    normalized_text = prerequisite_text.strip()

    if normalized_text.casefold() in {
        "none",
        "na",
        "n/a",
        "-",
        "nil",
    }:
        return records

    codes = [
        normalize_course_code(code)
        for code in COURSE_CODE_PATTERN.findall(
            normalized_text
        )
    ]

    codes = list(dict.fromkeys(codes))

    if not codes:
        return records

    if re.search(
        r"\bor\b|\beither\b",
        normalized_text,
        re.IGNORECASE,
    ):
        group_type = "OR"
    else:
        group_type = "AND"

    for required_code in codes:

        records.append({

            "course": course_code,

            "requires": required_code,

            "kind": "required",

            "group": group_type,

            "source_url": source_url,

            "retrieved_on": RETRIEVED_ON,

            "source_type": SOURCE_TYPE,
        })

    return records


# ============================================================
# EVIDENCE EXTRACTION
# ============================================================

def create_evidence_record(
    course_code,
    record_type,
    extracted_information,
    page_number,
    section,
    quotation,
    source_url,
):
    """Create one source-evidence record."""

    return {

        "record_id": f"{course_code}_{record_type}",

        "record_type": record_type,

        "extracted_information": extracted_information,

        "pdf_page": page_number,

        "source_heading_or_section": section,

        "exact_supporting_quotation": quotation,

        "source_url": source_url,

        "retrieved_on": RETRIEVED_ON,

        "source_type": SOURCE_TYPE,
    }


def extract_evidence(block, course_record, source_url):
    """Create evidence for extracted course fields."""

    evidence_records = []

    code = block["code"]
    page = block["page"]

    evidence_records.append(
        create_evidence_record(
            code,
            "course",
            course_record["title"],
            page,
            "Course header",
            f"{code} {course_record['title']}",
            source_url,
        )
    )

    if course_record["syllabus"]:

        evidence_records.append(
            create_evidence_record(
                code,
                "syllabus",
                course_record["syllabus"],
                page,
                "Course description",
                course_record["syllabus"],
                source_url,
            )
        )

    if course_record["prereq_text"]:

        evidence_records.append(
            create_evidence_record(
                code,
                "prerequisite",
                course_record["prereq_text"],
                page,
                "Prerequisite(s)",
                course_record["prereq_text"],
                source_url,
            )
        )

    overlap = extract_overlap_text(block)

    if overlap:

        evidence_records.append(
            create_evidence_record(
                code,
                "overlap",
                overlap,
                page,
                "Overlap with",
                overlap,
                source_url,
            )
        )

    if course_record["objectives"]:

        evidence_records.append(
            create_evidence_record(
                code,
                "objectives",
                course_record["objectives"],
                page,
                "Course objectives",
                course_record["objectives"],
                source_url,
            )
        )

    return evidence_records


# ============================================================
# COURSE EXTRACTION
# ============================================================

def extract_course_record(
    block,
    source_url,
):
    """Extract all structured fields from one course block."""

    code = block["code"]

    title = correct_source_ocr(
        code,
        block["title"],
    )

    credits = extract_credits(block)

    prerequisite_text = extract_prerequisite_text(
        block
    )

    objectives = extract_objectives(
        block
    )

    syllabus = correct_source_ocr(
        code,
        extract_syllabus(block),
    )

    department = department_from_code(
        code
    )

    record = {

        "code": code,

        "title": title,

        "dept": department,

        "credits": credits["credits"],

        "lecture": credits["lecture"],

        "tutorial": credits["tutorial"],

        "practical": credits["practical"],

        "semesters": "",

        "course_type": "",

        "mode": "",

        "objectives": objectives,

        "syllabus": syllabus,

        "prereq_text": prerequisite_text,

        "source_url": source_url,

        "retrieved_on": RETRIEVED_ON,

        "source_type": SOURCE_TYPE,
    }

    return record


# ============================================================
# MAIN EXTRACTION PIPELINE
# ============================================================

def extract_courses(
    pdf_path,
    output_dir,
    department,
    source_url,
):
    """Run course extraction from the official PDF."""

    print("\n======================================")
    print("COURSE OF STUDY EXTRACTION")
    print("======================================")

    print(f"Source PDF: {pdf_path}")
    print(f"Target department: {department}")
    print(f"Output directory: {output_dir}")

    # --------------------------------------------------------
    # Step 1: Read PDF pages.
    # --------------------------------------------------------

    pages = read_pdf_pages(pdf_path)

    # --------------------------------------------------------
    # Step 2: Split PDF into course blocks.
    # --------------------------------------------------------

    blocks = split_course_blocks(pages)

    print(f"\nCourse blocks detected: {len(blocks)}")

    # --------------------------------------------------------
    # Step 3: Extract structured course information.
    # --------------------------------------------------------

    course_records = []

    prerequisite_records = []

    evidence_records = []

    review_records = []

    for block in blocks:

        code = block["code"]

        # Apply department filtering.
        if not should_include_department(
            code,
            department,
        ):
            continue

        course_record = extract_course_record(
            block,
            source_url,
        )

        course_records.append(
            course_record
        )

        # Prerequisite relationships.
        prerequisite_records.extend(
            extract_prerequisite_records(
                code,
                course_record["prereq_text"],
                source_url,
            )
        )

        # Source evidence.
        evidence_records.extend(
            extract_evidence(
                block,
                course_record,
                source_url,
            )
        )

        # ----------------------------------------------------
        # Completeness checks.
        # ----------------------------------------------------

        missing_fields = []

        if not course_record["title"]:
            missing_fields.append("title")

        if not course_record["credits"]:
            missing_fields.append("credits")

        if not course_record["syllabus"]:
            missing_fields.append("syllabus")

        if missing_fields:

            review_records.append({

                "course_code": code,

                "pdf_page": block["page"],

                "missing_fields": "; ".join(
                    missing_fields
                ),

                "review_status": "needs_review",
            })

    return (
        course_records,
        prerequisite_records,
        evidence_records,
        review_records,
    )


# ============================================================
# CSV EXPORT
# ============================================================

def save_csv(
    records,
    output_path,
    columns,
):
    """Save extracted records to CSV."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )

        writer.writeheader()

        writer.writerows(records)

    print(
        f"Generated: {output_path} "
        f"({len(records)} records)"
    )


# ============================================================
# COMMAND LINE INTERFACE
# ============================================================

def main():

    global TARGET_DEPARTMENT

    parser = argparse.ArgumentParser(
        description=(
            "Extract courses, prerequisites, syllabus "
            "and source evidence from the official "
            "Course of Study PDF."
        )
    )

    parser.add_argument(
        "--pdf",
        default=str(DEFAULT_PDF),
        help="Path to the Course of Study PDF.",
    )

    parser.add_argument(
        "--department",
        default=TARGET_DEPARTMENT,
        help="Target department, for example DSAI or ALL.",
    )

    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for extracted CSV files.",
    )

    parser.add_argument(
        "--source-url",
        default="",
        help="Source URL or source filename.",
    )

    args = parser.parse_args()

    TARGET_DEPARTMENT = args.department

    pdf_path = Path(args.pdf)

    output_dir = Path(args.output_dir)

    if not pdf_path.is_absolute():
        pdf_path = PROJECT_ROOT / pdf_path

    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    if not pdf_path.exists():

        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    if not args.source_url:
        source_url = pdf_path.name
    else:
        source_url = args.source_url

    (
        courses,
        prerequisites,
        evidence,
        reviews,
    ) = extract_courses(
        pdf_path=pdf_path,
        output_dir=output_dir,
        department=TARGET_DEPARTMENT,
        source_url=source_url,
    )

    # --------------------------------------------------------
    # Export CSV files.
    # --------------------------------------------------------

    save_csv(
        courses,
        output_dir / "courses.csv",
        COURSE_COLUMNS,
    )

    save_csv(
        prerequisites,
        output_dir / "prerequisites.csv",
        PREREQUISITE_COLUMNS,
    )

    save_csv(
        evidence,
        output_dir / "source_evidence.csv",
        EVIDENCE_COLUMNS,
    )

    save_csv(
        reviews,
        output_dir / "extraction_review.csv",
        REVIEW_COLUMNS,
    )

    # --------------------------------------------------------
    # Summary.
    # --------------------------------------------------------

    print("\n======================================")
    print("EXTRACTION SUMMARY")
    print("======================================")

    print(f"Courses extracted: {len(courses)}")

    print(
        f"Prerequisite relationships: "
        f"{len(prerequisites)}"
    )

    print(
        f"Source evidence records: "
        f"{len(evidence)}"
    )

    print(
        f"Records needing review: "
        f"{len(reviews)}"
    )

    syllabus_count = sum(
        bool(row["syllabus"])
        for row in courses
    )

    print(
        f"Courses with syllabus: "
        f"{syllabus_count}/{len(courses)}"
    )

    print("\nExtraction completed successfully.")


if __name__ == "__main__":
    main()