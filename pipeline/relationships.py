import json
from pathlib import Path

from pipeline.normalize import read_csv


def load_rows(directory: Path, filename: str):
    """Load a CSV if it exists."""

    file_path = directory / filename

    if not file_path.exists():
        return []

    return read_csv(file_path)[1]


def build_relationships(
    normalized_dir: Path,
    output_dir: Path
):
    """Build relationships between knowledge-base entities."""

    courses = load_rows(
        normalized_dir,
        "courses.csv"
    )

    prerequisites = load_rows(
        normalized_dir,
        "prerequisites.csv"
    )

    course_skills = load_rows(
        normalized_dir,
        "course_skills.csv"
    )

    topics = load_rows(
        normalized_dir,
        "course_topics.csv"
    )

    program_plan = load_rows(
        normalized_dir,
        "program_plan.csv"
    )

    eligibility = load_rows(
        normalized_dir,
        "course_eligibility.csv"
    )

    relationships = {}

    # Initialize every course.
    for course in courses:

        code = course.get("code", "").strip().upper()

        if not code:
            continue

        relationships[code] = {
            "prerequisites": [],
            "skills": [],
            "topics": [],
            "program_plan": [],
            "eligibility": [],
        }

    # Prerequisites.
    for record in prerequisites:

        code = record.get("course", "").strip().upper()

        if code in relationships:
            relationships[code]["prerequisites"].append(record)

    # Course skills.
    for record in course_skills:

        code = record.get("course", "").strip().upper()

        if code in relationships:
            relationships[code]["skills"].append(record)

    # Course topics.
    for record in topics:

        code = record.get("course_code", "").strip().upper()

        if code in relationships:
            relationships[code]["topics"].append(record)

    # Programme plan.
    for record in program_plan:

        code = record.get("course_code", "").strip().upper()

        if code in relationships:
            relationships[code]["program_plan"].append(record)

    # Eligibility.
    for record in eligibility:

        code = record.get("course_code", "").strip().upper()

        if code in relationships:
            relationships[code]["eligibility"].append(record)

    result = {
        "course_relationships": relationships,
        "summary": {
            "total_courses": len(relationships),

            "courses_with_prerequisites": sum(
                bool(item["prerequisites"])
                for item in relationships.values()
            ),

            "courses_with_skills": sum(
                bool(item["skills"])
                for item in relationships.values()
            ),

            "courses_with_topics": sum(
                bool(item["topics"])
                for item in relationships.values()
            ),

            "courses_with_program_plan": sum(
                bool(item["program_plan"])
                for item in relationships.values()
            ),

            "courses_with_eligibility": sum(
                bool(item["eligibility"])
                for item in relationships.values()
            ),
        },
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = output_dir / "course_relationships.json"

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False
        )

    return result
