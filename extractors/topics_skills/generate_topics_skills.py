#!/usr/bin/env python3

"""
Generate:
    course_topics.csv
    skills.csv
    course_skills.csv

Input:
    data/extracted/courses.csv

Important rules:
1. Topics are extracted ONLY from the syllabus column.
2. prereq_text is never used as a fallback for syllabus.
3. Prerequisite and overlap metadata accidentally present at the
   beginning of syllabus text is removed.
4. Empty, duplicate, and obviously invalid topic candidates are skipped.
5. Skills are mapped using keyword evidence from extracted topics.
6. Skill depth is left blank for human review.
7. All outputs are candidates and require validation before final use.
"""

import argparse
import csv
import re

from collections import defaultdict
from datetime import date
from pathlib import Path


# =========================================================
# PATHS AND CONFIGURATION
# =========================================================

DEFAULT_INPUT = Path("data/extracted/courses.csv")
DEFAULT_OUTPUT_DIR = Path("data/extracted")

TODAY = date.today().isoformat()


# =========================================================
# CSV SCHEMAS
# =========================================================

TOPIC_COLUMNS = [
    "course_code",
    "topic",
    "unit",
    "source_url",
    "retrieved_on",
    "source_type",
]

SKILL_COLUMNS = [
    "id",
    "name",
    "category",
    "level",
    "parent",
    "source_url",
    "retrieved_on",
    "source_type",
]

COURSE_SKILL_COLUMNS = [
    "course",
    "skill",
    "depth",
    "source_url",
    "retrieved_on",
    "source_type",
]


# =========================================================
# CONTROLLED SKILL TAXONOMY
# =========================================================

# Each entry contains:
# Skill ID, Skill Name, Category, Keyword Patterns

