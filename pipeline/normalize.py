import csv
import re
from pathlib import Path


ENTITY_FILES = [
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

EVIDENCE_FILES = [
    "source_evidence.csv",
    "program_plan_evidence.csv",
    "course_eligibility_evidence.csv",
]

REVIEW_FILES = [
    "extraction_review.csv",
    "program_plan_review.csv",
    "course_eligibility_review.csv",
    "ug_manual_review.csv",
]

COMPLETENESS_FIELDS = {
    "courses.csv": [
        "code",
        "title",
        "credits",
        "semesters",
        "course_type",
        "mode",
        "objectives",
        "syllabus",
        "prereq_text",
        "source_url",
    ],
    "rules.csv": [
        "id",
        "category",
        "text",
        "source_url",
        "source_type",
    ],
    "program_plan.csv": [
        "semester",
        "course_code",
        "slot",
        "source_url",
    ],
    "course_eligibility.csv": [
        "course_code",
        "programme",
        "eligibility_status",
        "conditions",
        "source_url",
    ],
    "course_topics.csv": [
        "course_code",
        "topic",
        "unit",
        "source_url",
    ],
    "skills.csv": [
        "id",
        "name",
        "category",
        "level",
        "parent",
        "source_url",
    ],
    "prerequisites.csv": [
        "course",
        "requires",
        "kind",
        "group",
        "source_url",
    ],
    "course_skills.csv": [
        "course",
        "skill",
        "depth",
        "source_url",
    ],
    "resources.csv": [
        "resource_id",
        "title",
        "provider",
        "url",
        "license_name",
        "duration_value",
        "topics",
    ],
}

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


def read_csv(file_path: Path):
    """Read a CSV safely and return its headers and records."""

    with file_path.open(
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            return [], []

        headers = [
            str(column).strip()
            for column in reader.fieldnames
        ]

        records = []

        for row in reader:

            cleaned_row = {}

            for key, value in row.items():

                if key is None:
                    continue

                cleaned_key = str(key).strip()

                cleaned_value = (
                    value.strip()
                    if isinstance(value, str)
                    else ""
                )

                cleaned_row[cleaned_key] = cleaned_value

            records.append(cleaned_row)

    return headers, records


def write_csv(file_path: Path, headers: list, records: list):
    """Write records to a CSV safely."""

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=headers,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(records)


def calculate_completeness(
        filename: str,
        headers: list,
        records: list,
) -> list[dict]:
        """Calculate populated-field counts for fields present in an entity CSV."""

        fields = [
            field
            for field in COMPLETENESS_FIELDS.get(filename, [])
            if field in headers
        ]

        result = []
        total = len(records)

        for field in fields:
            populated = sum(
                bool(record.get(field, "").strip())
                for record in records
            )
            missing = total - populated
            percentage = (
                (populated / total) * 100
                if total
                else 0
            )
            result.append({
                "field": field,
                "total": total,
                "populated": populated,
                "missing": missing,
                "percentage": percentage,
            })

        return result


def normalize_value(value: str) -> str:
    """Normalize whitespace without changing the meaning."""

    if not isinstance(value, str):
        return ""

    return " ".join(value.split())


def normalize_csv(input_path: Path, output_path: Path):
    """Normalize one CSV file."""

    headers, records = read_csv(input_path)

    normalized_records = []

    for record in records:

        normalized_record = {
            key: normalize_value(value)
            for key, value in record.items()
        }

        normalized_records.append(normalized_record)

    write_csv(
        output_path,
        headers,
        normalized_records
    )

    return {
        "file": input_path.name,
        "records": len(normalized_records),
        "columns": len(headers),
    }


def _course_record_quality(record: dict) -> tuple[int, int]:
    """Rank course records without synthesizing or merging field values."""

    fields = (
        "title",
        "credits",
        "lecture",
        "tutorial",
        "practical",
        "objectives",
        "syllabus",
        "prereq_text",
        "source_url",
        "retrieved_on",
        "source_type",
    )
    populated = sum(bool(record.get(field, "").strip()) for field in fields)

    title = record.get("title", "").strip()
    malformed_title = bool(
        re.search(r"\b\d+(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?", title)
        or re.fullmatch(r"(?:[A-Z]{2,5}\d{3}\s*)+", title)
    )

    return populated, -int(malformed_title)


def normalize_courses(input_path: Path, output_path: Path) -> dict:
    """Normalize courses and remove only unambiguous malformed duplicates."""

    headers, records = read_csv(input_path)
    grouped: dict[str, list[dict]] = {}

    for record in records:
        code = record.get("code", "").strip().upper()
        grouped.setdefault(code, []).append(record)

    normalized_records = []
    removed_duplicates = 0

    for code, candidates in grouped.items():
        if not code or len(candidates) == 1:
            normalized_records.extend(candidates)
            continue

        ranked = sorted(
            candidates,
            key=_course_record_quality,
            reverse=True,
        )

        if _course_record_quality(ranked[0]) > _course_record_quality(ranked[1]):
            normalized_records.append(ranked[0])
            removed_duplicates += len(candidates) - 1
        else:
            normalized_records.extend(candidates)

    normalized_records = [
        {
            key: normalize_value(value)
            for key, value in record.items()
        }
        for record in normalized_records
    ]

    write_csv(output_path, headers, normalized_records)

    return {
        "file": input_path.name,
        "records": len(normalized_records),
        "columns": len(headers),
        "removed_duplicates": removed_duplicates,
    }


def merge_evidence(extracted_dir: Path, normalized_dir: Path):
    """Merge evidence files generated by individual extractors."""

    evidence_records = []
    seen = set()
    incompatible_files = []

    evidence_paths = {
        extracted_dir / filename
        for filename in EVIDENCE_FILES
        if (extracted_dir / filename).exists()
    }
    evidence_paths.update(
        path
        for path in extracted_dir.rglob("*evidence*.csv")
        if path.is_file()
    )

    for file_path in sorted(evidence_paths):

        headers, records = read_csv(file_path)

        missing_columns = [
            column
            for column in EVIDENCE_COLUMNS
            if column not in headers
        ]
        if missing_columns:
            incompatible_files.append({
                "file": str(file_path.relative_to(extracted_dir)),
                "missing_columns": missing_columns,
            })
            continue

        for record in records:

            cleaned_record = {
                column: normalize_value(record.get(column, ""))
                for column in EVIDENCE_COLUMNS
            }

            key = tuple(
                cleaned_record[column]
                for column in EVIDENCE_COLUMNS
            )

            if key not in seen:
                seen.add(key)
                evidence_records.append(cleaned_record)

    output_path = normalized_dir / "source_evidence.csv"

    if evidence_records or evidence_paths:
        write_csv(
            output_path,
            EVIDENCE_COLUMNS,
            evidence_records
        )

    return {
        "records": len(evidence_records),
        "files": len(evidence_paths) - len(incompatible_files),
        "incompatible_files": incompatible_files,
    }


def discover_review_files(extracted_dir: Path) -> tuple[list[dict], list[dict]]:
    """Discover nested review and evidence CSVs under the review directory."""

    review_root = extracted_dir / "review"
    review_files = []
    evidence_files = []

    if not review_root.is_dir():
        return review_files, evidence_files

    for file_path in sorted(review_root.rglob("*.csv")):
        headers, records = read_csv(file_path)
        item = {
            "file": str(file_path.relative_to(extracted_dir)),
            "records": len(records),
            "columns": len(headers),
        }

        if "evidence" in file_path.stem.casefold():
            evidence_files.append(item)
        else:
            review_files.append(item)

    return review_files, evidence_files


def copy_review_files(extracted_dir: Path, normalized_dir: Path):
    """Copy extractor review files for quality reporting."""

    copied = []

    review_files, _ = discover_review_files(extracted_dir)

    for item in review_files:
        source_path = extracted_dir / item["file"]
        destination = normalized_dir / item["file"]
        headers, records = read_csv(source_path)

        write_csv(
            destination,
            headers,
            records
        )

        copied.append({
            "file": item["file"],
            "records": len(records),
        })

    return copied


def normalize_all(
    extracted_dir: Path,
    normalized_dir: Path
):
    """
    Normalize all available extractor-generated entity files.

    data/manual is intentionally not used.
    """

    if not extracted_dir.exists():
        raise FileNotFoundError(
            f"Extracted directory does not exist: {extracted_dir}"
        )

    if not extracted_dir.is_dir():
        raise NotADirectoryError(
            f"Expected a directory: {extracted_dir}"
        )

    normalized_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    summary = {
        "entities": {},
        "evidence_records": 0,
        "review_files": [],
        "evidence_files_detail": [],
        "completeness": {},
    }

    for filename in ENTITY_FILES:

        source_path = extracted_dir / filename

        if not source_path.exists():
            continue

        output_path = normalized_dir / filename

        if filename == "courses.csv":
            result = normalize_courses(source_path, output_path)
        else:
            result = normalize_csv(source_path, output_path)

        normalized_headers, normalized_records = read_csv(output_path)
        summary["entities"][filename] = result
        summary["completeness"][filename] = calculate_completeness(
            filename,
            normalized_headers,
            normalized_records,
        )

    if not (normalized_dir / "courses.csv").exists():
        raise FileNotFoundError(
            "Required courses.csv was not found. "
            "Run the course extractor first."
        )

    evidence_summary = merge_evidence(
        extracted_dir,
        normalized_dir
    )
    summary["evidence_records"] = evidence_summary["records"]
    summary["evidence_files"] = evidence_summary["files"]
    summary["incompatible_evidence_files"] = evidence_summary[
        "incompatible_files"
    ]
    summary["deduplicated_courses"] = summary["entities"].get(
        "courses.csv",
        {},
    ).get("removed_duplicates", 0)

    summary["review_files"] = copy_review_files(
        extracted_dir,
        normalized_dir
    )
    _, summary["evidence_files_detail"] = discover_review_files(
        extracted_dir
    )

    return summary