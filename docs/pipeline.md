# Pipeline documentation

## One command: raw files to final outputs

The assignment describes five conceptual stages: ingest, parse and normalise, validate, chunk, and export. This repository performs document extraction before those stages and adds relationship generation and reporting as implementation steps.

### 1. Ingest

- Original PDFs remain in `data/raw/`.
- `run_extraction.py` reads those source documents without treating `data/manual/` as pipeline input.
- Enabled extractors write primary CSVs and review/evidence files under `data/extracted/`.

### 2. Parse and normalise

- Extractors standardize course codes while parsing source text and tables.
- `pipeline/normalize.py` strips surrounding whitespace and collapses repeated whitespace across available fields.
- Course records are grouped by uppercased code; only an unambiguously lower-quality duplicate is removed.
- The normalizer writes entities to `data/processed/normalized/` and merges compatible evidence into `source_evidence.csv`.
- Semester labels, titles, credits, and other source fields are retained and cleaned, but missing values are not synthesized.

### 3. Validate

The current checks are classified as follows:

| Assignment expectation | Current implementation |
|---|---|
| Missing prerequisite references | **Implemented as warnings** when a prerequisite is outside the collected course set. |
| Prerequisite cycles | **Not implemented**; no prerequisite graph cycle search exists. |
| Non-numeric credits | **Implemented** as an error for invalid or out-of-range values. |
| Duplicate course codes | **Implemented** as an error after normalization. |
| Missing source URLs | **Implemented as warnings** when a field exists but is empty; filename values are not verified web URLs. |

The validator also checks required schemas and values, course-skill and topic references, programme-plan codes/slots, source types, and resource verification status when `resources.csv` exists. Errors are counted separately from warnings, and validation errors do not immediately stop later relationship, chunk, export, and report steps.

### 4. Chunk

- Chunking is record-based, not token-window or semantic text splitting.
- Configured course, rule, skill, course-topic, resource, eligibility, and programme-plan records can become chunks when populated.
- Each chunk has a `chunk_id`, `entity_type`, normalized text, and metadata such as parent record identifiers, source file, and source URL.
- The generated chunks are exported to `output/chunks.jsonl`; `data/processed/chunks/` is created but does not receive the chunk records.

### 5. Export

| Output | Location | Purpose |
|---|---|---|
| Normalized entity CSVs | `data/processed/normalized/` | Cleaned intermediate records for later stages. |
| Relationship JSON | `data/processed/relationships/course_relationships.json` | Course-linked prerequisites, skills, topics, programme-plan, and eligibility records. |
| Knowledge base JSON | `output/knowledge_base.json` | Nested entities, relationships, metadata, and statistics. |
| Knowledge base JSONL | `output/knowledge_base.jsonl` | One JSON record per entity row. |
| Chunk JSONL | `output/chunks.jsonl` | Record-based chunks with retrieval-ready metadata. |
| Data-quality report | `reports/data_quality_report.md` | Counts, validation totals, limitations, and output paths. |
| Validation issues | `reports/validation_issues.csv` | Individual validation errors and warnings. |

These files are prepared for possible future retrieval and embedding work. Embeddings are not generated.

### Pipeline command

The normal entrypoint is:

```bash
python run_pipeline.py
```

After the command runs, the actual order is:

1. Document extraction through `run_extraction.py`.
2. Normalization through `pipeline/normalize.py`.
3. Validation through `pipeline/validate.py`.
4. Relationship generation through `pipeline/relationships.py`.
5. Chunk generation through `pipeline/chunking.py`.
6. JSON/JSONL export through `pipeline/export.py`.
7. Data-quality reporting through `pipeline/reports.py`.

## Extraction stage

`run_pipeline.py` calls `run_extraction.main` with `data/raw/` and `data/extracted/`. `run_extraction.py` reads the three PDFs, invokes the enabled extractors, and publishes primary CSVs and review/evidence files. Resource discovery is skipped because `RESOURCE_EXTRACTION_ENABLED` is false.

`data/manual/` is not read by this path. In particular, `data/manual/resources.csv` is not imported into the normal pipeline.

## Stage 1: Normalize

**File:** `pipeline/normalize.py`

The normalizer reads available entity CSVs from `data/extracted/`: courses, rules, skills, topics, course-skill links, prerequisites, programme plan, eligibility, and resources if a resource file exists. It does not read `data/manual/`.

It strips surrounding whitespace, collapses internal whitespace, and writes normalized copies to:

```text
data/processed/normalized/
```

