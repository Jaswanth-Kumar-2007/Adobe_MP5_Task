# Adobe DSAI Knowledge Base

Source-traced academic data pipeline for the B.Tech Data Science and Artificial Intelligence (DSAI) programme at IIT Bhilai.

## Project overview

The project reads three public institute PDFs, extracts course and programme information, normalizes and validates the extracted CSV files, builds course relationships, creates metadata-rich record chunks, and exports JSON/JSONL files. The normal pipeline stops before embeddings and does not call an LLM or embedding API.

The repository distinguishes automatic extraction from legacy manually curated data. The main pipeline reads `data/raw/` and `data/extracted/`; it does not consume `data/manual/`.

## Problem statement

Academic information is distributed across PDF documents and contains incomplete, duplicated, or ambiguous records. This project turns that information into structured candidates that can be reviewed, connected, and consumed by a future retrieval system without claiming that every extracted record is verified.

## Key features

- PDF extraction for courses, rules, programme plans, catalogue records, and eligibility candidates.
- Syllabus-derived topics and taxonomy-based skills.
- Source evidence and review CSVs for uncertain records.
- Normalization, structural validation, relationship generation, and record-based chunking.
- JSON, JSONL, and chunk JSONL exports.
- Independent course extraction validator.
- Disabled automatic resource discovery, with manual resources retained separately for follow-up.

## Architecture

```mermaid
flowchart TD
    run["python run_pipeline.py"] --> pipeline["run_pipeline.py"]
    pipeline --> extraction["run_extraction.py"]

    subgraph sources["Original source PDFs"]
        cos[(data/raw/Course_of_Study.pdf)]
        ug[(data/raw/UG_Manual.pdf)]
        cat[(data/raw/List_of_courses_V4.pdf)]
    end

    cos --> coursesExtractor["extract_courses.py"]
    cos --> planExtractor["extract_semester_courses.py<br/>(active programme-plan extractor)"]
    ug --> rulesExtractor["extract_rules.py"]
    cat --> catalogueExtractor["extract_course_catalogue.py"]
    coursesExtractor --> courseCsv[/courses.csv + prerequisites.csv/]
    coursesExtractor --> courseReview{{"course review/evidence CSVs"}}
    planExtractor --> planCsv[/program_plan.csv/]
    planExtractor --> planReview{{"programme-plan review/evidence CSVs"}}
    rulesExtractor --> rulesCsv[/rules.csv/]
    rulesExtractor --> rulesReview{{"UG Manual review/evidence CSVs"}}
    catalogueExtractor --> catalogueCsv[/course_catalogue.csv + course_eligibility.csv/]
    catalogueExtractor --> catalogueReview{{"catalogue review CSVs"}}

    courseCsv --> topics["generate_topics_skills.py<br/>+ curated skill taxonomy"]
    topics --> topicCsv[/course_topics.csv + skills.csv + course_skills.csv/]

    resourceDisabled["extract_resources.py<br/>DISABLED: DuckDuckGo timeouts"]:::disabled
    topicCsv -. would provide search inputs .-> resourceDisabled
    manualRes[(data/manual/resources.csv<br/>manual, not pipeline input)]:::manual

    extraction --> normalize["Normalize<br/>pipeline/normalize.py"]
    courseCsv --> normalize
    rulesCsv --> normalize
    planCsv --> normalize
    catalogueCsv --> normalize
    topicCsv --> normalize
    normalize --> validate["Validate<br/>pipeline/validate.py"]
    validate --> relationships["Relationships<br/>pipeline/relationships.py"]
    relationships --> chunk["Chunk records<br/>pipeline/chunking.py"]
    chunk --> export["Export<br/>pipeline/export.py"]
    export --> reports["Reports<br/>pipeline/reports.py"]
    export --> json[/output/knowledge_base.json/]
    export --> jsonl[/output/knowledge_base.jsonl/]
    export --> chunks[/output/chunks.jsonl/]
    reports --> reportFiles{{"reports/data_quality_report.md<br/>reports/validation_issues.csv"}}

    standalone["validators/validate_extracted_data.py"] -. independent .-> validationReport{{"reports/course_extraction_validation.csv"}}
    cos -. reads .-> standalone
    courseCsv -. reads .-> standalone

    classDef disabled fill:#ffe0e0,stroke:#b00020,color:#700000;
    classDef manual fill:#fff4cc,stroke:#997000,color:#5c4500;
```

