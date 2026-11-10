# Extraction documentation

## Extraction overview

Running `python run_pipeline.py` begins with the extraction stage. `run_pipeline.py` imports `run_extraction.main`, passes it `data/raw/` and `data/extracted/`, and stops if extraction returns a failure. The extraction stage then runs the enabled source-specific extractors and publishes their primary CSV files directly under `data/extracted/`; review and evidence CSVs are placed under `data/extracted/review/`.

The directories have different roles:

| Location | Role |
|---|---|
| `data/raw/` | Original institute PDFs. These are the source documents read by extractors. |
| `extractors/` | Python modules that parse specific PDFs or derive topics and skills. |
| `data/extracted/` | Primary CSV outputs produced by the enabled extraction run. |
| `data/extracted/review/` | Candidate, review, and source-evidence CSVs that support inspection. |
| `data/processed/normalized/` | Downstream normalized copies of available extracted entities. |
| `data/manual/` | Legacy manually curated CSVs. The current automated pipeline intentionally does not read this directory. |

Extraction success means that a script completed and wrote its expected files. It does not mean that every field is complete or semantically verified.

## Source-to-extractor mapping

### Course details

- **Input:** `data/raw/Course_of_Study.pdf`
- **Script:** `extractors/course_of_study/extract_courses.py`
- **Purpose:** Finds DSAI course headers, titles, credits, contact hours, syllabus text, prerequisite text, and provenance fields.
- **Primary outputs:** `data/extracted/courses.csv` and `data/extracted/prerequisites.csv`.
- **Review/evidence outputs:** `data/extracted/review/courses/extraction_review.csv` and `data/extracted/review/courses/source_evidence.csv`.
- **Limitations:** PDF layout can create duplicates or incomplete fields. The extractor filters by department-prefix mapping and does not independently verify programme classification. Some `source_url` values are PDF filenames.

### Academic rule candidates

- **Input:** `data/raw/UG_Manual.pdf`
- **Script:** `extractors/ug_manual/extract_rules.py`
- **Purpose:** Extracts paragraph candidates and assigns broad preliminary categories such as credits, prerequisites, electives, and programme options.
- **Primary output:** `data/extracted/rules.csv`.
- **Review/evidence outputs:** `data/extracted/review/rules/ug_manual_review.csv` and `data/extracted/review/rules/source_evidence.csv`.
- **Limitations:** The implementation explicitly treats these as candidates. Numeric limits and eligibility meanings are not automatically confirmed.

### Active programme-plan extraction

- **Input:** `data/raw/Course_of_Study.pdf`
- **Script used by `run_extraction.py`:** `extractors/program_structure/extract_semester_courses.py`
- **Purpose:** Finds course codes in semester context and creates semester-wise programme-plan records.
- **Primary output:** `data/extracted/program_plan.csv`.
- **Review/evidence outputs:** `data/extracted/review/program_plan/program_plan_review.csv` and `data/extracted/review/program_plan/program_plan_evidence.csv`.
- **Limitations:** A semester heading may be missed, elective slots may not have a course code, and table interpretation requires review.

`extractors/program_structure/extract_program_plan.py` is also present and writes the same programme-plan-style outputs when run directly, but it is not the module selected by the current `run_extraction.py` configuration.

### Course catalogue and eligibility

- **Input:** `data/raw/List_of_courses_V4.pdf`
- **Active script:** `extractors/course_catalogue/extract_course_catalogue.py`
- **Purpose:** Parses catalogue tables and produces catalogue records plus eligibility candidates.
- **Primary outputs:** `data/extracted/course_catalogue.csv` and `data/extracted/course_eligibility.csv`.
- **Review outputs:** `data/extracted/review/catalogue/course_catalogue_review.csv` and `data/extracted/review/catalogue/course_eligibility_review.csv`.
- **Limitations:** Table extraction and DSAI eligibility interpretation can require manual review. The active catalogue extractor, rather than the separate eligibility module, creates the eligibility CSV in the normal extraction run.

`extractors/program_structure/extract_eligibility.py` is present as a separate script that can parse eligibility-style lines from a supplied PDF, but `run_extraction.py` does not invoke it.

### Topics, skills, and course-skill relationships

- **Input:** Extracted `data/extracted/courses.csv` plus the controlled taxonomy embedded in `extractors/topics_skills/generate_topics_skills.py`.
- **Script:** `extractors/topics_skills/generate_topics_skills.py`
- **Purpose:** Derives topics only from available syllabus text and maps keyword evidence to taxonomy skills.
- **Primary outputs:** `data/extracted/course_topics.csv`, `data/extracted/skills.csv`, and `data/extracted/course_skills.csv`.
- **Review/evidence outputs:** No separate evidence file is generated by this module; the records retain source fields where available and remain candidates.
- **Limitations:** Courses without sufficient syllabus text receive incomplete or no topic/skill mappings. Skill depth is left for review.

## Resource extraction and manual resources

The automatic resource module is `extractors/resources/extract_resources.py`. `run_extraction.py` imports it but sets `RESOURCE_EXTRACTION_ENABLED = False`, so the normal run skips it. The extraction log records repeated DuckDuckGo request timeouts as the reason. No `resources.csv` is generated by the normal pipeline.

The legacy manual file `data/manual/resources.csv` is a separate dataset:

| Measure | Count |
|---|---:|
| Rows | 192 |
| Rows with `license_name` | 0 |
| Rows with `format` | 192 |
| Rows with `duration_value` | 8 |
| Rows with `duration_unit` | 8 |
| Rows with direct `url` | 7 |
| Rows with `topics` mapping | 0 |
| Rows with `catalogue_url` | 192 |

Its status values are `catalogue-listed` (175), `topic-seed-unverified` (10), and `provider-homepage-listed` (7). These labels are not licence verification. The file contains catalogue/provider metadata and notes that direct pages and licences still need verification.

Therefore the assignment requirement is:

**PARTIAL — Resource discovery is not automated. Resources are collected manually through `data/manual/resources.csv`; the final count and completeness of licence, format, duration and mappings must be verified.**

`pipeline/normalize.py` explicitly says `data/manual/` is not used, and `reports/data_quality_report.md` repeats that statement. Manual resources are not integrated into `run_pipeline.py`.

## Evidence and review workflow

Extractors preserve evidence where implemented: record identifiers, PDF page numbers, section headings, quotations, source metadata, and retrieval dates. The orchestrator publishes evidence and review files under `data/extracted/review/`. Normalization later discovers both classes recursively, merges compatible evidence into `data/processed/normalized/source_evidence.csv`, and copies review files while preserving their nested paths.

Review files contain uncertain or candidate records. A teammate should compare the candidate row, PDF page, quotation, and original source before treating it as authoritative. A successful extractor or a pipeline run with zero validation errors only establishes structural success; it does not establish semantic correctness.

## Extraction limitations

- Automatic resource discovery is disabled.
- Rule and eligibility rows are candidates requiring manual verification.
- Some course records have incomplete syllabus or objective information.
- Some provenance values are PDF filenames rather than clickable URLs.
- Programme-plan and catalogue table parsing can produce ambiguous records.
- Manual resources are not part of the automated pipeline.
