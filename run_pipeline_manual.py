#!/usr/bin/env python3

"""
IIT Bhilai DSAI Knowledge Base Pipeline

Pipeline:
1. Ingest raw source files and maintain SHA-256 manifest.
2. Parse and normalise eight CSV files.
3. Validate data and relationships.
4. Generate retrieval-ready chunks.
5. Export processed data and quality report.

Run:
    python run_pipeline.py

Sample mode:
    python run_pipeline.py --sample

Allow export despite validation errors:
    python run_pipeline.py --allow-errors

Skip raw ingestion:
    python run_pipeline.py --skip-ingest
"""

import argparse
import csv
import hashlib
import html
import json
import re
import sys

from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path


# ============================================================
# 1. CONFIGURATION
# ============================================================

PROGRAMME = "B.Tech Data Science and Artificial Intelligence"
INSTITUTE = "IIT Bhilai"

MIN_COURSES = 15
MIN_RESOURCES = 30
MAX_CHUNK_WORDS = 150

SOURCE_TYPES = {
    "official",
    "open-licence",
    "manual"
}

VERIFICATION_STATUSES = {
    "unverified",
    "human_verified",
    "disputed"
}

PREREQUISITE_KINDS = {
    "hard",
    "recommended",
    "concurrent"
}

SKILL_LEVELS = {
    "intro",
    "working",
    "advanced"
}

TABLES = {

    "courses": "courses.csv",

    "course_skills": "course_skills.csv",

    "prerequisites": "prerequisites.csv",

    "program_plan": "program_plan.csv",

    "resources": "resources.csv",

    "rules": "rules.csv",

    "skills": "skills.csv",

    "source_evidence": "source_evidence.csv"
}

FIELDS = {

    "courses": [
        "code", "title", "dept", "credits",
        "lecture", "tutorial", "practical",
        "semesters", "course_type", "mode",
        "objectives", "syllabus", "prereq_text",
        "source_url", "retrieved_on", "source_type"
    ],

    "course_skills": [
        "course", "skill", "depth",
        "source_url", "retrieved_on", "source_type"
    ],

    "prerequisites": [
        "course", "requires", "kind", "group",
        "source_url", "retrieved_on", "source_type"
    ],

    "program_plan": [
        "semester", "slot",
        "source_url", "retrieved_on", "source_type"
    ],

    "resources": [
        "id", "title", "provider",
        "licence_name", "licence_version",
        "licence_url", "licence_verified_on",
        "fmt", "duration_value", "duration_unit",
        "url", "instructor", "host_institute",
        "description", "source_url", "retrieved_on",
        "source_type", "source_note",
        "verification_status", "verified_on", "verified_by"
    ],

    "rules": [
        "id", "category", "text",
        "numeric_limit", "unit", "applies_to",
        "source_url", "retrieved_on", "source_type"
    ],

    "skills": [
        "id", "name", "level", "parent",
        "source_url", "retrieved_on", "source_type"
    ],

    "source_evidence": [
        "record_id", "extracted_information",
        "pdf_page", "source_heading_or_section",
        "exact_supporting_quotation",
        "source_url", "retrieved_on", "source_type"
    ]
}


# ============================================================
# 2. GENERAL HELPERS
# ============================================================

def clean_header(value):

    value = html.unescape(value or "")

    value = value.strip()

    value = value.replace("**", "")

    value = value.replace("\\", "")

    return value.strip().strip('"').strip()


def clean_text(value):

    return re.sub(
        r"\s+",
        " ",
        str(value or "")
    ).strip()


def split_multi(value):

    if not value:
        return []

    separator = ";" if ";" in value else ","

    return [
        item.strip()
        for item in value.split(separator)
        if item.strip()
    ]


def valid_date(value):

    try:

        date.fromisoformat(value)

        return True

    except (ValueError, TypeError):

        return False


def normalise_code(value):

    value = clean_text(value).upper()

    value = re.sub(r"[\s/_-]+", "", value)

    return value


def normalise_semesters(value):

    roman = {

        "I": "1",
        "II": "2",
        "III": "3",
        "IV": "4",
        "V": "5",
        "VI": "6",
        "VII": "7",
        "VIII": "8"
    }

    values = split_multi(value)

    result = []

    for item in values:

        key = item.upper()

        result.append(
            roman.get(key, key)
        )

    return ";".join(dict.fromkeys(result))


def stable_id(*parts):

    raw = "|".join(
        str(part)
        for part in parts
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:16]

    return f"chunk-{digest}"


def token_estimate(text):

    return max(
        1,
        round(len(text.split()) * 1.3)
    )


# ============================================================
# 3. INGESTION
# ============================================================

