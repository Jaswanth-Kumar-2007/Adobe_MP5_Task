import csv

from datetime import datetime
from pathlib import Path


ISSUE_COLUMNS = [
    "severity",
    "check",
    "record",
    "message",
]


def read_manual_resource_audit(reports_dir: Path) -> dict | None:
    """Summarize manual resource metadata without treating it as pipeline input."""

    resource_path = reports_dir.parent / "data" / "manual" / "resources.csv"

    if not resource_path.exists():
        return None

    with resource_path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        rows = list(csv.DictReader(file))

    def populated(field: str) -> int:
        return sum(bool(row.get(field, "").strip()) for row in rows)

    return {
        "records": len(rows),
        "license_name": populated("license_name"),
        "url": populated("url"),
        "topics": populated("topics"),
        "duration": sum(
            bool(row.get("duration_value", "").strip())
            and bool(row.get("duration_unit", "").strip())
            for row in rows
        ),
    }


def write_issues_csv(
    issues: list,
    output_path: Path
):
    """Save validation issues to CSV."""

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
            fieldnames=ISSUE_COLUMNS
        )

        writer.writeheader()
        writer.writerows(issues)


def generate_data_quality_report(
    extraction_summary: dict,
    issues: list,
    export_summary: dict,
    reports_dir: Path
):
    """Generate the final data-quality report."""

    reports_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    errors = sum(
        issue.get("severity") == "ERROR"
        for issue in issues
    )

    warnings = sum(
        issue.get("severity") == "WARN"
        for issue in issues
    )

    lines = [
        "# DSAI Knowledge Base — Data Quality Report",
        "",
        f"- Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "- Input directory: `data/extracted/`",
        "- Original documents are handled by the extraction stage.",
        "- `data/manual/` is not used by this processing pipeline.",
        "",
        "## 1. Entity statistics",
        "",
        "| Entity file | Records | Columns |",
        "|---|---:|---:|",
    ]

    for filename, information in extraction_summary.get(
        "entities", {}
    ).items():

        lines.append(
            f"| `{filename}` "
            f"| {information.get('records', 0)} "
            f"| {information.get('columns', 0)} |"
        )

    lines.extend([
        "",
        f"- Merged evidence records: {extraction_summary.get('evidence_records', 0)}",
        f"- Evidence files merged: {extraction_summary.get('evidence_files', 0)}",
        f"- Course duplicates removed during normalization: "
        f"{extraction_summary.get('deduplicated_courses', 0)}",
        "",
        "## 2. Extractor review files",
        "",
    ])

    incompatible_evidence = extraction_summary.get(
        "incompatible_evidence_files",
        [],
    )
    if incompatible_evidence:
        lines.extend([
            "",
            "## Evidence files not merged",
            "",
        ])
        for item in incompatible_evidence:
            lines.append(
                f"- `{item['file']}`: missing columns "
                f"{', '.join(item['missing_columns'])}"
            )

    review_files = extraction_summary.get(
        "review_files", []
    )

    if review_files:

        for item in review_files:

            lines.append(
                f"- `{item['file']}`: {item['records']} records"
            )

    else:

        lines.append(
            "- No review CSV files were discovered under "
            "`data/extracted/review/`."
        )

    evidence_files = extraction_summary.get(
        "evidence_files_detail",
        [],
    )

    lines.extend([
        "",
        "### Source-evidence files",
        "",
    ])

    if evidence_files:
        for item in evidence_files:
            lines.append(
                f"- `{item['file']}`: {item['records']} records"
            )
    else:
        lines.append(
            "- No source-evidence CSV files were discovered under "
            "`data/extracted/review/`."
        )

    completeness = extraction_summary.get("completeness", {})
    lines.extend([
        "",
        "## 3. Field completeness",
        "",
        "Percentages are calculated only for fields defined in each "
        "entity schema; they measure populated values, not semantic correctness.",
        "",
    ])

    if completeness:
        for filename, fields in completeness.items():
            lines.extend([
                f"### `{filename}`",
                "",
                "| Field | Total | Populated | Missing | Completeness |",
                "|---|---:|---:|---:|---:|",
            ])
            for item in fields:
                lines.append(
                    f"| `{item['field']}` | {item['total']} "
                    f"| {item['populated']} | {item['missing']} "
                    f"| {item['percentage']:.1f}% |"
                )
            lines.append("")

    resource_audit = read_manual_resource_audit(reports_dir)

    lines.extend([
        "## 4. Validation results",
        "",
        f"- Total validation issues: {len(issues)}",
        f"- Errors: **{errors}**",
        f"- Warnings: **{warnings}**",
        "",
        "External prerequisite references remain warnings when a "
        "prerequisite is outside the extracted course collection.",
        "",
        "## 5. Final outputs",
        "",
        f"- Knowledge base JSON: `{export_summary.get('knowledge_base_json', 'Not generated')}`",
        f"- Knowledge base JSONL: `{export_summary.get('knowledge_base_jsonl', 'Not generated')}`",
        f"- Chunks JSONL: `{export_summary.get('chunks_jsonl', 'Not generated')}`",
        f"- Total chunks: {export_summary.get('chunk_count', 0)}",
        "",
        "## 6. Limitations and manual verification",
        "",
        "- Extraction completeness depends on the original document structure.",
        "- Programme-plan candidates should be checked against official programme tables.",
        "- Eligibility candidates require confirmation against official restrictions.",
        "- Missing values are not automatically inferred.",
        "- External prerequisite references may belong to other departments.",
        "- A populated `source_url` may be a local source filename rather "
        "than a clickable web URL when no verified URL is recorded.",
        "- Resource licence verification must be supported by evidence.",
        "",
        "For a practical sample check, select representative rows from "
        "`courses.csv`, `rules.csv`, `program_plan.csv`, and "
        "`course_eligibility.csv`; compare each row with its cited PDF page "
        "and quotation in the review/evidence CSVs. Repeat for topic, skill, "
        "and prerequisite mappings, and record any discrepancy for manual review.",
        "",
        "Structural validation and populated-field percentages do not prove "
        "semantic correctness.",
        "",
        "## 7. Manual resource audit",
        "",
    ])

    if resource_audit is None:
        lines.append("- `data/manual/resources.csv` was not found.")
    else:
        lines.extend([
            "- Records: "
            f"**{resource_audit['records']}**",
            "- Licence names populated: "
            f"**{resource_audit['license_name']}**",
            "- Direct URLs populated: "
            f"**{resource_audit['url']}**",
            "- Topic mappings populated: "
            f"**{resource_audit['topics']}**",
            "- Complete duration value/unit pairs: "
            f"**{resource_audit['duration']}**",
            "- This manually collected dataset is not consumed by "
            "`run_pipeline.py`.",
            "- Automatic resource discovery is disabled; these records "
            "remain unverified candidates.",
            "",
        ])

    lines.extend([
        "## 8. Validation issue details",
        "",
    ])

    if issues:

        for issue in issues:

            lines.append(
                f"- **{issue['severity']}** | "
                f"{issue['check']} | "
                f"{issue['record']} | "
                f"{issue['message']}"
            )

    else:

        lines.append("No validation issues were detected.")

    report_path = reports_dir / "data_quality_report.md"

    with report_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        file.write("\n".join(lines))

    write_issues_csv(
        issues,
        reports_dir / "validation_issues.csv"
    )

    return report_path
