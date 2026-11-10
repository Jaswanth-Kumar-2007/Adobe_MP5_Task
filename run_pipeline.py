from __future__ import annotations

import argparse
import csv
import logging
import sys
import traceback

from pathlib import Path


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --------------------------------------------------
# PIPELINE IMPORTS
# --------------------------------------------------

from pipeline.normalize import normalize_all
from pipeline.validate import validate_all
from pipeline.relationships import build_relationships
from pipeline.chunking import create_chunks
from pipeline.export import export_knowledge_base
from pipeline.reports import generate_data_quality_report


# --------------------------------------------------
# LOGGING CONFIGURATION
# --------------------------------------------------

def configure_logging(log_path: Path) -> logging.Logger:
    """
    Configure terminal and file logging.
    """

    log_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    logger = logging.getLogger("dsai_knowledge_base")

    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    # File logging.
    file_handler = logging.FileHandler(
        log_path,
        encoding="utf-8"
    )

    file_handler.setFormatter(formatter)

    # Terminal logging.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# --------------------------------------------------
# STAGE 0: DOCUMENT EXTRACTION
# --------------------------------------------------

def run_extraction_stage(
    logger: logging.Logger,
    raw_dir: Path,
    extracted_dir: Path
) -> bool:
    """
    Execute document extraction before the main pipeline.

    Extractors read original documents from data/raw
    and generate CSV files inside data/extracted.

    Extraction failure stops the remaining pipeline.
    """

    logger.info("=" * 65)
    logger.info("STAGE 0: DOCUMENT EXTRACTION")
    logger.info("=" * 65)

    logger.info("Raw source directory: %s", raw_dir)
    logger.info("Extraction output directory: %s", extracted_dir)

    try:

        # Import the extraction orchestrator.
        from run_extraction import main as extraction_main

        # Preserve the original command-line arguments.
        original_argv = sys.argv[:]

        try:

            # Supply arguments to run_extraction.py.
            sys.argv = [
                "run_extraction.py",
                "--raw-dir",
                str(raw_dir),
                "--extracted-dir",
                str(extracted_dir)
            ]

            # Execute extraction.
            result = extraction_main()

        finally:

            # Restore original command-line arguments.
            sys.argv = original_argv

        if result != 0:

            raise RuntimeError(
                "Document extraction failed. "
                "The remaining pipeline stages will not execute."
            )

        logger.info(
            "Document extraction completed successfully."
        )

        return True

    except Exception:

        logger.exception(
            "Document extraction stage failed."
        )

        raise


# --------------------------------------------------
# MAIN PIPELINE
# --------------------------------------------------

