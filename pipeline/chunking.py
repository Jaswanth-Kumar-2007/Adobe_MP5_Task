from pathlib import Path

from pipeline.normalize import read_csv


def load_rows(directory: Path, filename: str):
    """Read a CSV if it exists."""

    file_path = directory / filename

    if not file_path.exists():
        return []

    return read_csv(file_path)[1]


def create_chunk(
    chunk_id: str,
    entity_type: str,
    text: str,
    metadata: dict
):
    """Create a standardized knowledge chunk."""

    return {
        "chunk_id": chunk_id,
        "entity_type": entity_type,
        "text": " ".join(text.split()),
        "metadata": metadata,
    }


def create_chunks(
    normalized_dir: Path,
    chunks_dir: Path
):
    """Generate knowledge chunks from normalized CSV records."""

    chunks = []

    # --------------------------------------------------
    # 1. Course chunks
    # --------------------------------------------------

    courses = load_rows(
        normalized_dir,
        "courses.csv"
    )

    for course in courses:

        code = course.get("code", "").strip()
        title = course.get("title", "").strip()

        fields = [
            ("Course code", code),
            ("Course title", title),
            ("Department", course.get("dept", "")),
            ("Credits", course.get("credits", "")),
            ("Lecture", course.get("lecture", "")),
            ("Tutorial", course.get("tutorial", "")),
            ("Practical", course.get("practical", "")),
            ("Semesters", course.get("semesters", "")),
            ("Course type", course.get("course_type", "")),
            ("Mode", course.get("mode", "")),
            ("Objectives", course.get("objectives", "")),
            ("Syllabus", course.get("syllabus", "")),
            ("Prerequisite information", course.get("prereq_text", "")),
        ]

        text = "\n".join(
            f"{label}: {value}"
            for label, value in fields
            if value.strip()
        )

        if not text.strip():
            continue

        chunks.append(
            create_chunk(
                chunk_id=f"course_{code}",
                entity_type="course",
                text=text,
                metadata={
                    "course_code": code,
                    "department": course.get("dept", ""),
                    "source_file": "courses.csv",
                    "source_url": course.get("source_url", ""),
                },
            )
        )

    # --------------------------------------------------
    # 2. Other entity chunks
    # --------------------------------------------------

    configurations = [
        {
            "filename": "rules.csv",
            "entity_type": "rule",
            "id_field": "id",
            "fields": [
                "category",
                "text",
                "numeric_limit",
                "unit",
                "applies_to",
            ],
        },
        {
            "filename": "skills.csv",
            "entity_type": "skill",
            "id_field": "id",
            "fields": [
                "name",
                "category",
                "level",
                "parent",
            ],
        },
        {
            "filename": "course_topics.csv",
            "entity_type": "course_topic",
            "id_field": "course_code",
            "fields": [
                "topic",
                "unit",
            ],
        },
        {
            "filename": "resources.csv",
            "entity_type": "resource",
            "id_field": "id",
            "fields": [
                "title",
                "provider",
                "description",
                "url",
                "licence_name",
            ],
        },
        {
            "filename": "course_eligibility.csv",
            "entity_type": "course_eligibility",
            "id_field": "course_code",
            "fields": [
                "programme",
                "eligibility_status",
                "conditions",
            ],
        },
        {
            "filename": "program_plan.csv",
            "entity_type": "program_plan",
            "id_field": "course_code",
            "fields": [
                "semester",
                "slot",
            ],
        },
    ]

    for config in configurations:

        records = load_rows(
            normalized_dir,
            config["filename"]
        )

        for index, record in enumerate(records, start=1):

            fields = config["fields"]

            text_parts = []

            for field in fields:

                value = record.get(field, "").strip()

                if value:
                    text_parts.append(f"{field}: {value}")

            text = "\n".join(text_parts)

            if not text:
                continue

            identifier = (
                record.get(config["id_field"], "").strip()
                or str(index)
            )

            chunks.append(
                create_chunk(
                    chunk_id=(
                        f"{config['entity_type']}_{identifier}_{index}"
                    ),
                    entity_type=config["entity_type"],
                    text=text,
                    metadata={
                        "source_file": config["filename"],
                        "record_id": identifier,
                        "source_url": record.get("source_url", ""),
                    },
                )
            )

    chunks_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    return chunks
