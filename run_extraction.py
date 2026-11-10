from __future__ import annotations

import argparse
import logging
import shutil
import sys
import traceback

from datetime import datetime
from pathlib import Path


# =========================================================
# PROJECT CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent

DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_EXTRACTED_DIR = PROJECT_ROOT / "data" / "extracted"

LOG_FILE = PROJECT_ROOT / "reports" / "extraction.log"

RESOURCE_EXTRACTION_ENABLED = False


# =========================================================
# OUTPUT CONFIGURATION
# =========================================================

# Only these files are placed directly inside data/extracted/.
# Evidence, review, and candidate files go into data/extracted/review/.

PRIMARY_OUTPUTS = {
    "courses": [
        "courses.csv",
        "prerequisites.csv",
    ],

    "rules": [
        "rules.csv",
    ],

    "program_plan": [
        "program_plan.csv",
    ],

    "catalogue": [
        "course_catalogue.csv",
        "course_eligibility.csv",
    ],

    "topics_skills": [
        "course_topics.csv",
        "skills.csv",
        "course_skills.csv",
    ],

    "resources": [],
}

REVIEW_OUTPUTS = {
    "resources": [
        "resources_web_candidates.csv",
    ],
}


# =========================================================
# LOGGING
# =========================================================

def setup_logger() -> logging.Logger:

    LOG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    logger = logging.getLogger("dsai_extraction")

    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8"
    )

    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# =========================================================
# COMMAND-LINE ARGUMENTS
# =========================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Extract DSAI Knowledge Base information "
            "from original academic source documents."
        )
    )

    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Directory containing original PDFs."
    )

    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=DEFAULT_EXTRACTED_DIR,
        help="Directory for extracted CSV files."
    )

    parser.add_argument(
        "--course-pdf",
        type=Path,
        default=None
    )

    parser.add_argument(
        "--manual-pdf",
        type=Path,
        default=None
    )

    parser.add_argument(
        "--program-plan-pdf",
        type=Path,
        default=None
    )

    parser.add_argument(
        "--catalogue-pdf",
        type=Path,
        default=None
    )

    parser.add_argument(
        "--resource-max-terms",
        type=int,
        default=30,
        help="Maximum number of resource search terms."
    )

    parser.add_argument(
        "--resource-max-results",
        type=int,
        default=5,
        help="Maximum search results per resource term."
    )

    parser.add_argument(
        "--resource-delay",
        type=float,
        default=1.0,
        help="Delay between resource search requests."
    )

    return parser.parse_args()


# =========================================================
# EXTRACTOR IMPORTS
# =========================================================

def import_extractors(logger: logging.Logger):

    try:

        from extractors.course_of_study import extract_courses

        from extractors.ug_manual import extract_rules

        from extractors.program_structure import (
            extract_semester_courses
        )

        from extractors.course_catalogue import (
            extract_course_catalogue
        )

        from extractors.topics_skills import (
            generate_topics_skills
        )

        from extractors.resources import (
            extract_resources
        )

        extractors = {
            "courses": extract_courses,
            "rules": extract_rules,
            "program_plan": extract_semester_courses,
            "catalogue": extract_course_catalogue,
            "topics_skills": generate_topics_skills,
            "resources": extract_resources,
        }

        logger.info(
            "All six extractor modules imported successfully."
        )

        return extractors

    except Exception:

        logger.exception(
            "Failed to import one or more extractor modules."
        )

        raise


# =========================================================
# PDF VALIDATION
# =========================================================

def validate_pdf(
    pdf_path: Path,
    extractor_name: str,
    logger: logging.Logger
) -> bool:

    if not pdf_path.exists():

        logger.error(
            "%s PDF not found: %s",
            extractor_name,
            pdf_path
        )

        return False

    if not pdf_path.is_file():

        logger.error(
            "%s path is not a file: %s",
            extractor_name,
            pdf_path
        )

        return False

    if pdf_path.suffix.lower() != ".pdf":

        logger.error(
            "%s source is not a PDF: %s",
            extractor_name,
            pdf_path
        )

        return False

    return True


# =========================================================
# EXTRACTOR EXECUTION
# =========================================================

def run_extractor(
    name: str,
    function,
    arguments: list[str],
    logger: logging.Logger
) -> bool:

    logger.info("=" * 65)
    logger.info("Starting extractor: %s", name)

    if not hasattr(function, "main"):

        logger.error(
            "%s does not contain a main() function.",
            name
        )

        return False

    original_argv = sys.argv[:]

    try:

        sys.argv = [
            name,
            *arguments
        ]

        function.main()

        logger.info(
            "Successfully completed: %s",
            name
        )

        return True

    except SystemExit as exc:

        if exc.code in (None, 0):

            logger.info(
                "Extractor completed: %s",
                name
            )

            return True

        logger.error(
            "Extractor exited with code %s: %s",
            exc.code,
            name
        )

        return False

    except Exception:

        logger.error(
            "Extractor failed: %s",
            name
        )

        logger.error(
            traceback.format_exc()
        )

        return False

    finally:

        sys.argv = original_argv


