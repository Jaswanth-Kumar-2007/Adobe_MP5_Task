# Sources

This file records the source material represented in the Adobe DSAI Knowledge Base. It distinguishes official institute documents from manually collected resource candidates. A source URL is included only when it is recorded by the implementation or existing data.

## Official institute documents

| Source file | Information extracted | Pipeline role | Source type | Retrieval date | Source URL | Limitations |
|---|---|---|---|---|---|---|
| `data/raw/Course_of_Study.pdf` | DSAI course codes, titles, credits, contact hours, syllabus text, prerequisite text, and programme-plan course/semester candidates | Read by `extractors/course_of_study/extract_courses.py` and the active `extractors/program_structure/extract_semester_courses.py` | Official institute PDF | `2026-11-10` in extracted CSV rows | Not recorded as a clickable URL; rows use `Course_of_Study.pdf` | PDF layout can create duplicates, missing fields, or uncertain semester context. Review files must be checked against the PDF. |
| `data/raw/UG_Manual.pdf` | Academic-rule paragraph candidates, preliminary categories, quotations, page numbers, and evidence metadata | Read by `extractors/ug_manual/extract_rules.py` | Official institute PDF | `2026-11-10` in extracted CSV rows | `https://www.iitbhilai.ac.in/index.php?pid=ug_manual` | The extractor labels records as candidates. Numeric limits, eligibility meaning, and rule interpretation require human verification. |
| `data/raw/List_of_courses_V4.pdf` | Course catalogue table records, credits, discipline/programme fields, remarks, and eligibility candidates | Read by `extractors/course_catalogue/extract_course_catalogue.py` | Official institute PDF | `2026-11-10` in extracted CSV rows | Not recorded as a clickable URL; rows use `List_of_courses_V4.pdf` | Table parsing and DSAI eligibility interpretation can require manual review. |

## Extractor output details

| Component | Input | How it works | Generated outputs | Review/evidence outputs | Verification notes |
|---|---|---|---|---|---|
| Course extraction | `data/raw/Course_of_Study.pdf` | Reads PDF pages, identifies course headers and parses credits, hours, syllabus, objectives, and prerequisite text. | `data/extracted/courses.csv`; `data/extracted/prerequisites.csv` | `data/extracted/review/courses/extraction_review.csv`; `data/extracted/review/courses/source_evidence.csv` | PDF layout can create duplicates or incomplete fields. |
| UG Manual rules | `data/raw/UG_Manual.pdf` | Groups candidate paragraphs by section, assigns preliminary categories, and preserves quotations and page numbers. | `data/extracted/rules.csv` | `data/extracted/review/rules/ug_manual_review.csv`; `data/extracted/review/rules/source_evidence.csv` | Candidates are not automatically verified policies. |
| Active programme structure | `data/raw/Course_of_Study.pdf` | Tracks semester headings and course-code matches to create semester-plan rows. | `data/extracted/program_plan.csv` | `data/extracted/review/program_plan/program_plan_review.csv`; `data/extracted/review/program_plan/program_plan_evidence.csv` | The active module is `extract_semester_courses.py`; table and elective slots require review. |
| Catalogue and eligibility | `data/raw/List_of_courses_V4.pdf` | Extracts catalogue tables, then creates eligibility candidates from catalogue fields and remarks. | `data/extracted/course_catalogue.csv`; `data/extracted/course_eligibility.csv` | `data/extracted/review/catalogue/course_catalogue_review.csv`; `data/extracted/review/catalogue/course_eligibility_review.csv` | Eligibility records may have `needs_review` status. |
| Topics and skills | `data/extracted/courses.csv` plus the embedded taxonomy | Reads syllabus text, derives topics, and applies keyword evidence to the curated skill taxonomy. | `data/extracted/course_topics.csv`; `data/extracted/skills.csv`; `data/extracted/course_skills.csv` | No separate review/evidence file from this module | This is derived processing, not independent PDF extraction. |
| Automatic resources | Extracted topics and skills when enabled | Searches for candidate learning resources and collects webpage metadata. | No output in the current run; intended candidate path is `resources_web_candidates.csv` under the extraction review area. | Resource error reporting is only relevant when the extractor runs. | Disabled in `run_extraction.py` because of recorded DuckDuckGo timeouts. |