def ingest(root):

    raw_dir = root / "data" / "raw"

    raw_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    manifest_path = raw_dir / "MANIFEST.json"

    previous = {}

    if manifest_path.exists():

        try:

            previous = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            ).get("files", {})

        except json.JSONDecodeError:

            previous = {}

    inventory = {}

    changed = []

    for path in sorted(raw_dir.rglob("*")):

        if not path.is_file():
            continue

        if path.name == "MANIFEST.json":
            continue

        relative = path.relative_to(raw_dir).as_posix()

        digest = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

        inventory[relative] = {

            "sha256": digest,

            "size_bytes": path.stat().st_size
        }

        if (
            relative in previous
            and previous[relative].get("sha256") != digest
        ):

            changed.append(relative)

    manifest = {

        "generated_on": date.today().isoformat(),

        "files": inventory,

        "changed_since_previous_manifest": changed,

        "note": (
            "SHA-256 hashes identify the raw files "
            "present during this pipeline run."
        )
    }

    manifest_path.write_text(

        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

    return manifest


# ============================================================
# 4. PARSING
# ============================================================

def read_csv(path):
    rows = []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, skipinitialspace=True)

        if not reader.fieldnames:
            return rows

        reader.fieldnames = [
            clean_header(name) for name in reader.fieldnames
        ]

        for line_no, row in enumerate(reader, start=2):

            # Detect extra columns instead of silently losing data.
            if None in row:
                raise ValueError(
                    f"{path.name}, line {line_no}: "
                    f"Unexpected extra CSV columns: {row[None]}"
                )

            cleaned_row = {
                clean_header(key): clean_text(value)
                for key, value in row.items()
            }

            # Skip completely empty rows.
            if not any(cleaned_row.values()):
                continue

            rows.append(cleaned_row)

    return rows


def load_data(root):

    manual_dir = root / "data" / "manual"

    data = {}

    for table, filename in TABLES.items():

        path = manual_dir / filename

        # Support old filename containing a space.
        if (
            table == "course_skills"
            and not path.exists()
        ):

            alternative = manual_dir / "course skills.csv"

            if alternative.exists():

                path = alternative

        data[table] = read_csv(path)

    return data


def normalise_data(data):

    for row in data["courses"]:

        row["code"] = normalise_code(
            row.get("code", "")
        )

        row["semesters"] = normalise_semesters(
            row.get("semesters", "")
        )

    for table in [
        "course_skills",
        "prerequisites"
    ]:

        for row in data[table]:

            row["course"] = normalise_code(
                row.get("course", "")
            )

            if table == "prerequisites":

                row["requires"] = normalise_code(
                    row.get("requires", "")
                )

    # --------------------------------------------------------
    # NORMALISE PREREQUISITE KINDS
    # --------------------------------------------------------

    prerequisite_kind_map = {
        "required": "hard",
        "hard": "hard",
        "recommended": "recommended",
        "concurrent": "concurrent"
    }

    for row in data["prerequisites"]:

        kind = row.get("kind", "").strip().lower()

        row["kind"] = prerequisite_kind_map.get(
            kind,
            kind
        )


# ============================================================
# 5. VALIDATION
# ============================================================

def issue(issues, severity, check, record, message):

    issues.append({

        "severity": severity,

        "check": check,

        "record": record,

        "message": message
    })


def validate_provenance(row, record, issues):

    if not row.get("source_url"):

        issue(
            issues, "ERROR",
            "source_url", record,
            "Missing source URL."
        )

    if not valid_date(row.get("retrieved_on", "")):

        issue(
            issues, "ERROR",
            "retrieved_on", record,
            "Missing or invalid retrieval date. Use YYYY-MM-DD."
        )

    if row.get("source_type") not in SOURCE_TYPES:

        issue(
            issues, "ERROR",
            "source_type", record,
            f"Invalid source type: {row.get('source_type')!r}"
        )


def find_cycle(graph):

    state = {}

    for start in graph:

        if state.get(start, 0):
            continue

        stack = [(start, 0)]

        path = []

        positions = {}

        while stack:

            node, index = stack[-1]

            if state.get(node, 0) == 0:

                state[node] = 1

                positions[node] = len(path)

                path.append(node)

            neighbours = graph.get(node, [])

            if index >= len(neighbours):

                stack.pop()

                state[node] = 2

                positions.pop(node, None)

                if path and path[-1] == node:

                    path.pop()

                continue

            nxt = neighbours[index]

            stack[-1] = (node, index + 1)

            if state.get(nxt, 0) == 1:

                return path[positions[nxt]:] + [nxt]

            if state.get(nxt, 0) == 0:

                stack.append((nxt, 0))

    return None