# =========================================================
# STAGING DIRECTORY MANAGEMENT
# =========================================================

def prepare_stage_directory(
    staging_dir: Path
) -> None:

    if staging_dir.exists():

        shutil.rmtree(staging_dir)

    staging_dir.mkdir(
        parents=True,
        exist_ok=True
    )


# =========================================================
# PUBLISH EXTRACTOR OUTPUTS
# =========================================================

def publish_stage_outputs(
    stage_name: str,
    staging_dir: Path,
    extracted_dir: Path,
    logger: logging.Logger
) -> tuple[list[str], list[str]]:

    review_dir = (
        extracted_dir
        / "review"
        / stage_name
    )

    review_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    primary_names = set(
        PRIMARY_OUTPUTS.get(stage_name, [])
    )

    review_names = set(
        REVIEW_OUTPUTS.get(stage_name, [])
    )

    published_primary = []
    published_review = []

    csv_files = sorted(
        staging_dir.glob("*.csv")
    )

    for source_file in csv_files:

        filename = source_file.name

        if filename in primary_names:

            destination = extracted_dir / filename

            category = "PRIMARY"

        else:

            destination = review_dir / filename

            category = "REVIEW"

        # Replace only the output file with the same name.
        if destination.exists():

            destination.unlink()

        shutil.move(
            str(source_file),
            str(destination)
        )

        if category == "PRIMARY":

            published_primary.append(filename)

            logger.info(
                "PRIMARY OUTPUT: %s",
                destination
            )

        else:

            published_review.append(filename)

            logger.info(
                "REVIEW OUTPUT: %s",
                destination
            )

    # Check that all expected primary files were produced.
    missing_primary = (
        primary_names - set(published_primary)
    )

    for filename in sorted(missing_primary):

        logger.error(
            "Expected primary output was not generated: %s",
            filename
        )

    # Check expected review outputs for stages that require them.
    missing_review = (
        review_names - set(published_review)
    )

    for filename in sorted(missing_review):

        logger.warning(
            "Expected review output was not generated: %s",
            filename
        )

    return published_primary, published_review


# =========================================================
# COMPLETE EXTRACTION STAGE
# =========================================================

def execute_stage(
    stage_name: str,
    display_name: str,
    function,
    arguments: list[str],
    staging_root: Path,
    extracted_dir: Path,
    logger: logging.Logger,
    required_review_outputs: bool = False,
) -> bool:

    staging_dir = staging_root / stage_name

    prepare_stage_directory(staging_dir)

    # Run extractor.
    success = run_extractor(
        name=display_name,
        function=function,
        arguments=arguments,
        logger=logger
    )

    if not success:

        logger.error(
            "Skipping publication because stage failed: %s",
            display_name
        )

        return False

    # Move generated CSVs into their final locations.
    primary, review = publish_stage_outputs(
        stage_name=stage_name,
        staging_dir=staging_dir,
        extracted_dir=extracted_dir,
        logger=logger
    )

    # Every stage must produce its expected primary files.
    expected_primary = set(
        PRIMARY_OUTPUTS.get(stage_name, [])
    )

    if not expected_primary.issubset(set(primary)):

        logger.error(
            "Stage did not produce all required primary outputs: %s",
            display_name
        )

        return False

    # Resource extraction must produce candidates.
    if required_review_outputs:

        expected_review = set(
            REVIEW_OUTPUTS.get(stage_name, [])
        )

        if not expected_review.issubset(set(review)):

            logger.error(
                "Stage did not produce required review outputs: %s",
                display_name
            )

            return False

    return True


# =========================================================
# MAIN EXTRACTION PROCESS
# =========================================================

