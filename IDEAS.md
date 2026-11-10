# Knowledge Buddy: Future Use Cases and Roadmap

## 1. Purpose

The Adobe DSAI Knowledge Base prepares source-traced academic data for a future student-facing **Knowledge Buddy**. The current repository is a local extraction and processing pipeline; it is not yet a chatbot, recommendation engine, retrieval application, or embedding-based search system.

The knowledge base primarily covers the B.Tech Data Science and Artificial Intelligence (DSAI) programme at IIT Bhilai, with some available CSE-related course and prerequisite references. A future Knowledge Buddy should answer from structured records, preserve uncertainty, and show supporting source information rather than present every extracted value as official or complete.

## 2. Current data foundation

The latest data-quality report records the following entity counts:

| Entity | File or exported entity | Records | What it represents |
|---|---|---:|---|
| Courses | `data/extracted/courses.csv` / `entities.courses` | 25 | Course codes, titles, credits, syllabus, objectives, delivery fields, and provenance. |
| Topics | `data/extracted/course_topics.csv` / `entities.course_topics` | 185 | Topics derived from available syllabus text. |
| Skills | `data/extracted/skills.csv` / `entities.skills` | 28 | Curated skill taxonomy with category, level, and optional parent. |
| Course-skill links | `data/extracted/course_skills.csv` / `entities.course_skills` | 125 | Course-to-skill mappings with a `depth` field and provenance. |
| Prerequisites | `data/extracted/prerequisites.csv` / `entities.prerequisites` | 12 | `course` to `requires` prerequisite references. |
| Programme plan | `data/extracted/program_plan.csv` / `entities.program_plan` | 46 | Semester, course-code, and slot records. |
| Eligibility | `data/extracted/course_eligibility.csv` / `entities.course_eligibility` | 251 | Course/programme eligibility candidates and conditions. |
| Academic rules | `data/extracted/rules.csv` / `entities.rules` | 134 | Rule text, category, numeric limit, unit, and applicability candidates. |
| Source evidence | `entities.source_evidence` | 289 | Merged evidence records used to support provenance and review. |

The exported `output/knowledge_base.json` also contains relationship summaries for prerequisites, skills, topics, programme-plan records, and eligibility. These relationships connect records by course code or the relevant course/skill identifiers; they do not fill missing information or prove that a candidate record is institutionally authoritative.

## 3. Intended Knowledge Buddy

A useful future assistant would combine:

1. **Structured lookup** across course, topic, skill, prerequisite, programme-plan, eligibility, and rule entities.
2. **Relationship-aware explanations** that connect a course to its topics, skills, prerequisites, and programme context.
3. **Evidence-aware answers** that include `source_url`, `source_type`, `retrieved_on`, source files, or evidence records where available.
4. **Uncertainty handling** for incomplete fields, candidate rules, external prerequisite references, and unverified resources.

The current pipeline stops before embeddings and does not call an LLM or embedding API. Any future retrieval or conversational layer should be added only after the structured data has been sufficiently verified.

## 4. Three questions it could answer well

### 4.1 Building a DSAI foundation

**Example question:**  
> I want to build a strong DSAI foundation. Which available courses, skills, topics, and prerequisites should I explore first?

**Possible response:** The Knowledge Buddy could list available course records by code and title, summarize populated `objectives` and `syllabus` fields, group related `course_topics`, and show associated `course_skills` with their `skill` and `depth` values. It could also display prerequisite references from `prerequisites` and identify programme-plan semesters where the course appears.

**How the data connects:**

```text
courses.code
  ├── course_topics.course_code → topics
  ├── course_skills.course → skills.id/name
  ├── prerequisites.course → prerequisites.requires
  └── program_plan.course_code → semester/slot
```

**Evidence:** The answer can include each record's `source_url`, `source_type`, and `retrieved_on`, together with matching `source_evidence` where present.

**Limitations:** Course-topic and course-skill mappings are incomplete, syllabus/objective fields are not uniformly populated, and the prerequisite collection contains only 12 records. Some prerequisites point outside the extracted course set, so the assistant must label missing external records rather than infer a complete learning sequence.

### 4.2 Exploring Machine Learning skills

**Example question:**  
> Which available courses can help me explore Machine Learning, and what topics and skills are recorded for them?

**Possible response:** The Knowledge Buddy could search the controlled `skills` taxonomy and the `course_skills` mapping, then connect matching courses to `course_topics` and the relevant syllabus text in `courses`. It could compare the recorded skill category, level, depth, course credits, and prerequisite references without claiming that a course covers more than its extracted evidence shows.

**How the data connects:**

```text
skills.id/name/category/level
  ← course_skills.skill + depth
  ← course_skills.course → courses.code
  ← course_topics.course_code → topic/unit
```

**Evidence:** Course and mapping rows retain provenance fields such as `source_url`, `source_type`, and `retrieved_on`. The assistant could link the result to the original PDF filename or source evidence when a clickable URL is unavailable.

**Limitations:** The mappings are keyword-derived from available syllabus text and are not a complete skills assessment. The data cannot reliably rank course difficulty, teaching quality, practical depth, or career value.

### 4.3 Comparing programme electives