def validate_data(data, sample=False):

    issues = []

    courses = data["courses"]

    course_codes = [
        row.get("code", "")
        for row in courses
        if row.get("code")
    ]

    course_set = set(course_codes)


    # -------------------------
    # Courses
    # -------------------------

    seen = set()

    for row in courses:

        code = row.get("code", "") or "<blank>"

        validate_provenance(
            row, code, issues
        )

        # -------------------------
        # Credit validation
        # -------------------------

        credit_text = row.get("credits", "").strip()

        if not credit_text:

            issue(
                issues, "WARN",
                "course_credits", code,
                "Credit information is not available."
            )

        else:

            try:

                credits = float(credit_text)

                if not 0 <= credits <= 30:
                    raise ValueError

            except ValueError:

                issue(
                    issues, "ERROR",
                    "course_credits", code,
                    f"Invalid credit value: {credit_text}"
                )

        if code in seen:

            issue(
                issues, "ERROR",
                "duplicate_course_code", code,
                "Duplicate course code."
            )

        seen.add(code)

        if not re.fullmatch(
            r"[A-Z]{2,5}\d{3,4}",
            code
        ):

            issue(
                issues, "ERROR",
                "course_code_format", code,
                "Expected a code such as ABC123."
            )

        if not row.get("title"):

            issue(
                issues, "ERROR",
                "course_title", code,
                "Missing course title."
            )


            credit_text = (row.get("credits") or "").strip()

            if not credit_text:
                issue(
                    issues, "WARN",
                    "course_credits", code,
                    "Credit information is not available."
                )
            else:
                try:
                    credits = float(credit_text)

                    if credits < 0 or credits > 30:
                        raise ValueError

                except ValueError:
                    issue(
                        issues, "ERROR",
                        "course_credits", code,
                        f"Invalid credit value: {credit_text}"
                    )

        if not row.get("dept"):

            issue(
                issues, "WARN",
                "course_department", code,
                "Department is missing."
            )

        if not row.get("semesters"):

            issue(
                issues, "WARN",
                "course_semesters", code,
                "No semester information recorded."
            )

        else:

            for sem in split_multi(row["semesters"]):

                try:

                    if not 1 <= int(sem) <= 8:

                        raise ValueError

                except ValueError:

                    issue(
                        issues, "ERROR",
                        "course_semester", code,
                        f"Invalid semester: {sem}."
                    )

    # -------------------------
    # Prerequisites
    # -------------------------

    graph = defaultdict(list)

    for index, row in enumerate(
        data["prerequisites"],
        start=1
    ):

        course = row.get("course", "")

        required = row.get("requires", "")

        record = f"{course}->{required} row {index}"

        validate_provenance(
            row, record, issues
        )

        if course not in course_set:

            issue(
                issues, "ERROR",
                "prerequisite_course_ref", record,
                f"Course {course!r} does not exist."
            )

        if required not in course_set:

            issue(
                issues, "ERROR",
                "prerequisite_target_ref", record,
                f"Prerequisite {required!r} does not exist."
            )

        if course and required:

            if course == required:

                issue(
                    issues, "ERROR",
                    "prerequisite_self_loop", record,
                    "Course cannot be its own prerequisite."
                )

            graph[course].append(required)

        if (
            row.get("kind")
            and row["kind"] not in PREREQUISITE_KINDS
        ):

            issue(
                issues, "ERROR",
                "prerequisite_kind", record,
                f"Invalid prerequisite kind: {row['kind']}."
            )

    cycle = find_cycle(graph)

    if cycle:

        issue(
            issues, "ERROR",
            "prerequisite_cycle",
            " -> ".join(cycle),
            "Prerequisite graph contains a cycle."
        )

    # -------------------------
    # Skills
    # -------------------------

    skill_ids = {
        row.get("id", "")
        for row in data["skills"]
        if row.get("id")
    }

    seen_skill_ids = set()

    for row in data["skills"]:

        sid = row.get("id", "") or "<blank>"

        validate_provenance(
            row, sid, issues
        )

        if sid in seen_skill_ids:

            issue(
                issues, "ERROR",
                "duplicate_skill_id", sid,
                "Duplicate skill ID."
            )

        seen_skill_ids.add(sid)

        if not row.get("name"):

            issue(
                issues, "ERROR",
                "skill_name", sid,
                "Missing skill name."
            )

        if (
            row.get("level")
            and row["level"] not in SKILL_LEVELS
        ):

            issue(
                issues, "WARN",
                "skill_level", sid,
                f"Unrecognised skill level: {row['level']}."
            )

        parent = row.get("parent", "")

        if parent and parent not in skill_ids:

            issue(
                issues, "ERROR",
                "skill_parent_ref", sid,
                f"Parent skill {parent!r} does not exist."
            )

    skill_graph = {

        row["id"]: [row["parent"]]

        for row in data["skills"]

        if row.get("id") and row.get("parent")
    }

    skill_cycle = find_cycle(skill_graph)

    if skill_cycle:

        issue(
            issues, "ERROR",
            "skill_cycle",
            " -> ".join(skill_cycle),
            "Skill hierarchy contains a cycle."
        )

    # -------------------------
    # Course-skill links
    # -------------------------

    for index, row in enumerate(
        data["course_skills"],
        start=1
    ):

        record = (
            f"{row.get('course', '')}/"
            f"{row.get('skill', '')} row {index}"
        )

        validate_provenance(
            row, record, issues
        )

        if row.get("course") not in course_set:

            issue(
                issues, "ERROR",
                "course_skill_course_ref", record,
                "Course reference does not exist."
            )

        if row.get("skill") not in skill_ids:

            issue(
                issues, "ERROR",
                "course_skill_skill_ref", record,
                "Skill reference does not exist."
            )

        if (
            row.get("depth")
            and row["depth"] not in SKILL_LEVELS
        ):

            issue(
                issues, "WARN",
                "course_skill_depth", record,
                f"Unrecognised depth: {row['depth']}."
            )

    # -------------------------
    # Rules
    # -------------------------

    seen_rules = set()

    for row in data["rules"]:

        rid = row.get("id", "") or "<blank>"

        validate_provenance(
            row, rid, issues
        )

        if rid in seen_rules:

            issue(
                issues, "ERROR",
                "duplicate_rule_id", rid,
                "Duplicate rule ID."
            )

        seen_rules.add(rid)

        if not row.get("text"):

            issue(
                issues, "ERROR",
                "rule_text", rid,
                "Missing rule text."
            )

    # -------------------------
    # Resources
    # -------------------------

    seen_resources = set()

    for row in data["resources"]:

        rid = row.get("id", "") or "<blank>"

        validate_provenance(
            row, rid, issues
        )

        if rid in seen_resources:

            issue(
                issues, "ERROR",
                "duplicate_resource_id", rid,
                "Duplicate resource ID."
            )

        seen_resources.add(rid)

        if not row.get("title"):

            issue(
                issues, "ERROR",
                "resource_title", rid,
                "Missing resource title."
            )

        if not row.get("licence_name"):

            issue(
                issues, "ERROR",
                "resource_licence", rid,
                "Licence name is missing."
            )

        if (
            row.get("source_type") == "open-licence"
            and not row.get("licence_verified_on")
        ):

            issue(
                issues, "WARN",
                "licence_verification", rid,
                "Open-licence resource has not recorded a licence verification date."
            )

    # -------------------------
    # Programme plan
    # -------------------------

    for index, row in enumerate(
        data["program_plan"],
        start=1
    ):

        record = f"programme plan row {index}"

        validate_provenance(
            row, record, issues
        )

        semester = row.get("semester", "")

        if semester:

            try:

                if not 1 <= int(semester) <= 8:

                    raise ValueError

            except ValueError:

                issue(
                    issues, "ERROR",
                    "program_plan_semester", record,
                    f"Invalid semester: {semester}."
                )

        if not row.get("slot"):

            issue(
                issues, "WARN",
                "program_plan_slot", record,
                "Slot is blank."
            )

    # -------------------------
    # Source evidence
    # -------------------------

    for index, row in enumerate(
        data["source_evidence"],
        start=1
    ):

        record = (
            row.get("record_id")
            or f"EVIDENCE-{index}"
        )

        validate_provenance(
            row, record, issues
        )

        if not (
            row.get("extracted_information")
            or row.get("exact_supporting_quotation")
        ):

            issue(
                issues, "WARN",
                "evidence_content", record,
                "No extracted information or supporting quotation."
            )

    # -------------------------
    # Assignment minimums
    # -------------------------

    if not sample:

        if len(courses) < MIN_COURSES:

            issue(
                issues, "WARN",
                "minimum_courses", "catalogue",
                f"Found {len(courses)} courses; target is {MIN_COURSES}."
            )

        if len(data["resources"]) < MIN_RESOURCES:

            issue(
                issues, "WARN",
                "minimum_resources", "resources",
                f"Found {len(data['resources'])} resources; target is {MIN_RESOURCES}."
            )

    return issues


