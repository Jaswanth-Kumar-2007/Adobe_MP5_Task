import re
import unicodedata


def normalize_unicode(text: str) -> str:
    """Normalize Unicode characters."""

    return unicodedata.normalize("NFKC", text or "")


def remove_null_characters(text: str) -> str:
    """Remove null characters introduced during PDF extraction."""

    return (text or "").replace("\x00", "")


def normalize_line_endings(text: str) -> str:
    """Standardize line endings."""

    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def fix_line_break_hyphenation(text: str) -> str:
    """
    Join words split across PDF lines using hyphens.

    Example:
        prerequi-
        site

    Becomes:
        prerequisite
    """

    return re.sub(
        r"(?<=\w)-\s*\n\s*(?=\w)",
        "",
        text or ""
    )


def normalize_spaces(text: str) -> str:
    """Remove unnecessary spaces while preserving paragraph boundaries."""

    text = re.sub(r"[ \t]+", " ", text or "")

    text = re.sub(r"\n[ \t]+", "\n", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def clean_pdf_text(text: str) -> str:
    """Apply the standard PDF text-cleaning operations."""

    text = normalize_unicode(text)

    text = remove_null_characters(text)

    text = normalize_line_endings(text)

    text = fix_line_break_hyphenation(text)

    text = normalize_spaces(text)

    return text


def clean_pdf_line(line: str) -> str:
    """Clean an individual extracted PDF line."""

    line = normalize_unicode(line)

    line = remove_null_characters(line)

    line = re.sub(r"\s+", " ", line)

    return line.strip()


def split_into_lines(text: str) -> list[str]:
    """Return non-empty cleaned lines."""

    text = clean_pdf_text(text)

    return [
        clean_pdf_line(line)
        for line in text.splitlines()
        if clean_pdf_line(line)
    ]