SKILL_TAXONOMY = [

    (
        "SK001",
        "Python Programming",
        "Programming",
        [
            r"\bpython\b",
        ],
    ),

    (
        "SK002",
        "C++ Programming",
        "Programming",
        [
            r"\bc\+\+(?!\w)",
        ],
    ),

    (
        "SK003",
        "Data Structures",
        "Computer Science",
        [
            r"\bdata structures?\b",
            r"\blinked lists?\b",
            r"\bstacks?\b",
            r"\bqueues?\b",
            r"\btrees?\b",
            r"\bgraphs?\b",
        ],
    ),

    (
        "SK004",
        "Algorithms",
        "Computer Science",
        [
            r"\balgorithms?\b",
            r"\bsorting\b",
            r"\bsearching\b",
            r"\boptimization\b",
        ],
    ),

    (
        "SK005",
        "Database Management",
        "Data Engineering",
        [
            r"\bsql\b",
            r"\bdatabases?\b",
            r"\bmongodb\b",
            r"\bcassandra\b",
            r"\bnosql\b",
        ],
    ),

    (
        "SK006",
        "Big Data Processing",
        "Data Engineering",
        [
            r"\bbig data\b",
            r"\bmapreduce\b",
            r"\bhadoop\b",
            r"\bspark\b",
            r"\bdistributed computing\b",
        ],
    ),

    (
        "SK007",
        "Data Analytics",
        "Data Science",
        [
            r"\bdata analytics\b",
            r"\bexploratory data analysis\b",
            r"\bdata analysis\b",
        ],
    ),

    (
        "SK008",
        "Data Visualization",
        "Data Science",
        [
            r"\bvisualization\b",
            r"\bvisualisation\b",
            r"\bmatplotlib\b",
            r"\bseaborn\b",
            r"\bplotly\b",
        ],
    ),

    (
        "SK009",
        "Statistical Analysis",
        "Mathematics and Statistics",
        [
            r"\bstatistics?\b",
            r"\bstatistical\b",
            r"\bprobability\b",
            r"\bbayes\b",
            r"\bsampling\b",
        ],
    ),

    (
        "SK010",
        "Linear Algebra",
        "Mathematics and Statistics",
        [
            r"\blinear algebra\b",
            r"\bmatrices\b",
            r"\bmatrix\b",
            r"\beigenvalues?\b",
            r"\beigenvectors?\b",
            r"\bsvd\b",
        ],
    ),

    (
        "SK011",
        "Machine Learning",
        "Artificial Intelligence",
        [
            r"\bmachine learning\b",
            r"\bsupervised learning\b",
            r"\bunsupervised learning\b",
            r"\bclassification\b",
            r"\bregression\b",
            r"\bclustering\b",
        ],
    ),

    (
        "SK012",
        "Deep Learning",
        "Artificial Intelligence",
        [
            r"\bdeep learning\b",
            r"\bneural networks?\b",
            r"\bmultilayer perceptrons?\b",
            r"\bbackpropagation\b",
        ],
    ),

    (
        "SK013",
        "Computer Vision",
        "Artificial Intelligence",
        [
            r"\bcomputer vision\b",
            r"\bimage processing\b",
            r"\bimage classification\b",
            r"\bobject detection\b",
            r"\bcnn\b",
            r"\bconvolutional neural networks?\b",
            r"\bsegmentation\b",
        ],
    ),

    (
        "SK014",
        "Natural Language Processing",
        "Artificial Intelligence",
        [
            r"\bnatural language processing\b",
            r"\bnlp\b",
            r"\btokenization\b",
            r"\bstemming\b",
            r"\bword vectors?\b",
            r"\bbert\b",
            r"\bgpt\b",
            r"\blanguage modelling\b",
            r"\blanguage modeling\b",
        ],
    ),

    (
        "SK015",
        "Reinforcement Learning",
        "Artificial Intelligence",
        [
            r"\breinforcement learning\b",
            r"\bq-learning\b",
            r"\bmarkov decision\b",
            r"\bpolicy search\b",
        ],
    ),

    (
        "SK016",
        "Information Retrieval",
        "Artificial Intelligence",
        [
            r"\binformation retrieval\b",
            r"\bbm25\b",
            r"\bpagerank\b",
            r"\bdocument indexing\b",
            r"\bsearch engines?\b",
        ],
    ),

    (
        "SK017",
        "Time Series Analysis",
        "Data Science",
        [
            r"\btime[\s-]series\b",
            r"\barima\b",
            r"\barma\b",
            r"\banomaly detection\b",
        ],
    ),

    (
        "SK018",
        "Graph Analytics",
        "Data Science",
        [
            r"\bgraph analysis\b",
            r"\bnetwork analysis\b",
            r"\bnetwork science\b",
            r"\bnetworkx\b",
            r"\bgraph neural networks?\b",
            r"\bknowledge graphs?\b",
        ],
    ),

    (
        "SK019",
        "Information Security",
        "Computer Science",
        [
            r"\binformation security\b",
            r"\bcybersecurity\b",
            r"\bdata privacy\b",
            r"\bprivacy\b",
        ],
    ),

    (
        "SK020",
        "Web Scraping and Data Collection",
        "Data Engineering",
        [
            r"\bweb scraping\b",
            r"\bdata scraping\b",
            r"\bweb crawling\b",
            r"\bcrawling\b",
            r"\bbeautiful soup\b",
            r"\bapis?\b",
        ],
    ),

    (
        "SK021",
        "Data Preprocessing",
        "Data Science",
        [
            r"\bdata preprocessing\b",
            r"\bdata wrangling\b",
            r"\bdata cleaning\b",
            r"\bdata handling\b",
        ],
    ),

    (
        "SK022",
        "Dimensionality Reduction",
        "Data Science",
        [
            r"\bdimensionality reduction\b",
            r"\bpca\b",
            r"\bt-sne\b",
            r"\bprincipal component analysis\b",
        ],
    ),

    (
        "SK023",
        "Speech Processing",
        "Artificial Intelligence",
        [
            r"\bspeech processing\b",
            r"\bspeech recognition\b",
            r"\bspeech synthesis\b",
            r"\bacoustic phonetics\b",
        ],
    ),

    (
        "SK024",
        "Software Development",
        "Software Engineering",
        [
            r"\bsoftware development\b",
            r"\bsoftware management\b",
            r"\bobject oriented\b",
            r"\bobject-oriented\b",
            r"\bdebugging\b",
            r"\bversion control\b",
            r"\bgit\b",
        ],
    ),

    (
        "SK025",
        "Edge Computing and IoT",
        "Computer Science",
        [
            r"\bedge computing\b",
            r"\binternet of things\b",
            r"\biot\b",
            r"\bedge applications?\b",
        ],
    ),

    (
        "SK026",
        "Optimization",
        "Mathematics and Statistics",
        [
            r"\boptimization\b",
            r"\bgradient descent\b",
            r"\bregularization\b",
        ],
    ),

    (
        "SK027",
        "Generative AI",
        "Artificial Intelligence",
        [
            r"\bgenerative models?\b",
            r"\bdiffusion models?\b",
            r"\bgan\b",
            r"\bvariational autoencoders?\b",
            r"\bllms?\b",
            r"\blarge language models?\b",
        ],
    ),

    (
        "SK028",
        "Data Mining",
        "Data Science",
        [
            r"\bdata mining\b",
            r"\bpattern mining\b",
            r"\bfrequent itemsets?\b",
        ],
    ),

]


