# Sources

This file records the source material represented in the Adobe DSAI Knowledge Base. It distinguishes official institute documents from manually collected resource candidates. A source URL is included only when it is recorded by the implementation or existing data.

## Official institute documents

| Source file | Information extracted | Pipeline role | Source type | Retrieval date | Source URL | Limitations |
|---|---|---|---|---|---|---|
| `data/raw/Course_of_Study.pdf` | DSAI course codes, titles, credits, contact hours, syllabus text, prerequisite text, and programme-plan course/semester candidates | Read by `extractors/course_of_study/extract_courses.py` and the active `extractors/program_structure/extract_semester_courses.py` | Official institute PDF | `2026-11-10` in extracted CSV rows | Not recorded as a clickable URL; rows use `Course_of_Study.pdf` | PDF layout can create duplicates, missing fields, or uncertain semester context. Review files must be checked against the PDF. |
| `data/raw/UG_Manual.pdf` | Academic-rule paragraph candidates, preliminary categories, quotations, page numbers, and evidence metadata | Read by `extractors/ug_manual/extract_rules.py` | Official institute PDF | `2026-11-10` in extracted CSV rows | `https://www.iitbhilai.ac.in/index.php?pid=ug_manual` | The extractor labels records as candidates. Numeric limits, eligibility meaning, and rule interpretation require human verification. |
| `data/raw/List_of_courses_V4.pdf` | Course catalogue table records, credits, discipline/programme fields, remarks, and eligibility candidates | Read by `extractors/course_catalogue/extract_course_catalogue.py` | Official institute PDF | `2026-11-10` in extracted CSV rows | Not recorded as a clickable URL; rows use `List_of_courses_V4.pdf` | Table parsing and DSAI eligibility interpretation can require manual review. |

### Related extractor modules

`extractors/program_structure/extract_program_plan.py` and `extractors/program_structure/extract_eligibility.py` are present in the repository, but the normal `run_extraction.py` configuration uses `extract_semester_courses.py` for programme-plan extraction and the catalogue extractor for eligibility output.

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

## Provenance limitations

The project records `source_url`, `retrieved_on`, and `source_type` columns in many extracted CSVs, but several PDF extractors pass the local PDF filename as `source_url`. This is provenance metadata, not a clickable web URL. Missing URLs and uncertain records should be resolved against the original institute source before publication or use in an assistant.
