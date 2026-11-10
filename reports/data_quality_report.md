# DSAI Knowledge Base — Data Quality Report

- Generated: 2026-11-10T16:40:42+05:30
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

- No review files were generated.

## 3. Validation results

- Total validation issues: 6
- Errors: **0**
- Warnings: **6**

## 4. Final outputs

- Knowledge base JSON: `/home/jaswanthkumarkamireddi/Desktop/Inter_IIT/Adobe/output/knowledge_base.json`
- Knowledge base JSONL: `/home/jaswanthkumarkamireddi/Desktop/Inter_IIT/Adobe/output/knowledge_base.jsonl`
- Chunks JSONL: `/home/jaswanthkumarkamireddi/Desktop/Inter_IIT/Adobe/output/chunks.jsonl`
- Total chunks: 669

## 5. Limitations and verification

- Extraction completeness depends on the original document structure.
- Programme-plan candidates should be checked against official programme tables.
- Eligibility candidates require confirmation against official restrictions.
- Missing values are not automatically inferred.
- External prerequisite references may belong to other departments.
- Resource licence verification must be supported by evidence.

## 6. Validation issue details

- **WARN** | external_prerequisite | MAL403 | Prerequisite referenced by DSL253 is not in this course collection.
- **WARN** | external_prerequisite | CSL303 | Prerequisite referenced by DSL351 is not in this course collection.
- **WARN** | external_prerequisite | CSL303 | Prerequisite referenced by DSP352 is not in this course collection.
- **WARN** | external_prerequisite | CSL304 | Prerequisite referenced by DSL608 is not in this course collection.
- **WARN** | external_prerequisite | CS550 | Prerequisite referenced by DSL608 is not in this course collection.
- **WARN** | external_prerequisite | MAL403 | Prerequisite referenced by DSL608 is not in this course collection.