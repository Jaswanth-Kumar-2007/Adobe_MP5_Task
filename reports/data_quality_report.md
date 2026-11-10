# DSAI Knowledge Base — Data Quality Report

- Generated: 2026-11-10T19:46:46+05:30
- Input directory: `data/extracted/`
- Original documents are handled by the extraction stage.
- `data/manual/` is not used by this processing pipeline.

## 1. Entity statistics

| Entity file | Records | Columns |
|---|---:|---:|
| `courses.csv` | 25 | 16 |
| `rules.csv` | 134 | 9 |
| `skills.csv` | 28 | 8 |
| `course_topics.csv` | 185 | 6 |
| `course_skills.csv` | 125 | 6 |
| `prerequisites.csv` | 12 | 7 |
| `program_plan.csv` | 46 | 6 |
| `course_eligibility.csv` | 251 | 7 |

- Merged evidence records: 289
- Evidence files merged: 3
- Course duplicates removed during normalization: 12

## 2. Extractor review files

- `review/catalogue/course_catalogue_review.csv`: 36 records
- `review/catalogue/course_eligibility_review.csv`: 0 records
- `review/courses/extraction_review.csv`: 14 records
- `review/program_plan/program_plan_review.csv`: 7 records
- `review/rules/ug_manual_review.csv`: 134 records

### Source-evidence files

- `review/courses/source_evidence.csv`: 109 records
- `review/program_plan/program_plan_evidence.csv`: 46 records
- `review/rules/source_evidence.csv`: 134 records

## 3. Field completeness

Percentages are calculated only for fields defined in each entity schema; they measure populated values, not semantic correctness.

### `courses.csv`

| Field | Total | Populated | Missing | Completeness |
|---|---:|---:|---:|---:|
| `code` | 25 | 25 | 0 | 100.0% |
| `title` | 25 | 25 | 0 | 100.0% |
| `credits` | 25 | 23 | 2 | 92.0% |
| `semesters` | 25 | 0 | 25 | 0.0% |
| `course_type` | 25 | 0 | 25 | 0.0% |
| `mode` | 25 | 0 | 25 | 0.0% |
| `objectives` | 25 | 0 | 25 | 0.0% |
| `syllabus` | 25 | 24 | 1 | 96.0% |
| `prereq_text` | 25 | 24 | 1 | 96.0% |
| `source_url` | 25 | 25 | 0 | 100.0% |

### `rules.csv`

| Field | Total | Populated | Missing | Completeness |
|---|---:|---:|---:|---:|
| `id` | 134 | 134 | 0 | 100.0% |
| `category` | 134 | 134 | 0 | 100.0% |
| `text` | 134 | 134 | 0 | 100.0% |
| `source_url` | 134 | 134 | 0 | 100.0% |
| `source_type` | 134 | 134 | 0 | 100.0% |

### `skills.csv`

| Field | Total | Populated | Missing | Completeness |
|---|---:|---:|---:|---:|
| `id` | 28 | 28 | 0 | 100.0% |
| `name` | 28 | 28 | 0 | 100.0% |
| `category` | 28 | 28 | 0 | 100.0% |
| `level` | 28 | 0 | 28 | 0.0% |
| `parent` | 28 | 0 | 28 | 0.0% |
| `source_url` | 28 | 0 | 28 | 0.0% |

### `course_topics.csv`

| Field | Total | Populated | Missing | Completeness |
|---|---:|---:|---:|---:|
| `course_code` | 185 | 185 | 0 | 100.0% |
| `topic` | 185 | 185 | 0 | 100.0% |
| `unit` | 185 | 185 | 0 | 100.0% |
| `source_url` | 185 | 185 | 0 | 100.0% |

### `course_skills.csv`

| Field | Total | Populated | Missing | Completeness |
|---|---:|---:|---:|---:|
| `course` | 125 | 125 | 0 | 100.0% |
| `skill` | 125 | 125 | 0 | 100.0% |
| `depth` | 125 | 0 | 125 | 0.0% |
| `source_url` | 125 | 125 | 0 | 100.0% |