Courses receive additional handling. Records are grouped by uppercased course code. When duplicate candidates exist, the code ranks field completeness and malformed titles. It removes duplicates only when one candidate is unambiguously better; it does not merge fields from multiple candidates.

Evidence CSVs are found both at expected paths and recursively under `data/extracted/`. Compatible records are deduplicated and written to `data/processed/normalized/source_evidence.csv`. Selected review files are copied when they are directly under `data/extracted/`.

## Stage 2: Validate

**File:** `pipeline/validate.py`

Validation checks:

- Required files and required columns.
- Empty required values.
- Duplicate course codes.
- Course-code format warnings.
- Numeric course credits and the allowed range.
- Prerequisite course and prerequisite-reference presence.
- Course-skill references to known courses and skill identifiers.
- Topic-course references.
- Programme-plan course-code format and descriptive requirement slots.
- Missing `source_url` and `source_type` values.
- Resource verification status when `resources.csv` exists.

Errors and warnings are both recorded. Missing required course fields, duplicate courses, unreadable CSVs, missing required schemas, and invalid credits can be errors. Many missing values and cross-entity references are warnings so that useful outputs can still be produced.

Prerequisite-cycle detection is **not implemented**. The validator checks whether references point to courses in the current collection, but it does not construct a graph and search for cycles. The latest report contains 0 errors and 6 warnings, all concerning prerequisite references outside the collected course set.

## Additional stage: Relationships

**File:** `pipeline/relationships.py`

This is not one of the assignment's five conceptual stages. It loads normalized courses, prerequisites, course skills, topics, programme-plan rows, and eligibility rows. For each course code it creates arrays for:

- prerequisites,
- skills,
- topics,
- programme-plan records, and
- eligibility records.

The result is written to:

```text
data/processed/relationships/course_relationships.json
```

The relationship object is also included in the exported `knowledge_base.json`.

## Stage 3: Chunk

**File:** `pipeline/chunking.py`

Chunking is record-based, not token-based or semantic-window splitting. It creates:

- one course chunk from available course fields;
- rule chunks;
- skill chunks;
- course-topic chunks;
- resource chunks if a normalized resource file exists;
- eligibility chunks; and
- programme-plan chunks.

Course text includes code, title, department, credits, contact hours, semesters, course type, mode, objectives, syllabus, and prerequisite information when populated. Other entity types use configured fields from their row.

Each chunk contains:

- `chunk_id`,
- `entity_type`,
- normalized `text`, and
- `metadata`.

Metadata includes fields such as `course_code`, `department`, `source_file`, `record_id`, and `source_url`. The function creates `data/processed/chunks/`, but the chunk records are returned in memory and exported to `output/chunks.jsonl`; no chunk file is written into `data/processed/chunks/`.

## Stage 4: Export

**File:** `pipeline/export.py`

The exporter loads available normalized entity CSVs, including an empty placeholder list for absent `resources.csv`, and builds a knowledge-base dictionary containing metadata, entities, relationships, and statistics.

It writes:

```text
output/knowledge_base.json
output/knowledge_base.jsonl
output/chunks.jsonl
```

The JSON file contains the complete entity and relationship structure. The knowledge-base JSONL contains one JSON object per entity record. The chunk JSONL contains one JSON object per generated chunk. No embedding vectors are generated.

## Stage 5: Reports

**File:** `pipeline/reports.py`

The reporting stage writes:

```text
reports/data_quality_report.md
reports/validation_issues.csv
```

The data-quality report measures entity row/column counts, merged evidence counts, duplicate removals, validation issue totals, final output paths, and chunk count. It also lists limitations and individual validation issues.

`run_extraction.py` writes `reports/extraction.log`. `run_pipeline.py` writes `reports/pipeline.log`. These logs show execution order, extractor status, output locations, and validation totals.

The reports do not calculate field-completeness percentages or prove semantic correctness. Source provenance and future-use ideas are documented separately in [`SOURCES.md`](../SOURCES.md) and [`IDEAS.md`](../IDEAS.md).

## Standalone validator

**File:** `validators/validate_extracted_data.py`

This is a separate utility and is not called by `run_pipeline.py`. It reads:

- `data/raw/Course_of_Study.pdf`
- `data/extracted/courses.csv`

It compares extracted course codes, titles, and academic values against PDF text and writes:

```text
reports/course_extraction_validation.csv
```

Run it separately:

```bash
python validators/validate_extracted_data.py
```

The validator does not modify the PDF or `courses.csv`. Its `REVIEW` results require manual inspection.