# =========================================================
# TEXT UTILITIES
# =========================================================

def clean_text(value):
    """
    Normalize whitespace without changing the meaning of text.
    """

    value = str(value or "")

    value = value.replace("\u00a0", " ")
    value = value.replace("\u200b", "")

    value = re.sub(r"[ \t]+", " ", value)

    return value.strip()


def normalize_for_matching(text):
    """
    Normalize text for case-insensitive keyword matching.
    """

    return clean_text(text).casefold()


def is_invalid_topic(topic):
    """
    Reject obvious extraction noise.

    This does not attempt to judge whether a topic is academically
    important. Human review is still required.
    """

    topic = clean_text(topic)

    if len(topic) < 3:
        return True

    if topic.casefold() in {
        "none",
        "null",
        "nan",
        "na",
        "n/a",
        "not applicable",
        "nil",
        "unknown",
        "syllabus",
        "prerequisite",
        "prerequisites",
        "overlap with",
    }:
        return True

    # Reject course codes such as DSL201 or MAL100.
    if re.fullmatch(
        r"[A-Z]{2,5}\s*-?\s*\d{3,4}",
        topic,
        flags=re.IGNORECASE,
    ):
        return True

    # Reject metadata statements.
    if re.match(
        r"(?i)^(prerequisite|prerequisites|overlap with)\s*[:(]",
        topic,
    ):
        return True

    return False


# =========================================================
# CSV UTILITIES
# =========================================================