**Example question:**  
> Which programme elective options are recorded, what information is available for each, and what eligibility considerations should I check before choosing?

**Possible response:** The Knowledge Buddy could read `program_plan` rows by `semester` and `slot`, identify named `course_code` entries, and join them to `courses`, `course_topics`, `course_skills`, `prerequisites`, and `course_eligibility`. It could present recorded `eligibility_status` and `conditions` as candidates, then show the associated course credits, syllabus, topics, and skills.

**How the data connects:**

```text
program_plan.semester/slot/course_code
  → courses.code
  → course_topics.course_code
  → course_skills.course
  → prerequisites.course
  → course_eligibility.course_code
```

**Evidence:** Eligibility rows contain `source_url`, `source_type`, and `retrieved_on`; course records carry comparable provenance. Rule candidates in `rules.csv` can provide additional context when their `text`, `numeric_limit`, and `applies_to` fields have been manually verified.

**Limitations:** Eligibility and rule records are candidates requiring review. A programme slot may be descriptive rather than a named course, and the data does not include a student's branch, completed courses, grades, or current registration status. The assistant must not decide personal eligibility or recommend an objectively “best” elective.

## 5. Questions it cannot reliably answer yet

| Question area | Why the current knowledge base cannot answer reliably |
|---|---|
| Individual grades, CGPA, and academic history | The repository contains no student records, grades, attendance, registration history, or personal academic profile. |
| Live course offerings and timetable | Current semester offerings, timetable information, faculty availability, room assignments, and seat availability are not represented. |
| Course difficulty, teaching quality, or placement outcomes | No validated workload, instructor evaluation, placement, salary, or graduate-outcome data is included. |
| Guidance for another branch, such as Mechanical Engineering | The dataset is primarily DSAI and includes only some CSE-related information; it is not a complete cross-branch curriculum or bridge plan. |
| Comprehensive EE/ECE technical guidance | EE/ECE curricula, laboratory sequences, department requirements, and domain-specific outcomes are outside the current dataset. |
| Deterministic GATE preparation | GATE syllabi, exam patterns, preparation plans, and performance data are not represented; course topics alone cannot produce a guaranteed strategy. |
| MS-admission recommendations | University-specific prerequisites, deadlines, test scores, research profiles, funding, and changing admissions policies are absent. |
| Fully verified external-resource recommendations | `data/manual/resources.csv` has 192 manual records, but it is not consumed by `run_pipeline.py`; licence fields and topic mappings are empty, direct URLs are limited, and duration data is incomplete. Automatic resource discovery is disabled. |
| Official interpretation of every academic rule | The 134 rule rows are candidates and require manual verification against the source document. |
| A complete prerequisite graph | Some references point to courses outside the extracted dataset, and prerequisite-cycle detection is not implemented. |

These are different limitations: some require data that does not exist in the repository, while others require additional verification or pipeline capabilities. A future interface should state which case applies instead of silently producing a definitive answer.

## 6. What should be added next?

### 6.1 Immediate data-quality improvements

| Priority | Improvement | What it would enable |
|---:|---|---|
| 1 | Verify academic-rule candidates manually and preserve quotations, page references, and approval status. | More trustworthy answers about credit limits, minors, prerequisites, and related policies. |
| 2 | Expand and verify prerequisite relationships, including referenced external courses. | More complete prerequisite navigation and safer learning-path explanations. |
| 3 | Improve course-topic and course-skill coverage, including review of keyword-derived mappings. | More reliable topic and skill searches, especially for foundational and ML areas. |
| 4 | Add module-level syllabus extraction and review. | Finer-grained answers about units, objectives, and course coverage. |
| 5 | Verify source evidence and replace filename-only provenance with confirmed URLs where possible. | Auditable answers that a teammate can trace to the original source. |
| 6 | Curate external resources with verified licences, direct URLs, durations, formats, and course/skill mappings. | Responsible learning-resource discovery instead of unverified candidate listing. |

### 6.2 Broader data and product improvements

| Priority | Improvement | What it would enable |
|---:|---|---|
| 7 | Add verified programme datasets for other branches and cross-branch prerequisites. | More useful guidance for students transitioning from Mechanical Engineering, EE, ECE, or other programmes. |
| 8 | Add metadata filters for semester, department, course type, skill category, level, evidence status, and verification state. | Transparent filtering and comparison before conversational retrieval is introduced. |
| 9 | Build retrieval over the validated JSON/JSONL and chunk outputs. | Source-grounded search and answer composition using structured records and citations. |
| 10 | Add embeddings only after structured data quality, provenance, and evaluation are sufficient. | Semantic discovery across syllabus and rule text without replacing exact structured lookups. |

Embeddings and an LLM would be optional future product layers, not substitutes for source verification, complete relationships, or missing institutional data.

## 7. Reliability principles for a future implementation

- Separate extracted, derived, candidate, and manually verified records.
- Show the source file, page or quotation, URL, and retrieval date when available.
- Distinguish “not present in this dataset” from “not true.”
- Never infer personal eligibility, grades, or live institutional status.
- Do not describe the 192 manual resource records as automatically extracted or licence-verified.
- Keep personal student information outside this knowledge base.