## Quick start

The repository URL and directory name are not available because no Git remote is configured in this checkout. Replace the placeholders below with the repository's actual clone URL and directory:

```bash
git clone https://github.com/Jaswanth-Kumar-2007/Adobe_MP5_Task.git
cd Adobe_MP5_Task

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

python run_pipeline.py
```

Before running, ensure the original PDFs are present in `data/raw/`. The command performs source extraction, normalization, validation, relationship generation, chunking, export, and reporting. Expected outputs are written to `output/`, `data/processed/`, and `reports/`.

## Project documentation

- [Extraction Documentation](docs/extraction.md)
- [Pipeline Documentation](docs/pipeline.md)
- [Project Structure](docs/project-structure.md)
- [Sources](SOURCES.md)
- [Ideas](IDEAS.md)

## Current implementation and audit results

Latest checked-in pipeline report metrics:

| Requirement | Status | Evidence |
|---|---|---|
| At least 15 courses | **PASS** | 25 normalized courses in `reports/data_quality_report.md`. |
| Course metadata completeness | **PARTIAL** | Required columns exist, but normalized syllabus is present for 24/25 courses, objectives are empty, and semester/type/mode fields are incomplete. |
| Academic rules | **PARTIAL** | 134 rule candidates; review files identify records needing human inspection. |
| At least 30 open learning resources | **PARTIAL** | 192 manual rows exist, but automatic discovery is disabled and required licence/mapping completeness is not met. |
| Normalization | **PASS** | `pipeline/normalize.py` normalizes fields and removes only unambiguous lower-quality duplicate course records. |
| Validation | **PARTIAL** | Structural, duplicate, credit, reference, provenance, and prerequisite checks exist; prerequisite-cycle detection and completeness percentages do not. |
| Relationships | **PASS** | Course relationships are written to `data/processed/relationships/course_relationships.json`. |
| Chunking | **PARTIAL** | 669 record-based chunks are generated; the implementation does not split text into token or semantic windows. |
| Export | **PASS** | JSON, JSONL, and chunk JSONL outputs are generated under `output/`. |
| No embeddings/LLM API calls | **PASS** | The normal Python pipeline stops before embedding. |
| Data-quality report | **PARTIAL** | Counts and six warnings are reported; field-completeness percentages are not calculated. |
| `SOURCES.md` | **MISSING** | Not present in the repository. |
| `IDEAS.md` | **MISSING** | Not present in the repository. |

Latest report metrics are 25 normalized courses, 134 rules, 46 programme-plan records, 251 eligibility records, 185 topics, 125 course-skill mappings, 289 evidence records, 669 chunks, 0 validation errors, and 6 validation warnings. These are extracted or candidate records, not proof of semantic verification.

## AI usage disclosure

ChatGPT was used during development to help create and refine the Python extraction scripts and pipeline implementation. ChatGPT was also used for debugging assistance, code review, and documentation. The actual extraction and processing pipeline runs through the repository's Python scripts, handles PDFs and generated outputs locally, and does not call an LLM or embedding API during normal execution.

## Limitations and future improvements

- Automatic resource discovery is disabled because repeated DuckDuckGo requests timed out.
- `data/manual/resources.csv` is not consumed by `run_pipeline.py`.
- Academic rules, eligibility candidates, programme-plan records, and some course records require human review.
- Some course syllabus/objective fields are incomplete.
- PDF filenames are sometimes stored in `source_url` fields instead of clickable source URLs.
- The latest six warnings concern prerequisite references outside the collected course set.
- Future work should verify manual resources, licences, mappings, source URLs, and assignment deliverables without treating a zero-error run as full verification.
