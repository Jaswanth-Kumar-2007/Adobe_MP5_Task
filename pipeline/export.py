import json
from pathlib import Path

from pipeline.normalize import read_csv


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
    "source_evidence.csv",
]


def export_knowledge_base(
    normalized_dir: Path,
    output_dir: Path,
    chunks: list,
    relationships: dict
):
    """Export the complete knowledge base in JSON and JSONL formats."""

    entities = {}

    # Load every available entity.
    for filename in ENTITY_FILES:

        file_path = normalized_dir / filename

        entity_name = filename.removesuffix(".csv")

        if file_path.exists():

            _, records = read_csv(file_path)

            entities[entity_name] = records

        else:

            entities[entity_name] = []

    # Build the final knowledge base.
    knowledge_base = {
        "metadata": {
            "project": "DSAI Knowledge Base",
            "schema_version": "1.0",
        },

        "entities": entities,

        "relationships": relationships,

        "statistics": {
            entity_name: len(records)
            for entity_name, records in entities.items()
        },
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------
    # JSON export
    # --------------------------------------------------

    json_path = output_dir / "knowledge_base.json"

    with json_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            knowledge_base,
            file,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------------
    # JSONL export
    # --------------------------------------------------

    jsonl_path = output_dir / "knowledge_base.jsonl"

    with jsonl_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        for entity_name, records in entities.items():

            for index, record in enumerate(records, start=1):

                record_id = (
                    record.get("code")
                    or record.get("id")
                    or record.get("course_code")
                    or str(index)
                )

                item = {
                    "entity_type": entity_name,
                    "record_id": record_id,
                    "data": record,
                }

                file.write(
                    json.dumps(
                        item,
                        ensure_ascii=False
                    ) + "\n"
                )

    # --------------------------------------------------
    # Chunk export
    # --------------------------------------------------

    chunks_path = output_dir / "chunks.jsonl"

    with chunks_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        for chunk in chunks:

            file.write(
                json.dumps(
                    chunk,
                    ensure_ascii=False
                ) + "\n"
            )

    return {
        "knowledge_base_json": str(json_path),
        "knowledge_base_jsonl": str(jsonl_path),
        "chunks_jsonl": str(chunks_path),

        "entity_counts": knowledge_base["statistics"],

        "chunk_count": len(chunks),
    }