# ============================================================
# 6. CHUNK GENERATION
# ============================================================

def split_text(text, max_words=MAX_CHUNK_WORDS):

    text = clean_text(text)

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    chunks = []

    current = []

    for sentence in sentences:

        words = sentence.split()

        if not words:
            continue

        if len(words) > max_words:

            if current:

                chunks.append(
                    " ".join(current)
                )

                current = []

            for start in range(
                0,
                len(words),
                max_words
            ):

                chunks.append(
                    " ".join(
                        words[start:start + max_words]
                    )
                )

            continue

        if (
            current
            and len(current) + len(words) > max_words
        ):

            chunks.append(
                " ".join(current)
            )

            current = []

        current.extend(words)

    if current:

        chunks.append(
            " ".join(current)
        )

    return chunks


def build_evidence_index(rows):

    index = defaultdict(list)

    for row in rows:

        record_id = row.get("record_id", "")

        if record_id:

            index[record_id].append(row)

    return index


def get_provenance(row, evidence=None):

    notes = []

    if row.get("source_note"):

        notes.append(
            row["source_note"]
        )

    for item in evidence or []:

        parts = []

        if item.get("pdf_page"):

            parts.append(
                f"PDF page {item['pdf_page']}"
            )

        if item.get("source_heading_or_section"):

            parts.append(
                item["source_heading_or_section"]
            )

        if parts:

            notes.append(
                " / ".join(parts)
            )

    status = row.get(
        "verification_status",
        "unverified"
    )

    if status not in VERIFICATION_STATUSES:

        status = "unverified"

    return {

        "source_url": (
            row.get("source_url") or None
        ),

        "source_note": (
            "; ".join(dict.fromkeys(notes))
            if notes else None
        ),

        "retrieved_on": (
            row.get("retrieved_on") or None
        ),

        "source_type": (
            row.get("source_type") or None
        ),

        "verification_status": status,

        "verified_on": (
            row.get("verified_on") or None
        ),

        "verified_by": (
            row.get("verified_by") or None
        )
    }