def run_pipeline(
    raw_dir: Path,
    extracted_dir: Path,
    processed_dir: Path,
    output_dir: Path,
    reports_dir: Path,
    logger: logging.Logger
) -> int:
    """
    Execute the complete knowledge-base pipeline.

    Execution order:

        0. Document extraction
        1. Normalization
        2. Validation
        3. Relationship generation
        4. Chunk generation
        5. Knowledge-base export
        6. Data-quality reporting

    Return codes:

        0 = Successful execution without validation errors.
        1 = Pipeline completed, but validation errors exist.
        2 = Pipeline execution failed.
    """

    try:

        logger.info("=" * 65)
        logger.info("DSAI KNOWLEDGE BASE PIPELINE STARTED")
        logger.info("=" * 65)

        logger.info("Project root: %s", PROJECT_ROOT)
        logger.info("Raw directory: %s", raw_dir)
        logger.info("Extracted directory: %s", extracted_dir)
        logger.info("Processed directory: %s", processed_dir)
        logger.info("Output directory: %s", output_dir)
        logger.info("Reports directory: %s", reports_dir)

        # --------------------------------------------------
        # CHECK SOURCE DIRECTORY
        # --------------------------------------------------

        if not raw_dir.exists():

            raise FileNotFoundError(
                f"Raw source directory does not exist: {raw_dir}"
            )

        if not raw_dir.is_dir():

            raise NotADirectoryError(
                f"Raw source path is not a directory: {raw_dir}"
            )

        extracted_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        processed_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        reports_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # --------------------------------------------------
        # STAGE 0: DOCUMENT EXTRACTION
        # --------------------------------------------------

        run_extraction_stage(
            logger=logger,
            raw_dir=raw_dir,
            extracted_dir=extracted_dir
        )

        # Define intermediate directories.
        normalized_dir = processed_dir / "normalized"

        relationships_dir = (
            processed_dir / "relationships"
        )

        chunks_dir = (
            processed_dir / "chunks"
        )

        # --------------------------------------------------
        # STAGE 1: NORMALIZATION
        # --------------------------------------------------

        logger.info("=" * 65)
        logger.info("STAGE 1/6: NORMALIZATION")
        logger.info("=" * 65)

        extraction_summary = normalize_all(
            extracted_dir,
            normalized_dir
        )

        logger.info(
            "Normalized entity files: %d",
            len(extraction_summary["entities"])
        )

        logger.info(
            "Evidence records merged: %d",
            extraction_summary["evidence_records"]
        )

        # --------------------------------------------------
        # STAGE 2: VALIDATION
        # --------------------------------------------------

        logger.info("=" * 65)
        logger.info("STAGE 2/6: VALIDATION")
        logger.info("=" * 65)

        issues = validate_all(
            normalized_dir
        )

        errors = sum(
            issue["severity"] == "ERROR"
            for issue in issues
        )

        warnings = sum(
            issue["severity"] == "WARN"
            for issue in issues
        )

        logger.info(
            "Validation completed."
        )

        logger.info(
            "Errors: %d | Warnings: %d",
            errors,
            warnings
        )

        # Validation errors do not immediately stop execution.
        # Continue generating reports and useful outputs.

        # --------------------------------------------------
        # STAGE 3: RELATIONSHIPS
        # --------------------------------------------------

        logger.info("=" * 65)
        logger.info("STAGE 3/6: RELATIONSHIPS")
        logger.info("=" * 65)

        relationships = build_relationships(
            normalized_dir,
            relationships_dir
        )

        logger.info(
            "Course relationships generated: %d",
            relationships["summary"]["total_courses"]
        )

        # --------------------------------------------------
        # STAGE 4: CHUNKING
        # --------------------------------------------------

        logger.info("=" * 65)
        logger.info("STAGE 4/6: CHUNKING")
        logger.info("=" * 65)

        chunks = create_chunks(
            normalized_dir,
            chunks_dir
        )

        logger.info(
            "Knowledge chunks generated: %d",
            len(chunks)
        )

        # --------------------------------------------------
        # STAGE 5: EXPORT
        # --------------------------------------------------

        logger.info("=" * 65)
        logger.info("STAGE 5/6: EXPORT")
        logger.info("=" * 65)

        export_summary = export_knowledge_base(
            normalized_dir=normalized_dir,
            output_dir=output_dir,
            chunks=chunks,
            relationships=relationships
        )

        logger.info(
            "Knowledge base JSON: %s",
            export_summary["knowledge_base_json"]
        )

        logger.info(
            "Knowledge base JSONL: %s",
            export_summary["knowledge_base_jsonl"]
        )

        logger.info(
            "Chunks JSONL: %s",
            export_summary["chunks_jsonl"]
        )

        # --------------------------------------------------
        # STAGE 6: DATA QUALITY REPORTS
        # --------------------------------------------------

        logger.info("=" * 65)
        logger.info("STAGE 6/6: DATA QUALITY REPORTS")
        logger.info("=" * 65)

        report_path = generate_data_quality_report(
            extraction_summary=extraction_summary,
            issues=issues,
            export_summary=export_summary,
            reports_dir=reports_dir
        )

        logger.info(
            "Data quality report generated: %s",
            report_path
        )

        # --------------------------------------------------
        # FINAL STATUS
        # --------------------------------------------------

        logger.info("=" * 65)

        if errors:

            logger.error(
                "PIPELINE COMPLETED WITH %d VALIDATION ERRORS.",
                errors
            )

            logger.info(
                "Check validation_issues.csv for details."
            )

            return 1

        if warnings:

            logger.warning(
                "PIPELINE COMPLETED WITH %d WARNINGS.",
                warnings
            )

            logger.info(
                "Review warnings before final submission."
            )

        else:

            logger.info(
                "PIPELINE COMPLETED WITHOUT VALIDATION ISSUES."
            )

        logger.info("=" * 65)

        return 0

    # --------------------------------------------------
    # ERROR HANDLING
    # --------------------------------------------------

    except FileNotFoundError as exc:

        logger.exception(
            "Required file or directory not found: %s",
            exc
        )

        return 2

    except NotADirectoryError as exc:

        logger.exception(
            "Invalid directory: %s",
            exc
        )

        return 2

    except PermissionError as exc:

        logger.exception(
            "Permission denied while accessing project files: %s",
            exc
        )

        return 2

    except csv.Error as exc:

        logger.exception(
            "CSV processing error: %s",
            exc
        )

        return 2

    except KeyboardInterrupt:

        logger.warning(
            "Pipeline interrupted by user."
        )

        return 130

    except Exception as exc:

        logger.exception(
            "Unexpected pipeline failure: %s",
            exc
        )

        logger.debug(
            "Full traceback:\n%s",
            traceback.format_exc()
        )

        return 2

    finally:

        logger.info(
            "Pipeline execution attempt finished."
        )


# --------------------------------------------------
# COMMAND-LINE INTERFACE
# --------------------------------------------------

def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Run the complete DSAI Knowledge Base workflow: "
            "document extraction, normalization, validation, "
            "relationship generation, chunking, export "
            "and data-quality reporting."
        )
    )

    # Original source documents.
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw",
        help="Directory containing original source documents."
    )

    # Extractor-generated CSV files.
    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "extracted",
        help="Directory containing extracted CSV files."
    )

    # Intermediate processing files.
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed",
        help="Directory for normalized and intermediate files."
    )

    # Final knowledge-base exports.
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "output",
        help="Directory for final knowledge-base exports."
    )

    # Reports and logs.
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=PROJECT_ROOT / "reports",
        help="Directory for reports and logs."
    )

    args = parser.parse_args()

    logger = configure_logging(
        args.reports_dir / "pipeline.log"
    )

    try:

        exit_code = run_pipeline(
            raw_dir=args.raw_dir,
            extracted_dir=args.extracted_dir,
            processed_dir=args.processed_dir,
            output_dir=args.output_dir,
            reports_dir=args.reports_dir,
            logger=logger
        )

        return exit_code

    except KeyboardInterrupt:

        logger.warning(
            "Pipeline interrupted by user."
        )

        return 130

    except Exception:

        logger.exception(
            "Fatal error while starting the pipeline."
        )

        return 2

    finally:

        # Flush and close every logging handler.
        for handler in list(logger.handlers):

            try:

                handler.flush()
                handler.close()

            except Exception:

                pass

            finally:

                logger.removeHandler(handler)


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":

    raise SystemExit(main())