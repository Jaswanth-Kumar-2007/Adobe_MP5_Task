from __future__ import annotations

import csv
import re
import sys

from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher

import pdfplumber


# =========================================================
# PROJECT CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent

PDF_FILE = PROJECT_ROOT / "data" / "raw" / "Course_of_Study.pdf"

COURSES_CSV = PROJECT_ROOT / "data" / "extracted" / "courses.csv"

REPORT_DIR = PROJECT_ROOT / "reports"

REPORT_FILE = REPORT_DIR / "course_extraction_validation.csv"


# =========================================================
# VALIDATION CONFIGURATION
# =========================================================

COURSE_CODE_PATTERN = re.compile(
    r"\b[A-Z]{2,4}\s*\d{3}\b"
)

CREDIT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-–]\s*"
    r"(\d+(?:\.\d+)?)\s*[-–]\s*"
    r"(\d+(?:\.\d+)?)\s*[-–]\s*"
    r"(\d+(?:\.\d+)?)"
)

CONTEXT_SIZE = 500

TITLE_SIMILARITY_THRESHOLD = 0.80


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(value: str) -> str:
    """
    Normalize text for comparison.

    - Convert to lowercase.
    - Remove punctuation.
    - Normalize whitespace.
    """

    value = str(value or "").lower()

    value = re.sub(r"[^a-z0-9\s.]", " ", value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_course_code(value: str) -> str:
    """
    Normalize course codes.

    Example:
        DSL 251 -> DSL251
        dsl251  -> DSL251
    """

    return re.sub(r"\s+", "", str(value or "").upper()).strip()


def normalize_number(value: str) -> str:
    """
    Normalize numeric values.

    Example:
        3.0 -> 3
        3   -> 3
    """

    try:
        number = float(value)

        if number.is_integer():
            return str(int(number))

        return str(number)

    except (ValueError, TypeError):
        return str(value or "").strip()


# =========================================================
# LOAD COURSES CSV
# =========================================================

def load_courses() -> list[dict]:
    """
    Load normalized courses.csv.
    """

    if not COURSES_CSV.exists():
        raise FileNotFoundError(
            f"Courses CSV not found: {COURSES_CSV}"
        )

    with open(
        COURSES_CSV,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("courses.csv is empty or has no header.")

        required_columns = {
            "code",
            "title",
            "credits",
            "lecture",
            "tutorial",
            "practical",
        }

        missing_columns = required_columns - set(reader.fieldnames)

        if missing_columns:
            raise ValueError(
                f"Missing required CSV columns: {sorted(missing_columns)}"
            )

        courses = []

        for row in reader:

            row["code"] = normalize_course_code(row.get("code", ""))

            if not row["code"]:
                continue

            courses.append(row)

    return courses


# =========================================================
# EXTRACT TEXT FROM ORIGINAL PDF
# =========================================================

def extract_pdf_pages() -> list[dict]:
    """
    Read the original PDF independently using pdfplumber.

    No functions from the project's course extractor
    are imported or reused.
    """

    if not PDF_FILE.exists():
        raise FileNotFoundError(
            f"Source PDF not found: {PDF_FILE}"
        )

    pages = []

    with pdfplumber.open(PDF_FILE) as pdf:

        print(f"\nReading PDF: {PDF_FILE.name}")
        print(f"Total PDF pages: {len(pdf.pages)}")

        for page_number, page in enumerate(pdf.pages, start=1):

            text = page.extract_text() or ""

            pages.append({
                "page": page_number,
                "text": text,
                "normalized": normalize_text(text),
            })

    return pages


# =========================================================
# FIND COURSE IN ORIGINAL PDF
# =========================================================

def find_course_in_pdf(
    course_code: str,
    pages: list[dict]
) -> list[dict]:
    """
    Find every occurrence of a course code in the PDF.

    Returns:
        Page number and nearby source text.
    """

    matches = []

    for page in pages:

        text = page["text"]

        pattern = re.compile(
            rf"(?<![A-Z0-9])"
            rf"{re.escape(course_code[:len(course_code.rstrip('0123456789'))])}"
            rf"\s*{re.escape(course_code[len(course_code.rstrip('0123456789')):])}"
            rf"(?!\d)",
            re.IGNORECASE
        )

        for match in pattern.finditer(text):

            start = max(0, match.start() - CONTEXT_SIZE)

            end = min(
                len(text),
                match.end() + CONTEXT_SIZE
            )

            context = text[start:end]

            matches.append({
                "page": page["page"],
                "context": context,
                "normalized_context": normalize_text(context),
            })

    return matches


# =========================================================
# VALIDATE COURSE TITLE
# =========================================================

def validate_title(
    extracted_title: str,
    source_context: str
) -> tuple[str, str]:
    """
    Compare the extracted title against nearby PDF text.

    This is a screening check, not a definitive semantic
    comparison.
    """

    extracted = normalize_text(extracted_title)

    source = normalize_text(source_context)

    if not extracted:
        return "REVIEW", "Extracted title is empty."

    if extracted in source:
        return "PASS", "Title text found in source context."

    extracted_words = set(extracted.split())

    source_words = set(source.split())

    if not extracted_words:
        return "REVIEW", "Unable to compare title."

    overlap = len(extracted_words & source_words)

    similarity = overlap / len(extracted_words)

    sequence_similarity = SequenceMatcher(
        None,
        extracted,
        source
    ).ratio()

    if similarity >= TITLE_SIMILARITY_THRESHOLD:
        return (
            "PASS",
            f"Title tokens found in source context ({similarity:.2f})."
        )

    if sequence_similarity >= TITLE_SIMILARITY_THRESHOLD:
        return (
            "REVIEW",
            "Possible title match; inspect PDF context manually."
        )

    return (
        "REVIEW",
        f"Title could not be confidently verified (overlap: {similarity:.2f})."
    )


# =========================================================
# VALIDATE CREDITS AND L-T-P
# =========================================================

def validate_academic_values(
    course: dict,
    source_context: str
) -> tuple[str, str]:
    """
    Compare credits and L-T-P values against nearby
    source PDF text.

    Expected PDF format:
        L-T-P-C

    Example:
        3-0-2-4
    """

    expected = (
        normalize_number(course.get("lecture", "")),
        normalize_number(course.get("tutorial", "")),
        normalize_number(course.get("practical", "")),
        normalize_number(course.get("credits", "")),
    )

    if any(not value for value in expected):
        return "REVIEW", "One or more CSV academic values are empty."

    source = normalize_text(source_context)

    matches = CREDIT_PATTERN.findall(source)

    if not matches:
        return (
            "REVIEW",
            "No L-T-P-C pattern found in nearby PDF text."
        )

    for match in matches:

        actual = tuple(
            normalize_number(value)
            for value in match
        )

        if actual == expected:

            return (
                "PASS",
                f"Matching L-T-P-C values found: {'-'.join(actual)}"
            )

    source_candidates = [
        "-".join(match)
        for match in matches
    ]

    return (
        "REVIEW",
        "Expected L-T-P-C: "
        + "-".join(expected)
        + "; nearby candidates: "
        + ", ".join(source_candidates)
    )


# =========================================================
# VALIDATE ONE COURSE
# =========================================================

def validate_course(
    course: dict,
    pages: list[dict]
) -> dict:
    """
    Validate one course against the original PDF.
    """

    code = course["code"]

    title = course.get("title", "")

    matches = find_course_in_pdf(code, pages)

    result = {
        "course_code": code,
        "extracted_title": title,
        "source_pages": "",
        "code_status": "",
        "title_status": "",
        "academic_values_status": "",
        "overall_status": "",
        "title_details": "",
        "academic_values_details": "",
        "source_excerpt": "",
    }

    # -----------------------------------------------------
    # Course code validation
    # -----------------------------------------------------

    if not matches:

        result.update({
            "code_status": "NOT_FOUND",
            "title_status": "NOT_VERIFIABLE",
            "academic_values_status": "NOT_VERIFIABLE",
            "overall_status": "REVIEW",
            "title_details": "Course code not found in PDF.",
            "academic_values_details": "Course code not found in PDF.",
        })

        return result

    result["code_status"] = "PASS"

    result["source_pages"] = ", ".join(
        str(match["page"])
        for match in matches
    )

    # -----------------------------------------------------
    # Check title and academic values against each
    # occurrence. The strongest result is retained.
    # -----------------------------------------------------

    title_results = []

    academic_results = []

    for match in matches:

        title_status, title_details = validate_title(
            title,
            match["context"]
        )

        academic_status, academic_details = validate_academic_values(
            course,
            match["context"]
        )

        title_results.append({
            "status": title_status,
            "details": title_details,
        })

        academic_results.append({
            "status": academic_status,
            "details": academic_details,
        })

    # Prefer a passing match over a review result.

    title_result = next(
        (
            item for item in title_results
            if item["status"] == "PASS"
        ),
        title_results[0]
    )

    academic_result = next(
        (
            item for item in academic_results
            if item["status"] == "PASS"
        ),
        academic_results[0]
    )

    result["title_status"] = title_result["status"]

    result["title_details"] = title_result["details"]

    result["academic_values_status"] = academic_result["status"]

    result["academic_values_details"] = academic_result["details"]

    result["source_excerpt"] = matches[0]["context"].replace(
        "\n", " "
    ).strip()

    # -----------------------------------------------------
    # Overall status
    # -----------------------------------------------------

    statuses = [
        result["code_status"],
        result["title_status"],
        result["academic_values_status"],
    ]

    if all(status == "PASS" for status in statuses):

        result["overall_status"] = "PASS"

    else:

        result["overall_status"] = "REVIEW"

    return result


# =========================================================
# DUPLICATE COURSE DETECTION
# =========================================================

def find_duplicate_courses(courses: list[dict]) -> list[str]:
    """
    Identify duplicate course codes in courses.csv.
    """

    counter = Counter(
        course["code"]
        for course in courses
    )

    return [
        code
        for code, count in counter.items()
        if count > 1
    ]


# =========================================================
# GENERATE VALIDATION REPORT
# =========================================================

def generate_report(results: list[dict]) -> None:
    """
    Write validation results to a separate CSV file.
    """

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    fieldnames = [
        "course_code",
        "extracted_title",
        "source_pages",
        "code_status",
        "title_status",
        "academic_values_status",
        "overall_status",
        "title_details",
        "academic_values_details",
        "source_excerpt",
    ]

    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(results)


# =========================================================
# MAIN
# =========================================================

def main() -> int:

    print("=" * 65)
    print("COURSE EXTRACTION SOURCE VALIDATION")
    print("=" * 65)

    try:

        # -------------------------------------------------
        # Step 1: Load normalized CSV
        # -------------------------------------------------

        courses = load_courses()

        print(f"\nCourses loaded from CSV: {len(courses)}")

        # -------------------------------------------------
        # Step 2: Read original PDF
        # -------------------------------------------------

        pages = extract_pdf_pages()

        # -------------------------------------------------
        # Step 3: Check duplicate course codes
        # -------------------------------------------------

        duplicates = find_duplicate_courses(courses)

        print("\nDuplicate course codes:")

        if duplicates:

            for code in duplicates:
                print(f"  - {code}")

        else:

            print("  None")

        # -------------------------------------------------
        # Step 4: Validate every course
        # -------------------------------------------------

        print("\nValidating courses...\n")

        results = []

        for index, course in enumerate(courses, start=1):

            result = validate_course(course, pages)

            results.append(result)

            print(
                f"[{index}/{len(courses)}] "
                f"{result['course_code']} "
                f"-> {result['overall_status']}"
            )

        # -------------------------------------------------
        # Step 5: Generate report
        # -------------------------------------------------

        generate_report(results)

        # -------------------------------------------------
        # Step 6: Print summary
        # -------------------------------------------------

        total = len(results)

        passed = sum(
            result["overall_status"] == "PASS"
            for result in results
        )

        review = sum(
            result["overall_status"] == "REVIEW"
            for result in results
        )

        code_not_found = sum(
            result["code_status"] == "NOT_FOUND"
            for result in results
        )

        print("\n" + "=" * 65)
        print("VALIDATION SUMMARY")
        print("=" * 65)

        print(f"Total courses:       {total}")
        print(f"Passed:              {passed}")
        print(f"Needs review:        {review}")
        print(f"Course codes absent: {code_not_found}")
        print(f"Duplicate codes:     {len(duplicates)}")

        print("\nReport generated:")
        print(REPORT_FILE)

        print("\nIMPORTANT:")
        print(
            "REVIEW results require manual inspection. "
            "They are not automatically confirmed errors."
        )

        print(
            "This script does not modify courses.csv or the PDF."
        )

        print("=" * 65)

        return 0

    except Exception as error:

        print(f"\nVALIDATION FAILED: {error}")

        return 1


if __name__ == "__main__":

    sys.exit(main())