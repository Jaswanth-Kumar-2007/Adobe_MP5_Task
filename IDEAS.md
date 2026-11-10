# Ideas for a future Knowledge Buddy

The current project prepares structured academic records, relationships, evidence, and record-based chunks. It does not implement a chatbot, recommendation engine, embeddings, or a student-facing assistant. The ideas below describe realistic future uses of the existing data, with explicit boundaries around what still needs verification.

## Questions the Knowledge Buddy Could Answer

The current data could support questions such as:

1. **“What is the title, department, and credit value of course DSL251?”**
   - Supported by normalized course fields in `data/processed/normalized/courses.csv`.
   - The assistant should cite the course record and source evidence where available.

2. **“Which courses have topics related to machine learning or information retrieval?”**
   - Partly supported by `course_topics.csv`, `course_skills.csv`, and `skills.csv`.
   - Topic and skill mappings are derived from syllabus text and keyword evidence, so the assistant should describe them as extracted mappings rather than complete curriculum truth.

3. **“What syllabus information is available for DSL504?”**
   - Supported when the course has syllabus text.
   - Missing or empty fields must be reported rather than inferred.

4. **“What prerequisites are recorded for this course?”**
   - Supported by prerequisite rows and course relationships.
   - External prerequisite references must be identified as outside the collected course set; the data does not prove that a prerequisite cycle is absent.

5. **“What courses appear in each programme-plan semester?”**
   - Supported by `program_plan.csv` and the generated course relationships.
   - Elective or requirement slots without a course code need to remain visibly different from named courses.

6. **“What eligibility information was extracted for this course?”**
   - Partly supported by `course_eligibility.csv`.
   - Eligibility records are candidates and may have `needs_review` status, so the assistant must not present them as current official policy without checking the source.

7. **“What academic rules mention credits, prerequisites, or minors?”**
   - Search is possible over the separate rule candidate rows and their evidence.
   - The assistant must quote the source context and state that rule candidates require human verification.

8. **“Which courses are connected to a given skill?”**
   - Supported by course-skill relationships for the 25 normalized courses and the current taxonomy.
   - The mapping is syllabus-derived and incomplete where syllabus fields are missing.

9. **“Where are the gaps in the current course-skill coverage?”**
   - A future analysis could compare available taxonomy skills with course-skill links.
   - This requires a clearly defined coverage method and must not be presented as a complete assessment of student competence or programme quality.

10. **“Are there learning resources for this topic?”**
    - Only after the manual resource candidates have verified licences, relevance, direct URLs, duration, and course/skill mappings.
    - The current `data/manual/resources.csv` is not integrated into the main pipeline and does not yet support reliable recommendations.

## Current data model that enables these ideas

The available outputs include:

- Course records with code, title, department, credits, syllabus, prerequisite text, and provenance fields.
- Separate prerequisite edges.
- Rule candidates with category, text, page/evidence information, and provenance.
- Semester-plan candidates and eligibility candidates.
- A controlled skill taxonomy, course topics, and course-skill links.
- Course relationship JSON connecting prerequisites, skills, topics, programme-plan records, and eligibility records.
- Record-based chunks in `output/chunks.jsonl` with entity types and source metadata.

## Questions It Cannot Reliably Answer Yet

The current data should not be used to answer these questions as authoritative facts:

- **“What is the official current credit limit, minor eligibility rule, or NPTEL/SWAYAM policy?”**
  - The rule extractor produces candidates and requires source verification.

- **“Does this prerequisite graph contain no cycles?”**
  - Prerequisite-cycle validation is not implemented.

- **“Is every course offered in a particular semester?”**
  - Semester extraction is document-layout dependent and includes review candidates and requirement slots.

- **“What are the complete objectives, mode, course type, or semester offerings for every course?”**
  - Several course fields are incomplete, including objective and syllabus information.

- **“Can I recommend this resource because it is openly licensed?”**
  - The manual resource file has 192 rows but no recorded licence fields and incomplete direct URLs and mappings.

- **“Which resource is the best match for this student's skill gap?”**
  - Resource-to-course/skill mappings and verification are incomplete, and no recommendation system exists.

- **“What are my grades, CGPA, attendance, registration status, or academic standing?”**
  - The project contains no student records, grades, or personal details.

- **“What is the institute's live current policy or course offering?”**
  - The dataset is based on stored source documents and does not provide live institute updates.

- **“Has this extracted record been officially approved?”**
  - Extraction success and zero structural validation errors do not establish semantic or institutional approval.

## Practical future work

Before using this data in a student-facing system, a future implementation should:

1. Verify rule, eligibility, programme-plan, and course records against original sources.
2. Replace filename-only provenance with verified source URLs where available.
3. Verify manual resource licences, direct links, duration, relevance, and mappings.
4. Add explicit resource and resource-skill integration only after verification.
5. Add prerequisite-cycle checks and field-completeness reporting.
6. Preserve citations and uncertainty labels in any future interface.
7. Keep personal student data out of this knowledge base.