`extractors/program_structure/extract_program_plan.py` and `extractors/program_structure/extract_eligibility.py` exist, but the normal orchestrator uses `extract_semester_courses.py` and the catalogue extractor respectively. The catalogue extractor is the component that actually creates the current `course_catalogue.csv` and `course_eligibility.csv`.

`extractors/topics_skills/generate_topics_skills.py` does not read an original PDF directly. It derives topics from extracted course syllabus text and maps keyword evidence to its embedded curated skill taxonomy.

## Manual resource dataset

### `data/manual/resources.csv`

This file contains manually collected resource candidates and is not consumed by `run_pipeline.py`. It is not an automatic extractor output and must not be treated as a verified open-licensed resource catalogue.

Current observed metadata:

- Records: **192**
- `format` present: **192**
- `duration_value` present: **8**
- `duration_unit` present: **8**
- Direct `url` present: **7**
- `catalogue_url` present: **192**
- `license_name` present: **0**
- `license_url` present: **0**
- `topics` mapping present: **0**
- Retrieval date: **Not recorded**
- Verification statuses: `catalogue-listed`, `topic-seed-unverified`, and `provider-homepage-listed`

The rows contain catalogue/provider metadata and notes, but licence information, direct resource links, topic mappings, and duration metadata are incomplete. These entries require verification for licence, relevance, course/skill mapping, format, duration, and accessibility before they can support the assignment's open-resource requirement.

## Evidence and review locations

The extractors write evidence and review files under `data/extracted/review/`, including:

- Course evidence and extraction review files.
- UG Manual evidence and rule review files.
- Programme-plan evidence and review files.
- Catalogue and eligibility review files.

The downstream normalizer merges compatible evidence into `data/processed/normalized/source_evidence.csv`. Review records remain candidates for manual inspection.

## Output inventory

| Output | Location | Role |
|---|---|---|
| Course records | `data/extracted/courses.csv` | Extracted course candidates. |
| Prerequisite edges | `data/extracted/prerequisites.csv` | Extracted prerequisite relationships. |
| Academic rules | `data/extracted/rules.csv` | Candidate rule paragraphs. |
| Programme plan | `data/extracted/program_plan.csv` | Semester/course and requirement candidates. |
| Catalogue | `data/extracted/course_catalogue.csv` | Catalogue table records. |
| Eligibility | `data/extracted/course_eligibility.csv` | Eligibility candidates. |
| Topics | `data/extracted/course_topics.csv` | Syllabus-derived topics. |
| Skills | `data/extracted/skills.csv` | Curated skill taxonomy. |
| Course-skill links | `data/extracted/course_skills.csv` | Syllabus-derived course-skill mappings. |
| Merged evidence | `data/processed/normalized/source_evidence.csv` | Compatible evidence rows merged during normalization. |
| Normalized entities | `data/processed/normalized/` | Downstream cleaned CSV copies and review copies. |
| Relationships | `data/processed/relationships/course_relationships.json` | Generated course-linked relationship structure. |
| Knowledge base | `output/knowledge_base.json` | Nested entities, relationships, and statistics. |
| Entity JSONL | `output/knowledge_base.jsonl` | One JSON record per exported entity row. |
| Chunks | `output/chunks.jsonl` | Record-based chunks with source metadata. |
| Quality report | `reports/data_quality_report.md` | Counts, warnings, limitations, and output paths. |
| Validation issues | `reports/validation_issues.csv` | Individual validation issues. |

## Provenance limitations

The project records `source_url`, `retrieved_on`, and `source_type` columns in many extracted CSVs, but several PDF extractors pass the local PDF filename as `source_url`. This is provenance metadata, not a clickable web URL. Missing URLs and uncertain records should be resolved against the original institute source before publication or use in an assistant.