def read_courses(input_file):
    """
    Read the extracted courses CSV.

    The input must contain at least:
        code
        syllabus
    """

    if not input_file.exists():
        raise FileNotFoundError(
            f"Could not find extracted courses file: {input_file}"
        )

    with open(
        input_file,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        required_columns = {
            "code",
            "syllabus",
        }

        available_columns = set(reader.fieldnames or [])

        missing_columns = required_columns - available_columns

        if missing_columns:
            raise ValueError(
                "courses.csv is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        return list(reader)


def write_csv(path, columns, rows):
    """
    Write a CSV using the required schema.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


# =========================================================
# SYLLABUS CLEANING
# =========================================================

def remove_leading_metadata(text):
    """
    Remove prerequisite and overlap metadata if it has accidentally
    appeared at the beginning of the syllabus field.

    Importantly, this function does NOT read prereq_text.

    Examples handled:

        Prerequisite(s): None
        Overlap with: NA
        Introduction to probability...

    It also handles metadata appearing on the same line.
    """

    if not text:
        return ""

    text = str(text).replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")

    cleaned_lines = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # Handle metadata placed before actual syllabus content
        # on the same line.
        line = re.sub(
            r"(?is)^.*?Overlap with:\s*(?:NA|N/A|None)?\s*",
            "",
            line,
            count=1,
        )

        # Remove prerequisite-only lines.
        if re.match(
            r"(?i)^\s*prerequisite(?:s)?(?:\s*\([^)]*\))?\s*:",
            line,
        ):
            continue

        # Remove overlap-only lines.
        if re.match(
            r"(?i)^\s*overlap with\s*:",
            line,
        ):
            continue

        line = clean_text(line)

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def get_syllabus_text(course):
    """
    Return syllabus content only.

    Never fall back to prereq_text.

    An empty syllabus must remain empty instead of being replaced
    with prerequisite information.
    """

    syllabus = course.get("syllabus", "")

    syllabus = str(syllabus or "").strip()

    if not syllabus:
        return ""

    return remove_leading_metadata(syllabus)


# =========================================================
# TOPIC EXTRACTION
# =========================================================

def split_syllabus_segments(text):
    """
    Split syllabus content into manageable candidate segments.

    Supported separators:
        - New lines
        - Semicolons
        - Bullet points
        - Numbered list markers

    Commas are deliberately NOT used as a general separator.
    A comma may be part of a meaningful topic or explanation.
    """

    if not text:
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    segments = []

    for line in text.split("\n"):

        line = clean_text(line)

        if not line:
            continue

        # Remove bullet markers.
        line = re.sub(
            r"^\s*(?:[-*•▪◦]+)\s*",
            "",
            line,
        )

        # Remove numbered list markers such as:
        # 1. Topic
        # 2) Topic
        line = re.sub(
            r"^\s*\d+[\.)]\s*",
            "",
            line,
        )

        # Split semicolon-separated syllabus items.
        parts = re.split(
            r"\s*;\s*",
            line,
        )

        for part in parts:

            part = clean_text(part)

            if part:
                segments.append(part)

    return segments


def process_topic_segment(segment):
    """
    Process one syllabus segment.

    If a segment contains a heading followed by a colon,
    separate a meaningful heading from its description.

    Generic introductory headings are not emitted as standalone topics.
    """

    segment = clean_text(segment)

    if not segment:
        return []

    results = []

    if ":" in segment:

        heading, remainder = segment.split(":", 1)

        heading = clean_text(heading)
        remainder = clean_text(remainder)

        generic_headings = {
            "introduction",
            "overview",
            "introduction and overview",
            "introduction and brief overview",
            "course objectives",
            "objectives",
            "syllabus",
            "course outline",
        }

        # Preserve meaningful headings.
        if heading and heading.casefold() not in generic_headings:

            if not is_invalid_topic(heading):
                results.append(heading)

        if remainder:
            results.append(remainder)

    else:
        results.append(segment)

    return results


def split_topics(text):
    """
    Convert syllabus text into cleaned topic candidates.

    The function:
        1. Removes leading metadata.
        2. Splits into syllabus segments.
        3. Processes headings.
        4. Removes obvious invalid records.
        5. Deduplicates while preserving order.
    """

    text = remove_leading_metadata(text)

    if not text:
        return []

    segments = split_syllabus_segments(text)

    topics = []

    for segment in segments:

        candidates = process_topic_segment(segment)

        for candidate in candidates:

            candidate = clean_text(candidate)

            if is_invalid_topic(candidate):
                continue

            topics.append(candidate)

    # Deduplicate while preserving original order.
    unique_topics = []
    seen = set()

    for topic in topics:

        key = topic.casefold()

        if key in seen:
            continue

        seen.add(key)
        unique_topics.append(topic)

    return unique_topics


# =========================================================
# GENERATE COURSE TOPICS
# =========================================================

def generate_course_topics(courses):
    """
    Generate course_topics.csv records.

    Topic records are created only when syllabus content exists.
    """

    rows = []

    missing_syllabus = []
    courses_without_topics = []

    for course in courses:

        code = clean_text(course.get("code"))

        if not code:
            continue

        syllabus = get_syllabus_text(course)

        if not syllabus:
            missing_syllabus.append(code)
            continue

        topics = split_topics(syllabus)

        if not topics:
            courses_without_topics.append(code)
            continue

        source_url = clean_text(
            course.get("source_url")
        )

        retrieved_on = (
            clean_text(course.get("retrieved_on"))
            or TODAY
        )

        source_type = clean_text(
            course.get("source_type")
        )

        for index, topic in enumerate(topics, start=1):

            rows.append({

                "course_code": code,

                "topic": topic,

                "unit": f"Topic {index}",

                "source_url": source_url,

                "retrieved_on": retrieved_on,

                "source_type": source_type,

            })

    statistics = {
        "missing_syllabus": missing_syllabus,
        "courses_without_topics": courses_without_topics,
    }

    return rows, statistics


# =========================================================
# GENERATE SKILLS
# =========================================================

def generate_skill_taxonomy():
    """
    Generate the controlled skills taxonomy.

    Skill levels and parent relationships are left blank because
    they require explicit academic validation.
    """

    rows = []

    for skill_id, name, category, patterns in SKILL_TAXONOMY:

        rows.append({

            "id": skill_id,

            "name": name,

            "category": category,

            "level": "",

            "parent": "",

            "source_url": "",

            "retrieved_on": TODAY,

            "source_type": "curated_taxonomy",

        })

    return rows


# =========================================================
# GENERATE COURSE-SKILL MAPPINGS
# =========================================================

def generate_course_skills(topic_rows):
    """
    Map extracted topics to the controlled skill taxonomy.

    A mapping is created only when at least one keyword pattern
    matches an extracted syllabus topic.

    Depth is intentionally left blank for human review.
    """

    # Store evidence for each course-skill pair.
    course_skill_evidence = defaultdict(list)

    # Store source information for each course.
    course_sources = {}

    for topic_row in topic_rows:

        course_code = topic_row["course_code"]

        topic = topic_row["topic"]

        topic_lower = normalize_for_matching(topic)

        course_sources.setdefault(
            course_code,
            topic_row,
        )

        for skill_id, name, category, patterns in SKILL_TAXONOMY:

            matched = any(
                re.search(pattern, topic_lower)
                for pattern in patterns
            )

            if matched:

                key = (course_code, skill_id)

                course_skill_evidence[key].append(topic)

    course_skill_rows = []

    for (course_code, skill_id), evidence_topics in sorted(
        course_skill_evidence.items()
    ):

        source_row = course_sources.get(course_code, {})

        course_skill_rows.append({

            "course": course_code,

            "skill": skill_id,

            # Human review is required to determine depth.
            "depth": "",

            "source_url": source_row.get("source_url", ""),

            "retrieved_on": source_row.get(
                "retrieved_on",
                TODAY,
            ),

            "source_type": "syllabus_keyword_mapping",

        })

    return course_skill_rows, course_skill_evidence


# =========================================================
# GENERATION REPORT
# =========================================================

def print_generation_report(
    courses,
    topic_rows,
    skill_rows,
    course_skill_rows,
    statistics,
    course_skill_evidence,
):
    """
    Print a concise summary of generated records.
    """

    total_courses = len(courses)

    courses_with_topics = len({
        row["course_code"]
        for row in topic_rows
    })

    courses_with_skill_mappings = len({
        row["course"]
        for row in course_skill_rows
    })

    print("\n" + "=" * 55)
    print("TOPICS AND SKILLS GENERATION REPORT")
    print("=" * 55)

    print(f"Input courses:                 {total_courses}")
    print(f"Courses with extracted topics: {courses_with_topics}")
    print(f"Total topic records:           {len(topic_rows)}")

    print(f"Generated skill taxonomy:      {len(skill_rows)}")

    print(f"Course-skill mappings:         {len(course_skill_rows)}")

    print(
        f"Courses with skill mappings:   "
        f"{courses_with_skill_mappings}"
    )

    print(
        f"Courses with missing syllabus: "
        f"{len(statistics['missing_syllabus'])}"
    )

    print(
        f"Courses with no valid topics:  "
        f"{len(statistics['courses_without_topics'])}"
    )

    print("\nCourses with missing syllabus:")

    if statistics["missing_syllabus"]:

        for code in statistics["missing_syllabus"]:
            print(f"  - {code}")

    else:
        print("  None")

    print("\nCourses with no extracted topics:")

    if statistics["courses_without_topics"]:

        for code in statistics["courses_without_topics"]:
            print(f"  - {code}")

    else:
        print("  None")

    print("\nSkills with course mappings:")

    mapped_skill_ids = {
        skill_id
        for _, skill_id in course_skill_evidence
    }

    for skill_id, name, category, patterns in SKILL_TAXONOMY:

        if skill_id in mapped_skill_ids:
            print(f"  - {skill_id}: {name}")

    print("=" * 55)


# =========================================================
# MAIN
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generate course topics, skills and course-skill "
            "mappings from extracted syllabus data."
        )
    )

    parser.add_argument(
        "--courses",
        default=str(DEFAULT_INPUT),
        help="Path to the extracted courses.csv",
    )

    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for generated CSV files.",
    )

    args = parser.parse_args()

    input_file = Path(args.courses)

    output_dir = Path(args.out_dir)

    print("\nReading extracted courses.csv...")

    courses = read_courses(input_file)

    print(f"Loaded {len(courses)} course records.")

    # -----------------------------------------------------
    # Step 1: Extract topics
    # -----------------------------------------------------

    print("\nExtracting topics from syllabus fields only...")

    topic_rows, statistics = generate_course_topics(courses)

    print(f"Generated {len(topic_rows)} topic records.")

    # -----------------------------------------------------
    # Step 2: Generate skill taxonomy
    # -----------------------------------------------------

    print("\nGenerating controlled skill taxonomy...")

    skill_rows = generate_skill_taxonomy()

    print(f"Generated {len(skill_rows)} skill records.")

    # -----------------------------------------------------
    # Step 3: Map courses to skills
    # -----------------------------------------------------

    print("\nMapping syllabus topics to skills...")

    course_skill_rows, course_skill_evidence = generate_course_skills(
        topic_rows
    )

    print(
        f"Generated {len(course_skill_rows)} course-skill mappings."
    )

    # -----------------------------------------------------
    # Step 4: Write output files
    # -----------------------------------------------------

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_csv(
        output_dir / "course_topics.csv",
        TOPIC_COLUMNS,
        topic_rows,
    )

    write_csv(
        output_dir / "skills.csv",
        SKILL_COLUMNS,
        skill_rows,
    )

    write_csv(
        output_dir / "course_skills.csv",
        COURSE_SKILL_COLUMNS,
        course_skill_rows,
    )

    # -----------------------------------------------------
    # Step 5: Print report
    # -----------------------------------------------------

    print_generation_report(
        courses,
        topic_rows,
        skill_rows,
        course_skill_rows,
        statistics,
        course_skill_evidence,
    )

    print("\nSuccessfully generated:")

    print(output_dir / "course_topics.csv")
    print(output_dir / "skills.csv")
    print(output_dir / "course_skills.csv")

    print("\nIMPORTANT:")
    print("These outputs are extraction candidates.")
    print("Review topic quality and skill mappings before final use.")


if __name__ == "__main__":
    main()