import csv

from datetime import datetime
from pathlib import Path


ISSUE_COLUMNS = [
    "severity",
    "check",
    "record",
    "message",
]


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

        lines.append("- No review files were generated.")

    lines.extend([
        "",
        "## 3. Validation results",
        "",
        f"- Total validation issues: {len(issues)}",
        f"- Errors: **{errors}**",
        f"- Warnings: **{warnings}**",
        "",
        "## 4. Final outputs",
        "",
        f"- Knowledge base JSON: `{export_summary.get('knowledge_base_json', 'Not generated')}`",
        f"- Knowledge base JSONL: `{export_summary.get('knowledge_base_jsonl', 'Not generated')}`",
        f"- Chunks JSONL: `{export_summary.get('chunks_jsonl', 'Not generated')}`",
        f"- Total chunks: {export_summary.get('chunk_count', 0)}",
        "",
        "## 5. Limitations and verification",
        "",
        "- Extraction completeness depends on the original document structure.",
        "- Programme-plan candidates should be checked against official programme tables.",
        "- Eligibility candidates require confirmation against official restrictions.",
        "- Missing values are not automatically inferred.",
        "- External prerequisite references may belong to other departments.",
        "- Resource licence verification must be supported by evidence.",
        "",
        "## 6. Validation issue details",
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