def make_chunk(
    parent_id,
    parent_type,
    chunk_type,
    ordinal,
    text,
    metadata,
    prov
):

    identity = "|".join([
        str(parent_type),
        str(parent_id),
        str(chunk_type),
        str(ordinal),
        str(text)
    ])

    digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:16]

    return {

        "chunk_id": f"chunk-{digest}",

        "parent_id": str(parent_id),

        "parent_type": parent_type,

        "chunk_type": chunk_type,

        "ordinal": ordinal,

        "text": text,

        "token_estimate": token_estimate(text),

        "filter_metadata": metadata,

        **prov
    }


def add_text_chunks(
    output,
    parent_id,
    parent_type,
    chunk_type,
    text,
    metadata,
    prov
):

    parts = split_text(text)

    for ordinal, part in enumerate(parts):

        output.append(
            make_chunk(
                parent_id,
                parent_type,
                chunk_type,
                ordinal,
                part,
                metadata,
                prov
            )
        )


def token_estimate(text):

    return max(
        1,
        round(len(text.split()) * 1.3)
    )


# ============================================================
# 7. ENTITY-SPECIFIC CHUNKS
# ============================================================

def generate_chunks(data):

    output = []

    evidence = build_evidence_index(
        data["source_evidence"]
    )

    skills_by_course = defaultdict(list)

    prereqs_by_course = defaultdict(list)

    for row in data["course_skills"]:

        skills_by_course[
            row.get("course", "")
        ].append(row)

    for row in data["prerequisites"]:

        prereqs_by_course[
            row.get("course", "")
        ].append(row)

    # --------------------------------------------------------
    # COURSES
    # --------------------------------------------------------

    for row in data["courses"]:

        code = row.get("code", "")

        if not code:
            continue

        skill_links = skills_by_course[code]

        prereq_edges = prereqs_by_course[code]

        skill_ids = [
            link.get("skill")
            for link in skill_links
            if link.get("skill")
        ]

        prerequisite_metadata = [

            {
                "requires": edge.get("requires") or None,

                "kind": edge.get("kind") or None,

                "group": edge.get("group") or None
            }

            for edge in prereq_edges
        ]

        course_fields = [

            ("Course code", row.get("code")),

            ("Title", row.get("title")),

            ("Department", row.get("dept")),

            ("Credits", row.get("credits")),

            (
                "Lecture/tutorial/practical",
                "/".join(
                    value
                    for value in [
                        row.get("lecture"),
                        row.get("tutorial"),
                        row.get("practical")
                    ]
                    if value
                )
            ),

            ("Semesters", row.get("semesters")),

            ("Course type", row.get("course_type")),

            ("Mode", row.get("mode")),

            ("Prerequisite description", row.get("prereq_text"))
        ]

        card_lines = [

            f"{label}: {value}"

            for label, value in course_fields

            if value
        ]

        if prerequisite_metadata:

            recorded = []

            for edge in prerequisite_metadata:

                item = (
                    f"{edge['requires']} "
                    f"({edge['kind'] or 'unspecified'})"
                )

                if edge["group"]:

                    item += (
                        f" [group: {edge['group']}]"
                    )

                recorded.append(item)

            card_lines.append(
                "Recorded prerequisite edges: "
                + "; ".join(recorded)
            )

        else:

            card_lines.append(
                "No prerequisite edge is recorded in the current dataset. "
                "This does not establish that no prerequisite exists."
            )

        if skill_ids:

            card_lines.append(
                "Linked skill IDs: "
                + ", ".join(skill_ids)
            )

        metadata = {

            "entity": "course",

            "programme": PROGRAMME,

            "course_code": code,

            "title": row.get("title") or None,

            "dept": row.get("dept") or None,

            "credits": row.get("credits") or None,

            "lecture": row.get("lecture") or None,

            "tutorial": row.get("tutorial") or None,

            "practical": row.get("practical") or None,

            "semesters": split_multi(
                row.get("semesters", "")
            ),

            "course_type": row.get("course_type") or None,

            "mode": row.get("mode") or None,

            "skill_ids": skill_ids,

            "prerequisite_edges": prerequisite_metadata
        }

        prov = get_provenance(
            row,
            evidence.get(code)
        )

        output.append(
            make_chunk(
                code,
                "course",
                "course_card",
                0,
                "\n".join(card_lines),
                metadata,
                prov
            )
        )

        add_text_chunks(
            output,
            code,
            "course",
            "objectives",
            row.get("objectives", ""),
            {
                **metadata,
                "entity": "course_objectives"
            },
            prov
        )

        add_text_chunks(
            output,
            code,
            "course",
            "syllabus",
            row.get("syllabus", ""),
            {
                **metadata,
                "entity": "course_syllabus"
            },
            prov
        )

    # --------------------------------------------------------
    # PREREQUISITES
    # --------------------------------------------------------

    for index, row in enumerate(data["prerequisites"]):

        course = row.get("course", "")

        required = row.get("requires", "")

        if not course or not required:
            continue

        kind = row.get("kind") or "unspecified"

        group = row.get("group") or None

        parent_id = (
            f"{course}->{required}:{kind}:"
            f"{group or 'ungrouped'}:{index}"
        )

        text = (
            f"{course} has a recorded {kind} "
            f"prerequisite relationship with {required}."
        )

        if group:

            text += (
                f" Prerequisite group: {group}."
            )

        output.append(
            make_chunk(
                parent_id,
                "prerequisite",
                "prerequisite",
                0,
                text,
                {
                    "entity": "prerequisite",
                    "course": course,
                    "requires": required,
                    "kind": kind,
                    "group": group
                },
                get_provenance(
                    row,
                    evidence.get(course)
                )
            )
        )

    # --------------------------------------------------------
    # COURSE-SKILL RELATIONSHIPS
    # --------------------------------------------------------

    for index, row in enumerate(data["course_skills"]):

        course = row.get("course", "")

        skill = row.get("skill", "")

        if not course or not skill:
            continue

        depth = row.get("depth") or None

        text = (
            f"Course {course} is linked to skill {skill}."
        )

        if depth:

            text += (
                f" Skill coverage depth: {depth}."
            )

        output.append(
            make_chunk(
                f"{course}:{skill}:{index}",
                "course_skill_link",
                "course_skill_link",
                0,
                text,
                {
                    "entity": "course_skill_link",
                    "course": course,
                    "skill": skill,
                    "depth": depth
                },
                get_provenance(
                    row,
                    evidence.get(course)
                )
            )
        )

    # --------------------------------------------------------
    # SKILLS
    # --------------------------------------------------------

    for row in data["skills"]:

        skill_id = row.get("id", "")

        if not skill_id:
            continue

        text = (
            f"Skill: {row.get('name', skill_id)}."
        )

        if row.get("category"):
            text += (
                f" Category: {row['category']}."
            )

        if row.get("level"):
            text += (
                f" Level: {row['level']}."
            )

        if row.get("parent"):
            text += (
                f" Parent skill: {row['parent']}."
            )

        output.append(
            make_chunk(
                skill_id,
                "skill",
                "skill_node",
                0,
                text,
                {
                    "entity": "skill",
                    "skill_id": skill_id,
                    "name": row.get("name") or None,
                    "category": row.get("category") or None,
                    "level": row.get("level") or None,
                    "parent": row.get("parent") or None,
                    "origin": "author_inferred"
                },
                get_provenance(
                    row,
                    evidence.get(skill_id)
                )
            )
        )

    # --------------------------------------------------------
    # ACADEMIC RULES
    # --------------------------------------------------------

    for row in data["rules"]:

        rule_id = row.get("id", "")

        text = row.get("text", "")

        if not rule_id or not text:
            continue

        output.append(
            make_chunk(
                rule_id,
                "academic_rule",
                "rule",
                0,
                text,
                {
                    "entity": "academic_rule",
                    "rule_id": rule_id,
                    "category": row.get("category") or None,
                    "numeric_limit": row.get("numeric_limit") or None,
                    "unit": row.get("unit") or None,
                    "applies_to": row.get("applies_to") or None
                },
                get_provenance(
                    row,
                    evidence.get(rule_id)
                )
            )
        )

    # --------------------------------------------------------
    # RESOURCES
    # --------------------------------------------------------

    for row in data["resources"]:

        resource_id = row.get("id", "")

        if not resource_id:
            continue

        parts = [
            f"Resource: {row.get('title', resource_id)}."
        ]

        labels = [

            ("Provider", "provider"),

            ("Format", "fmt"),

            ("Duration", "duration_value"),

            ("Duration unit", "duration_unit"),

            ("Licence", "licence_name"),

            ("Licence version", "licence_version"),

            ("Description", "description")
        ]

        for label, field in labels:

            if row.get(field):

                parts.append(
                    f"{label}: {row[field]}."
                )

        metadata = {

            "entity": "resource",

            "resource_id": resource_id,

            "title": row.get("title") or None,

            "provider": row.get("provider") or None,

            "licence_name": row.get("licence_name") or None,

            "licence_version": row.get("licence_version") or None,

            "licence_url": row.get("licence_url") or None,

            "licence_verified_on": row.get("licence_verified_on") or None,

            "fmt": row.get("fmt") or None,

            "duration_value": row.get("duration_value") or None,

            "duration_unit": row.get("duration_unit") or None,

            "url": row.get("url") or None,

            "instructor": row.get("instructor") or None,

            "host_institute": row.get("host_institute") or None
        }

        add_text_chunks(
            output,
            resource_id,
            "resource",
            "resource_desc",
            " ".join(parts),
            metadata,
            get_provenance(
                row,
                evidence.get(resource_id)
            )
        )

    # --------------------------------------------------------
    # PROGRAMME PLAN
    # --------------------------------------------------------

    for index, row in enumerate(data["program_plan"]):

        semester = row.get("semester", "")

        slot = row.get("slot", "")

        if not semester and not slot:
            continue

        parent_id = (
            f"PLAN-S{semester}-{slot}-{index}"
        )

        text = (
            f"Programme plan: Semester "
            f"{semester or 'unspecified'}; "
            f"slot: {slot or 'unspecified'}."
        )

        output.append(
            make_chunk(
                parent_id,
                "program_plan",
                "program_plan_slot",
                0,
                text,
                {
                    "entity": "program_plan_slot",
                    "programme": PROGRAMME,
                    "semester": semester or None,
                    "slot": slot or None
                },
                get_provenance(row)
            )
        )

    # --------------------------------------------------------
    # SOURCE EVIDENCE
    # --------------------------------------------------------

    for index, row in enumerate(data["source_evidence"]):

        record_id = (
            row.get("record_id")
            or f"EVIDENCE-{index + 1}"
        )

        parts = []

        if row.get("extracted_information"):

            parts.append(
                "Extracted information: "
                + row["extracted_information"]
            )

        if row.get("exact_supporting_quotation"):

            parts.append(
                'Exact supporting quotation: "'
                + row["exact_supporting_quotation"]
                + '"'
            )

        if row.get("pdf_page"):

            parts.append(
                "PDF page: " + row["pdf_page"]
            )

        if row.get("source_heading_or_section"):

            parts.append(
                "Source section: "
                + row["source_heading_or_section"]
            )

        if not parts:
            continue

        output.append(
            make_chunk(
                record_id,
                "source_evidence",
                "source_evidence",
                0,
                " | ".join(parts),
                {
                    "entity": "source_evidence",
                    "record_id": record_id,
                    "pdf_page": row.get("pdf_page") or None,
                    "source_heading_or_section": (
                        row.get("source_heading_or_section") or None
                    )
                },
                get_provenance(row)
            )
        )

    return output