def main() -> int:

    logger = setup_logger()

    start_time = datetime.now()

    results = {}

    try:

        args = parse_args()

        raw_dir = args.raw_dir.resolve()
        extracted_dir = args.extracted_dir.resolve()

        # -------------------------------------------------
        # SOURCE FILE CONFIGURATION
        # -------------------------------------------------

        course_pdf = (
            args.course_pdf.resolve()
            if args.course_pdf
            else raw_dir / "Course_of_Study.pdf"
        )

        manual_pdf = (
            args.manual_pdf.resolve()
            if args.manual_pdf
            else raw_dir / "UG_Manual.pdf"
        )

        program_plan_pdf = (
            args.program_plan_pdf.resolve()
            if args.program_plan_pdf
            else course_pdf
        )

        catalogue_pdf = (
            args.catalogue_pdf.resolve()
            if args.catalogue_pdf
            else raw_dir / "List_of_courses_V4.pdf"
        )

        # -------------------------------------------------
        # DIRECTORY INITIALIZATION
        # -------------------------------------------------

        logger.info("=" * 65)
        logger.info("DSAI KNOWLEDGE BASE EXTRACTION")
        logger.info("=" * 65)

        logger.info(
            "Project directory: %s",
            PROJECT_ROOT
        )

        logger.info(
            "Raw directory: %s",
            raw_dir
        )

        logger.info(
            "Extracted directory: %s",
            extracted_dir
        )

        logger.info(
            "Review directory: %s",
            extracted_dir / "review"
        )

        logger.info(
            "Course PDF: %s",
            course_pdf
        )

        logger.info(
            "UG Manual PDF: %s",
            manual_pdf
        )

        logger.info(
            "Programme Plan PDF: %s",
            program_plan_pdf
        )

        logger.info(
            "Course Catalogue PDF: %s",
            catalogue_pdf
        )

        if not raw_dir.exists() or not raw_dir.is_dir():

            raise NotADirectoryError(
                f"Invalid raw directory: {raw_dir}"
            )

        extracted_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        review_dir = extracted_dir / "review"

        review_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        staging_root = extracted_dir / ".staging"

        staging_root.mkdir(
            parents=True,
            exist_ok=True
        )

        # -------------------------------------------------
        # IMPORT EXTRACTORS
        # -------------------------------------------------

        extractors = import_extractors(logger)

        # -------------------------------------------------
        # 1. COURSE EXTRACTION
        # -------------------------------------------------

        if validate_pdf(
            course_pdf,
            "Course of Study",
            logger
        ):

            results["courses"] = execute_stage(
                stage_name="courses",
                display_name="Course Extraction",
                function=extractors["courses"],
                arguments=[
                    "--pdf",
                    str(course_pdf),
                    "--output-dir",
                    str(staging_root / "courses"),
                    "--source-url",
                    course_pdf.name,
                ],
                staging_root=staging_root,
                extracted_dir=extracted_dir,
                logger=logger
            )

        else:

            results["courses"] = False

        # -------------------------------------------------
        # 2. ACADEMIC RULE EXTRACTION
        # -------------------------------------------------

        if validate_pdf(
            manual_pdf,
            "UG Manual",
            logger
        ):

            results["rules"] = execute_stage(
                stage_name="rules",
                display_name="UG Manual Rules",
                function=extractors["rules"],
                arguments=[
                    "--pdf",
                    str(manual_pdf),
                    "--out-dir",
                    str(staging_root / "rules"),
                ],
                staging_root=staging_root,
                extracted_dir=extracted_dir,
                logger=logger
            )

        else:

            results["rules"] = False

        # -------------------------------------------------
        # 3. PROGRAMME PLAN EXTRACTION
        # -------------------------------------------------

        if validate_pdf(
            program_plan_pdf,
            "Programme Plan",
            logger
        ):

            results["program_plan"] = execute_stage(
                stage_name="program_plan",
                display_name="Programme Plan",
                function=extractors["program_plan"],
                arguments=[
                    "--pdf",
                    str(program_plan_pdf),
                    "--out-dir",
                    str(staging_root / "program_plan"),
                ],
                staging_root=staging_root,
                extracted_dir=extracted_dir,
                logger=logger
            )

        else:

            results["program_plan"] = False

        # -------------------------------------------------
        # 4. COURSE CATALOGUE EXTRACTION
        # -------------------------------------------------

        if validate_pdf(
            catalogue_pdf,
            "Course Catalogue",
            logger
        ):

            results["catalogue"] = execute_stage(
                stage_name="catalogue",
                display_name="Course Catalogue",
                function=extractors["catalogue"],
                arguments=[
                    "--pdf",
                    str(catalogue_pdf),
                    "--out-dir",
                    str(staging_root / "catalogue"),
                ],
                staging_root=staging_root,
                extracted_dir=extracted_dir,
                logger=logger
            )

        else:

            results["catalogue"] = False

        # -------------------------------------------------
        # 5. TOPICS AND SKILLS
        # -------------------------------------------------

        courses_file = extracted_dir / "courses.csv"

        if (
            results.get("courses")
            and courses_file.exists()
        ):

            results["topics_skills"] = execute_stage(
                stage_name="topics_skills",
                display_name="Topics and Skills",
                function=extractors["topics_skills"],
                arguments=[
                    "--courses",
                    str(courses_file),
                    "--out-dir",
                    str(staging_root / "topics_skills"),
                ],
                staging_root=staging_root,
                extracted_dir=extracted_dir,
                logger=logger
            )

        else:

            results["topics_skills"] = False

            logger.warning(
                "Topics and skills generation skipped: "
                "course extraction did not produce courses.csv."
            )

        # -------------------------------------------------
        # 6. RESOURCE DISCOVERY
        # -------------------------------------------------

        topics_file = extracted_dir / "course_topics.csv"
        skills_file = extracted_dir / "skills.csv"

        if RESOURCE_EXTRACTION_ENABLED:

            if (
                results.get("topics_skills")
                and topics_file.exists()
                and skills_file.exists()
            ):

                results["resources"] = execute_stage(
                    stage_name="resources",
                    display_name="Resource Discovery",
                    function=extractors["resources"],
                    arguments=[
                        "--data-dir",
                        str(extracted_dir),
                        "--out",
                        str(
                            staging_root
                            / "resources"
                            / "resources_web_candidates.csv"
                        ),
                        "--max-terms",
                        str(args.resource_max_terms),
                        "--max-results",
                        str(args.resource_max_results),
                        "--delay",
                        str(args.resource_delay),
                    ],
                    staging_root=staging_root,
                    extracted_dir=extracted_dir,
                    logger=logger,
                    required_review_outputs=True
                )

            else:

                results["resources"] = False

                logger.warning(
                    "Resource discovery skipped: "
                    "topics_skills extraction did not produce "
                    "course_topics.csv and skills.csv."
                )

        else:

            logger.warning(
                "Resource extraction skipped because DuckDuckGo "
                "search requests were timing out."
            )

        # -------------------------------------------------
        # CLEAN TEMPORARY STAGING DIRECTORY
        # -------------------------------------------------

        if staging_root.exists():

            shutil.rmtree(staging_root)

        # -------------------------------------------------
        # OUTPUT CHECKS
        # -------------------------------------------------

        logger.info("=" * 65)
        logger.info("PRIMARY OUTPUT CHECKS")
        logger.info("=" * 65)

        expected_files = [
            "courses.csv",
            "prerequisites.csv",
            "rules.csv",
            "program_plan.csv",
            "course_catalogue.csv",
            "course_eligibility.csv",
            "course_topics.csv",
            "skills.csv",
            "course_skills.csv",
        ]

        for filename in expected_files:

            output_file = extracted_dir / filename

            if output_file.exists():

                logger.info(
                    "OUTPUT FOUND: %s",
                    output_file
                )

            else:

                logger.warning(
                    "OUTPUT MISSING: %s",
                    output_file
                )

        logger.info("=" * 65)
        logger.info("REVIEW OUTPUT CHECKS")
        logger.info("=" * 65)

        for review_file in sorted(
            review_dir.rglob("*.csv")
        ):

            logger.info(
                "REVIEW FILE: %s",
                review_file.relative_to(extracted_dir)
            )

        # -------------------------------------------------
        # EXTRACTION SUMMARY
        # -------------------------------------------------

        logger.info("=" * 65)
        logger.info("EXTRACTION SUMMARY")
        logger.info("=" * 65)

        enabled_results = {
            name: success
            for name, success in results.items()
            if name != "resources" or RESOURCE_EXTRACTION_ENABLED
        }

        for name, success in enabled_results.items():

            status = "SUCCESS" if success else "FAILED"

            logger.info(
                "%-25s : %s",
                name,
                status
            )

        successful = sum(enabled_results.values())
        failed = len(enabled_results) - successful

        logger.info(
            "Successful extractors: %d",
            successful
        )

        logger.info(
            "Failed extractors: %d",
            failed
        )

        logger.info(
            "Total execution time: %.2f seconds",
            (datetime.now() - start_time).total_seconds()
        )

        if failed:

            logger.error(
                "Extraction finished with %d failure(s).",
                failed
            )

            return 1

        logger.info(
            "All extraction stages completed successfully."
        )

        return 0

    except FileNotFoundError as exc:

        logger.exception(
            "Required source file or directory missing: %s",
            exc
        )

        return 1

    except NotADirectoryError as exc:

        logger.exception(
            "Invalid directory: %s",
            exc
        )

        return 1

    except PermissionError as exc:

        logger.exception(
            "Permission error: %s",
            exc
        )

        return 1

    except KeyboardInterrupt:

        logger.warning(
            "Extraction interrupted by user."
        )

        return 130

    except Exception:

        logger.exception(
            "Unexpected extraction failure."
        )

        return 1

    finally:

        logger.info(
            "Extraction process finished."
        )

        for handler in list(logger.handlers):

            try:

                handler.flush()
                handler.close()

            except Exception:
                pass

            finally:

                logger.removeHandler(handler)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    raise SystemExit(main())