### `prerequisites.csv`

| Field | Total | Populated | Missing | Completeness |
|---|---:|---:|---:|---:|
| `course` | 12 | 12 | 0 | 100.0% |
| `requires` | 12 | 12 | 0 | 100.0% |
| `kind` | 12 | 12 | 0 | 100.0% |
| `group` | 12 | 12 | 0 | 100.0% |
| `source_url` | 12 | 12 | 0 | 100.0% |

### `program_plan.csv`

| Field | Total | Populated | Missing | Completeness |
|---|---:|---:|---:|---:|
| `semester` | 46 | 46 | 0 | 100.0% |
| `course_code` | 46 | 36 | 10 | 78.3% |
| `slot` | 46 | 46 | 0 | 100.0% |
| `source_url` | 46 | 46 | 0 | 100.0% |

### `course_eligibility.csv`

| Field | Total | Populated | Missing | Completeness |
|---|---:|---:|---:|---:|
| `course_code` | 251 | 251 | 0 | 100.0% |
| `programme` | 251 | 251 | 0 | 100.0% |
| `eligibility_status` | 251 | 251 | 0 | 100.0% |
| `conditions` | 251 | 251 | 0 | 100.0% |
| `source_url` | 251 | 251 | 0 | 100.0% |

## 4. Validation results

- Total validation issues: 6
- Errors: **0**
- Warnings: **6**

External prerequisite references remain warnings when a prerequisite is outside the extracted course collection.

## 5. Final outputs

- Knowledge base JSON: `/home/jaswanthkumarkamireddi/Desktop/Inter_IIT/Adobe/output/knowledge_base.json`
- Knowledge base JSONL: `/home/jaswanthkumarkamireddi/Desktop/Inter_IIT/Adobe/output/knowledge_base.jsonl`
- Chunks JSONL: `/home/jaswanthkumarkamireddi/Desktop/Inter_IIT/Adobe/output/chunks.jsonl`
- Total chunks: 669

## 6. Limitations and manual verification

- Extraction completeness depends on the original document structure.
- Programme-plan candidates should be checked against official programme tables.
- Eligibility candidates require confirmation against official restrictions.
- Missing values are not automatically inferred.
- External prerequisite references may belong to other departments.
- A populated `source_url` may be a local source filename rather than a clickable web URL when no verified URL is recorded.
- Resource licence verification must be supported by evidence.

For a practical sample check, select representative rows from `courses.csv`, `rules.csv`, `program_plan.csv`, and `course_eligibility.csv`; compare each row with its cited PDF page and quotation in the review/evidence CSVs. Repeat for topic, skill, and prerequisite mappings, and record any discrepancy for manual review.

Structural validation and populated-field percentages do not prove semantic correctness.

## 7. Manual resource audit

- Records: **192**
- Licence names populated: **0**
- Direct URLs populated: **7**
- Topic mappings populated: **0**
- Complete duration value/unit pairs: **8**
- This manually collected dataset is not consumed by `run_pipeline.py`.
- Automatic resource discovery is disabled; these records remain unverified candidates.

## 8. Validation issue details

- **WARN** | external_prerequisite | MAL403 | Prerequisite referenced by DSL253 is not in this course collection.
- **WARN** | external_prerequisite | CSL303 | Prerequisite referenced by DSL351 is not in this course collection.
- **WARN** | external_prerequisite | CSL303 | Prerequisite referenced by DSP352 is not in this course collection.
- **WARN** | external_prerequisite | CSL304 | Prerequisite referenced by DSL608 is not in this course collection.
- **WARN** | external_prerequisite | CS550 | Prerequisite referenced by DSL608 is not in this course collection.
- **WARN** | external_prerequisite | MAL403 | Prerequisite referenced by DSL608 is not in this course collection.