# ============================================================
# 8. EXPORT AND QUALITY REPORT
# ============================================================

def write_csv(path, rows, fields):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()

        for row in rows:

            writer.writerow({
                field: row.get(field, "")
                for field in fields
            })


def build_quality_report(data, chunks, issues, manifest):

    errors = [
        item for item in issues
        if item["severity"] == "ERROR"
    ]

    warnings = [
        item for item in issues
        if item["severity"] == "WARN"
    ]

    lines = [

        "# DSAI Knowledge Base — Data Quality Report",

        "",

        f"- Generated: {date.today().isoformat()}",

        f"- Programme: {PROGRAMME}",

        f"- Institute: {INSTITUTE}",

        "- Pipeline: ingest → parse → normalise → validate → chunk → export",

        "",

        "## 1. Entity counts",

        "",

        "| Entity | Records |",

        "|---|---:|"
    ]

    for table, rows in data.items():

        lines.append(
            f"| {table} | {len(rows)} |"
        )

    lines += [

        f"| chunks | {len(chunks)} |",

        "",

        "## 2. Chunk distribution",

        "",

        "| Chunk type | Count |",

        "|---|---:|"
    ]

    counts = Counter(
        chunk["chunk_type"]
        for chunk in chunks
    )

    for kind, count in sorted(counts.items()):

        lines.append(
            f"| {kind} | {count} |"
        )

    lines += [

        "",

        "## 3. Validation summary",

        "",

        f"- Errors: {len(errors)}",

        f"- Warnings: {len(warnings)}",

        f"- Total findings: {len(issues)}",

        "",

        "## 4. Field completeness",

        "",

        "| Entity | Field | Present | Total | Completeness |",

        "|---|---|---:|---:|---:|"
    ]

    completeness_fields = {

        "courses": [
            "code", "title", "dept", "credits",
            "semesters", "course_type", "mode",
            "objectives", "syllabus",
            "source_url", "retrieved_on", "source_type"
        ],

        "resources": [
            "id", "title", "licence_name",
            "fmt", "url", "source_url",
            "retrieved_on", "source_type"
        ],

        "rules": [
            "id", "category", "text",
            "source_url", "retrieved_on", "source_type"
        ],

        "skills": [
            "id", "name","category", "level","parent",
            "source_url", "retrieved_on", "source_type"
        ]
    }

    for table, fields in completeness_fields.items():

        rows = data[table]

        for field in fields:

            present = sum(
                bool(row.get(field))
                for row in rows
            )

            total = len(rows)

            percentage = (
                100 * present / total
                if total else 0
            )

            lines.append(
                f"| {table} | {field} | {present} | "
                f"{total} | {percentage:.1f}% |"
            )

    lines += [

        "",

        "## 5. Validation findings",

        ""
    ]

    if issues:

        for item in issues:

            lines.append(
                f"- **{item['severity']} — {item['check']}** "
                f"({item['record']}): {item['message']}"
            )

    else:

        lines.append(
            "No validation findings."
        )

    lines += [

        "",

        "## 6. Raw-source inventory",

        "",

        f"- Files inventoried: {len(manifest.get('files', {}))}",

        f"- Changed files: "
        f"{len(manifest.get('changed_since_previous_manifest', []))}",

        "",

        "## 7. Limitations",

        "",

        "- Missing prerequisite edges do not prove that a course has no prerequisite.",

        "- Skill taxonomy may contain author-inferred entries.",

        "- Token counts are estimates, not exact tokenizer measurements.",

        "- Source URLs, quotations and licences require human verification.",

        "- Numeric rule ranges should be retained in rule text or represented using separate minimum and maximum fields.",

        "- No embeddings or LLM APIs are used.",

        ""
    ]

    return "\n".join(lines)


