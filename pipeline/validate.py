import re
from pathlib import Path

from pipeline.normalize import read_csv


REQUIRED_COLUMNS = {
    "courses.csv": [
        "code",
        "title",
    ],
    "rules.csv": [
        "id",
        "category",
        "text",
    ],
    "skills.csv": [
        "id",
        "name",
    ],
    "course_topics.csv": [
        "course_code",
        "topic",
    ],
    "course_skills.csv": [
        "course",
        "skill",
    ],
    "prerequisites.csv": [
        "course",
        "requires",
    ],
    "program_plan.csv": [
        "semester",
        "course_code",
    ],
    "course_eligibility.csv": [
        "course_code",
        "eligibility_status",
    ],
    "resources.csv": [
        "id",
        "title",
        "url",
    ],
    "source_evidence.csv": [
        "record_id",
        "record_type",
        "pdf_page",
    ],
}

COURSE_CODE_PATTERN = re.compile(
    r"^[A-Z]{2,5}\d{3}$"
)

EXPECTED_SKIPPED_FILES = {
    "resources.csv",
}

REQUIREMENT_SLOT_PATTERN = re.compile(
    r"(?i)\b(?:PE|OE|LA(?:\s+Courses?)?|elective|requirement)\b"
)


def validate_all(normalized_dir: Path):
    """Validate all available normalized CSV files."""

    issues = []
    loaded_data = {}

    def add_issue(
        severity,
        check,
        record,
        message
    ):
        issues.append({
            "severity": severity,
            "check": check,
            "record": record,
            "message": message,
        })

    # --------------------------------------------------
    # 1. Check files and schemas
    # --------------------------------------------------

    for filename, required_columns in REQUIRED_COLUMNS.items():

        file_path = normalized_dir / filename

        if not file_path.exists():

            if filename == "courses.csv":
                add_issue(
                    "ERROR",
                    "required_file",
                    filename,
                    "Required courses.csv file is missing."
                )

            elif filename in EXPECTED_SKIPPED_FILES:
                continue
            else:
                add_issue(
                    "WARN",
                    "optional_file",
                    filename,
                    "Optional CSV file was not generated."
                )

            continue

        try:
            headers, records = read_csv(file_path)

        except Exception as exc:
            add_issue(
                "ERROR",
                "csv_read",
                filename,
                f"Could not read CSV: {exc}"
            )
            continue

        loaded_data[filename] = records

        missing_columns = [
            column
            for column in required_columns
            if column not in headers
        ]

        if missing_columns:

            add_issue(
                "ERROR",
                "schema_columns",
                filename,
                "Missing columns: " + ", ".join(missing_columns)
            )

            continue

        if not records:

            add_issue(
                "WARN",
                "empty_entity",
                filename,
                "CSV exists but contains no records."
            )

        # Check mandatory values.
        for row_number, record in enumerate(records, start=2):

            for column in required_columns:

                value = record.get(column, "").strip()

                if (
                    filename == "program_plan.csv"
                    and column == "course_code"
                    and not value
                    and REQUIREMENT_SLOT_PATTERN.search(
                        record.get("slot", "").strip()
                    )
                ):
                    continue

                if not value:

                    severity = (
                        "ERROR"
                        if filename == "courses.csv"
                        else "WARN"
                    )

                    add_issue(
                        severity,
                        "required_value",
                        f"{filename}:row {row_number}",
                        f"Required field '{column}' is empty."
                    )

    # --------------------------------------------------
    # 2. Validate course records
    # --------------------------------------------------

    courses = loaded_data.get("courses.csv", [])

    known_courses = set()
    seen_courses = set()

    for row_number, course in enumerate(courses, start=2):

        code = course.get("code", "").strip().upper()

        if code:

            if code in seen_courses:

                add_issue(
                    "ERROR",
                    "duplicate_course",
                    code,
                    "Duplicate course code."
                )

            seen_courses.add(code)
            known_courses.add(code)

            if not COURSE_CODE_PATTERN.fullmatch(code):

                add_issue(
                    "WARN",
                    "course_code_format",
                    code,
                    "Course code does not match the expected pattern."
                )

        # Credits validation.
        credits = course.get("credits", "").strip()

        if credits:

            try:
                value = float(credits)

                if value <= 0 or value > 30:
                    raise ValueError

            except ValueError:

                add_issue(
                    "ERROR",
                    "course_credits",
                    code or f"courses.csv:row {row_number}",
                    "Credits must be numeric and between 0 and 30."
                )

    # --------------------------------------------------
    # 3. Validate prerequisite references
    # --------------------------------------------------

    for row_number, record in enumerate(
        loaded_data.get("prerequisites.csv", []),
        start=2
    ):

        course = record.get("course", "").strip().upper()
        required = record.get("requires", "").strip().upper()

        if course and course not in known_courses:

            add_issue(
                "WARN",
                "unknown_prerequisite_course",
                f"prerequisites.csv:row {row_number}",
                f"Course {course} is not in courses.csv."
            )

        if required and required not in known_courses:

            add_issue(
                "WARN",
                "external_prerequisite",
                required,
                f"Prerequisite referenced by {course} is not in this course collection."
            )

    # --------------------------------------------------
    # 4. Validate course-skill relationships
    # --------------------------------------------------

    skill_ids = {
        record.get("id", "").strip().casefold()
        for record in loaded_data.get("skills.csv", [])
        if record.get("id", "").strip()
    }

    for row_number, record in enumerate(
        loaded_data.get("course_skills.csv", []),
        start=2
    ):

        course = record.get("course", "").strip().upper()
        skill = record.get("skill", "").strip().casefold()

        if course and course not in known_courses:

            add_issue(
                "WARN",
                "unknown_skill_course",
                f"course_skills.csv:row {row_number}",
                f"Course {course} is not in courses.csv."
            )

        if skill and skill_ids and skill not in skill_ids:

            add_issue(
                "WARN",
                "unknown_skill",
                f"course_skills.csv:row {row_number}",
                f"Skill '{record.get('skill', '')}' is not in skills.csv."
            )

    # --------------------------------------------------
    # 5. Validate topic-course references
    # --------------------------------------------------

    for row_number, record in enumerate(
        loaded_data.get("course_topics.csv", []),
        start=2
    ):

        code = record.get("course_code", "").strip().upper()

        if code and code not in known_courses:

            add_issue(
                "WARN",
                "unknown_topic_course",
                f"course_topics.csv:row {row_number}",
                f"Course {code} is not in courses.csv."
            )

    # --------------------------------------------------
    # 5b. Validate programme-plan course references
    # --------------------------------------------------

    for row_number, record in enumerate(
        loaded_data.get("program_plan.csv", []),
        start=2
    ):

        course_code = record.get("course_code", "").strip().upper()
        slot = record.get("slot", "").strip()

        if course_code and not COURSE_CODE_PATTERN.fullmatch(course_code):
            add_issue(
                "WARN",
                "program_plan_course_code_format",
                f"program_plan.csv:row {row_number}",
                f"Course code '{course_code}' does not match the expected pattern."
            )

        if not course_code and not REQUIREMENT_SLOT_PATTERN.search(slot):
            add_issue(
                "WARN",
                "program_plan_requirement",
                f"program_plan.csv:row {row_number}",
                "Empty course_code is allowed only for a descriptive elective or requirement slot."
            )

    # --------------------------------------------------
    # 6. Validate source provenance
    # --------------------------------------------------

    provenance_files = [
        "courses.csv",
        "rules.csv",
        "skills.csv",
        "course_topics.csv",
        "course_skills.csv",
        "prerequisites.csv",
        "program_plan.csv",
        "course_eligibility.csv",
        "resources.csv",
    ]

    for filename in provenance_files:

        for row_number, record in enumerate(
            loaded_data.get(filename, []),
            start=2
        ):

            if (
                "source_url" in record
                and not record.get("source_url", "").strip()
                and not (
                    filename == "skills.csv"
                    and record.get("source_type", "").strip().casefold()
                    == "curated_taxonomy"
                )
            ):

                add_issue(
                    "WARN",
                    "missing_source_url",
                    f"{filename}:row {row_number}",
                    "Source URL is empty."
                )

            if (
                "source_type" in record
                and not record.get("source_type", "").strip()
            ):

                add_issue(
                    "WARN",
                    "missing_source_type",
                    f"{filename}:row {row_number}",
                    "Source type is empty."
                )

    # --------------------------------------------------
    # 7. Validate learning resources
    # --------------------------------------------------

    for row_number, resource in enumerate(
        loaded_data.get("resources.csv", []),
        start=2
    ):

        status = resource.get(
            "verification_status",
            ""
        ).strip().casefold()

        if status not in {
            "verified",
            "verified_free",
            "verified_open",
        }:

            add_issue(
                "WARN",
                "resource_verification",
                f"resources.csv:row {row_number}",
                "Resource licence or verification status is not confirmed."
            )

    return issues