def export_results(root, data, chunks, issues, manifest, run_info):

    output_dir = root / "data" / "processed"

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # Export all entity tables.
    for table, rows in data.items():

        fields = FIELDS[table]

        write_csv(
            output_dir / f"{table}.csv",
            rows,
            fields
        )

        (output_dir / f"{table}.json").write_text(

            json.dumps(
                rows,
                indent=2,
                ensure_ascii=False
            ),

            encoding="utf-8"
        )

    # Export chunks.
    with (
        output_dir / "chunks.jsonl"
    ).open("w", encoding="utf-8") as file:

        for chunk in chunks:

            file.write(
                json.dumps(
                    chunk,
                    ensure_ascii=False
                ) + "\n"
            )

    # Validation reports.
    write_csv(
        output_dir / "validation_report.csv",
        issues,
        ["severity", "check", "record", "message"]
    )

    (output_dir / "validation_report.json").write_text(

        json.dumps(
            issues,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

    # Run manifest.
    (output_dir / "run_manifest.json").write_text(

        json.dumps(
            run_info,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

    # Quality report.
    report = build_quality_report(
        data,
        chunks,
        issues,
        manifest
    )

    (
        output_dir / "quality_report.md"
    ).write_text(
        report,
        encoding="utf-8"
    )


# ============================================================
# 9. MAIN PIPELINE
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="IIT Bhilai DSAI knowledge-base pipeline."
    )

    parser.add_argument(
        "--root",
        default=".",
        help="Project root directory."
    )

    parser.add_argument(
        "--sample",
        action="store_true",
        help="Sample mode; suppress minimum record-count warnings."
    )

    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip refreshing the raw-source SHA-256 manifest."
    )

    parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="Export despite validation errors. Not recommended for final submission."
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()

    manual_dir = root / "data" / "manual"

    output_dir = root / "data" / "processed"

    if not manual_dir.exists():

        print(
            f"ERROR: Manual data directory not found: {manual_dir}"
        )

        return 2

    raw_dir = root / "data" / "raw"

    if output_dir.resolve() == raw_dir.resolve():

        print(
            "ERROR: Processed output cannot overwrite raw input."
        )

        return 2

    # -------------------------
    # STAGE 1: INGEST
    # -------------------------

    print("\n[1/5] INGEST")

    if args.skip_ingest:

        manifest = {
            "files": {},
            "changed_since_previous_manifest": []
        }

    else:

        manifest = ingest(root)

    print(
        f"Raw files inventoried: "
        f"{len(manifest.get('files', {}))}"
    )

    # -------------------------
    # STAGE 2: PARSE
    # -------------------------

    print("\n[2/5] PARSE AND NORMALISE")

    data = load_data(root)

    normalise_data(data)

    for table, rows in data.items():

        print(
            f"{table:<20}: {len(rows)} records"
        )

    # -------------------------
    # STAGE 3: VALIDATE
    # -------------------------

    print("\n[3/5] VALIDATE")

    issues = validate_data(
        data,
        sample=args.sample
    )

    errors = [
        item for item in issues
        if item["severity"] == "ERROR"
    ]

    warnings = [
        item for item in issues
        if item["severity"] == "WARN"
    ]

    print(f"Errors:   {len(errors)}")

    print(f"Warnings: {len(warnings)}")

    if errors and not args.allow_errors:

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        write_csv(
            output_dir / "validation_report.csv",
            issues,
            ["severity", "check", "record", "message"]
        )

        print(
            "\nPipeline stopped because validation errors exist."
        )

        print(
            "Fix the reported errors before generating final chunks."
        )

        print(
            f"Report: {output_dir / 'validation_report.csv'}"
        )

        return 1

    # -------------------------
    # STAGE 4: CHUNK
    # -------------------------

    print("\n[4/5] CHUNK")

    chunks = generate_chunks(data)

    print(
        f"Generated {len(chunks)} chunks."
    )

    # -------------------------
    # STAGE 5: EXPORT
    # -------------------------

    print("\n[5/5] EXPORT")

    run_info = {

        "generated_on": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),

        "programme": PROGRAMME,

        "institute": INSTITUTE,

        "sample_mode": args.sample,

        "counts": {
            table: len(rows)
            for table, rows in data.items()
        },

        "chunk_count": len(chunks),

        "chunk_types": dict(
            Counter(
                chunk["chunk_type"]
                for chunk in chunks
            )
        ),

        "validation_errors": len(errors),

        "validation_warnings": len(warnings),

        "raw_inventory": manifest
    }

    export_results(
        root,
        data,
        chunks,
        issues,
        manifest,
        run_info
    )

    # -------------------------
    # SUMMARY
    # -------------------------

    print("\n" + "=" * 58)

    print("DSAI KNOWLEDGE BASE PIPELINE COMPLETED")

    print("=" * 58)

    print(
        f"Courses:   {len(data['courses'])}"
    )

    print(
        f"Resources: {len(data['resources'])}"
    )

    print(
        f"Chunks:    {len(chunks)}"
    )

    print(
        f"Errors:    {len(errors)}"
    )

    print(
        f"Warnings:  {len(warnings)}"
    )

    print(
        f"Output:    {output_dir}"
    )

    print("=" * 58)

    if errors:

        print(
            "WARNING: Exported despite validation errors."
        )

    return 0


if __name__ == "__main__":

    raise SystemExit(main())