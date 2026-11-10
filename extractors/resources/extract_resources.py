#!/usr/bin/env python3
"""Discover candidate learning resources and extract webpage metadata.

Lenient by default: individual failures never stop the run. Everything that goes
wrong is collected into an error report CSV next to the output file
(``<output>_error_report.csv``) and summarised in the log. Use ``--strict`` to
get a non-zero exit code when any ERROR-level problem occurred.

Requires: requests, beautifulsoup4, ddgs   (uv add requests beautifulsoup4 ddgs)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import logging
import random
import re
import sys
import threading
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# CONFIGURATION
# =========================================================

def _find_project_root() -> Path:
    parents = Path(__file__).resolve().parents
    return parents[2] if len(parents) > 2 else parents[-1]


PROJECT_ROOT = _find_project_root()
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "extracted"
DEFAULT_OUTPUT = DEFAULT_DATA_DIR / "resources_web_candidates.csv"

BOT_NAME = "ResourceDiscoveryBot"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_QUERY_SUFFIX = "free online learning course tutorial documentation lecture"

REQUEST_TIMEOUT = 12
MAX_HTML_BYTES = 2_000_000
MAX_TITLE_CHARS = 300
MAX_DESCRIPTION_CHARS = 1000

BLOCKED_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com", "pinterest.com",
    "tiktok.com", "linkedin.com", "reddit.com", "quora.com",
    "amazon.com", "ebay.com", "flipkart.com",
}

TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAMS = {"fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "ref", "ref_src"}
VIDEO_HOSTS = {"youtube.com", "youtu.be", "vimeo.com", "dailymotion.com"}

FILE_EXTENSIONS = {
    "pdf": "pdf", "ppt": "ppt", "pptx": "pptx", "doc": "doc", "docx": "docx",
    "zip": "zip", "mp4": "mp4", "mp3": "mp3", "ipynb": "ipynb",
    "html": "webpage", "htm": "webpage",
}

RESOURCE_COLUMNS = [
    "id", "title", "provider", "licence_name", "licence_version", "licence_url",
    "licence_verified_on", "fmt", "duration_value", "duration_unit", "url",
    "instructor", "host_institute", "description", "source_url", "retrieved_on",
    "source_type", "source_note", "verification_status", "verified_on", "verified_by",
]

LOGGER_NAME = "resource_discovery"


@dataclass
class Settings:
    data_dir: Path = DEFAULT_DATA_DIR
    output_path: Path = DEFAULT_OUTPUT
    max_terms: int = 30
    max_results: int = 5
    delay: float = 1.0
    workers: int = 4
    timeout: float = REQUEST_TIMEOUT
    retries: int = 1
    query_suffix: str = DEFAULT_QUERY_SUFFIX
    block_domains: list[str] = field(default_factory=list)
    user_agent: str = DEFAULT_USER_AGENT
    respect_robots: bool = False
    fresh: bool = False
    report_path: Path | None = None

    def normalize(self) -> "Settings":
        """Clamp bad values instead of failing."""
        self.data_dir = Path(self.data_dir).resolve()
        self.output_path = Path(self.output_path).resolve()
        self.max_terms = max(1, int(self.max_terms))
        self.max_results = max(1, int(self.max_results))
        self.delay = max(0.0, float(self.delay))
        self.workers = max(1, int(self.workers))
        self.timeout = max(1.0, float(self.timeout))
        self.retries = max(0, int(self.retries))
        if self.report_path is None:
            self.report_path = self.output_path.with_name(
                self.output_path.stem + "_error_report.csv"
            )
        self.report_path = Path(self.report_path).resolve()
        return self


# =========================================================
# LOGGING
# =========================================================

def setup_logger(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


# =========================================================
# ERROR REPORT
# =========================================================

class ErrorReport:
    """Thread-safe collector of every problem encountered during a run."""

    COLUMNS = ["timestamp", "severity", "stage", "target", "error_type", "message", "detail"]

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.entries: list[dict] = []

    def add(
        self, severity: str, stage: str, target: str, error: Any,
        with_trace: bool = False,
    ) -> None:
        error_type, detail = "", ""
        if isinstance(error, BaseException):
            error_type = type(error).__name__
            message = str(error) or error_type
            response = getattr(error, "response", None)
            status = getattr(response, "status_code", None)
            if status:
                message = f"HTTP {status}: {message}"
            if with_trace:
                detail = "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                )[-1500:]
        else:
            message = str(error)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "severity": severity,
            "stage": stage,
            "target": clean_text(target)[:300],
            "error_type": error_type,
            "message": clean_text(message)[:500],
            "detail": detail,
        }
        with self._lock:
            self.entries.append(entry)

    def error(self, stage: str, target: str, error: Any, with_trace: bool = False) -> None:
        self.add("ERROR", stage, target, error, with_trace)

    def warning(self, stage: str, target: str, error: Any) -> None:
        self.add("WARNING", stage, target, error)

    def count(self, severity: str) -> int:
        with self._lock:
            return sum(1 for e in self.entries if e["severity"] == severity)

    def write(self, path: Path, logger: logging.Logger) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=self.COLUMNS)
                writer.writeheader()
                with self._lock:
                    for entry in self.entries:
                        writer.writerow({c: _sanitize_cell(entry.get(c, "")) for c in self.COLUMNS})
            return True
        except OSError as exc:
            logger.warning("Could not write error report to %s: %s", path, exc)
            return False

    def log_summary(self, logger: logging.Logger, path: Path) -> None:
        with self._lock:
            entries = list(self.entries)
        errors = sum(1 for e in entries if e["severity"] == "ERROR")
        warnings = len(entries) - errors

        logger.info("=" * 60)
        logger.info("ERROR REPORT SUMMARY")
        logger.info("Errors: %d | Warnings: %d", errors, warnings)
        if not entries:
            logger.info("No problems recorded.")
        else:
            groups = Counter((e["severity"], e["stage"], e["error_type"] or "-") for e in entries)
            for (severity, stage, error_type), n in groups.most_common(12):
                example = next(
                    e for e in entries
                    if (e["severity"], e["stage"], e["error_type"] or "-") == (severity, stage, error_type)
                )
                logger.info(
                    "  %-7s %-9s %-22s x%-3d e.g. %s -> %s",
                    severity, stage, error_type, n, example["target"][:60], example["message"][:90],
                )
            logger.info("Full report: %s", path)
        logger.info("=" * 60)


# =========================================================
# TEXT / URL HELPERS
# =========================================================

def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def as_text(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, dict):
        return clean_text(value.get("name") or value.get("@value") or "")
    if isinstance(value, list):
        return as_text(value[0]) if value else ""
    return ""


def names_from(value: Any) -> list[str]:
    items = value if isinstance(value, list) else [value]
    names: list[str] = []
    for item in items:
        name = as_text(item)
        if name and name not in names:
            names.append(name)
    return names


def _is_tracking_param(key: str) -> bool:
    key = key.lower()
    return key in TRACKING_PARAMS or key.startswith(TRACKING_PARAM_PREFIXES)


def normalize_url(url: Any) -> str:
    url = clean_text(url)
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return ""

    query = parsed.query
    pairs = parse_qsl(query, keep_blank_values=True)
    kept = [(k, v) for k, v in pairs if not _is_tracking_param(k)]
    if len(kept) != len(pairs):
        query = urlencode(kept)

    return urlunparse((
        parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/",
        parsed.params, query, "",
    ))


def host_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def dedup_key(url: str) -> str:
    normalized = normalize_url(url)
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    key = host_of(normalized) + parsed.path.rstrip("/")
    return f"{key}?{parsed.query}" if parsed.query else key


def is_blocked(url: str, blocked: set[str]) -> bool:
    host = host_of(url)
    return any(host == d or host.endswith("." + d) for d in blocked)


def generate_resource_id(url: str) -> str:
    digest = hashlib.sha1(dedup_key(url).encode("utf-8")).hexdigest()[:16]
    return f"RES_{digest.upper()}"


# =========================================================
# CSV HELPERS
# =========================================================

def read_csv(path: Path, logger: logging.Logger, report: ErrorReport | None = None) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as file:
            rows = []
            for row in csv.DictReader(file):
                cleaned = {
                    key: (value or "").strip()
                    for key, value in row.items()
                    if key is not None and isinstance(value, (str, type(None)))
                }
                if any(cleaned.values()):
                    rows.append(cleaned)
            return rows
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        if report:
            report.warning("csv_read", str(path), exc)
        return []


def _sanitize_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(temporary_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=RESOURCE_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({c: _sanitize_cell(row.get(c, "")) for c in RESOURCE_COLUMNS})
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


# =========================================================
# INPUT DATA
# =========================================================

def _read_terms(
    path: Path, columns: tuple[str, ...], logger: logging.Logger, report: ErrorReport
) -> list[str]:
    if not path.exists():
        report.warning("input", str(path), "Input file not found")
        logger.warning("Input file not found: %s", path)
        return []
    rows = read_csv(path, logger, report)
    terms = []
    for row in rows:
        for column in columns:
            value = clean_text(row.get(column, ""))
            if len(value) >= 2:
                terms.append(value)
                break
    if rows and not terms:
        report.warning("input", str(path), f"No usable values in columns {list(columns)}")
    logger.info("Loaded %d term(s) from %s.", len(terms), path.name)
    return terms


def _unique(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value.lower() not in seen:
            seen.add(value.lower())
            result.append(value)
    return result


def collect_search_terms(
    data_dir: Path, max_terms: int, logger: logging.Logger, report: ErrorReport
) -> list[str]:
    topics = _read_terms(data_dir / "course_topics.csv", ("topic", "name", "title"), logger, report)
    skills = _read_terms(data_dir / "skills.csv", ("name", "skill", "title"), logger, report)
    terms = _unique(t for pair in zip_longest(topics, skills) for t in pair)

    if not terms:
        logger.warning("No topics or skills found. Falling back to course titles.")
        terms = _unique(_read_terms(data_dir / "courses.csv", ("title", "name"), logger, report))

    selected = terms[:max_terms]
    logger.info("Selected %d unique search term(s).", len(selected))
    return selected


# =========================================================
# HTTP INFRASTRUCTURE
# =========================================================

def create_session(user_agent: str, retries: int) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.8",
    })
    retry = Retry(
        total=retries, connect=retries, read=retries, status=retries,
        backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"), respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class DomainThrottle:
    def __init__(self, delay: float) -> None:
        self.delay = max(delay, 0.0)
        self._lock = threading.Lock()
        self._next_slot: dict[str, float] = {}

    def wait(self, domain: str) -> None:
        if self.delay <= 0:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_slot.get(domain, 0.0))
            self._next_slot[domain] = start + self.delay
        if start > now:
            time.sleep(start - now)


class RobotsChecker:
    """Cached robots.txt checks; fails open on any problem."""

    _MISSING = object()

    def __init__(self, session: requests.Session, enabled: bool, timeout: float) -> None:
        self.session, self.enabled, self.timeout = session, enabled, timeout
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}

    def allowed(self, url: str) -> bool:
        if not self.enabled:
            return True
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        with self._lock:
            parser = self._cache.get(origin, self._MISSING)
        if parser is self._MISSING:
            parser = self._load(origin)
            with self._lock:
                self._cache[origin] = parser
        return True if parser is None else parser.can_fetch(BOT_NAME, url)

    def _load(self, origin: str) -> RobotFileParser | None:
        try:
            response = self.session.get(origin + "/robots.txt", timeout=self.timeout)
            if response.status_code != 200:
                return None
            parser = RobotFileParser()
            parser.parse(response.content[:500_000].decode("utf-8", "replace").splitlines())
            return parser
        except Exception:
            return None


@dataclass
class FetchContext:
    session: requests.Session
    throttle: DomainThrottle
    robots: RobotsChecker
    timeout: float
    logger: logging.Logger
    report: ErrorReport


def download_page(
    session: requests.Session, url: str, timeout: float
) -> tuple[str, str, tuple[bytes, str | None] | None]:
    with session.get(url, timeout=timeout, stream=True, allow_redirects=True) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        final_url = normalize_url(response.url) or url

        if "html" not in content_type.lower():
            return final_url, content_type, None

        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            chunks.append(chunk)
            size += len(chunk)
            if size >= MAX_HTML_BYTES:
                break

        encoding = response.encoding if "charset" in content_type.lower() else None
        return final_url, content_type, (b"".join(chunks)[:MAX_HTML_BYTES], encoding)


# =========================================================
# SEARCH
# =========================================================

def create_search_client(report: ErrorReport):
    """Return a search client, or None (recorded in the report) if unavailable."""
    for module_name in ("ddgs", "duckduckgo_search"):  # dynamic import avoids editor warnings
        try:
            module = importlib.import_module(module_name)
            return module.DDGS()
        except ImportError:
            continue
        except Exception as exc:
            report.error("setup", module_name, exc, with_trace=True)
            return None
    report.error(
        "setup", "ddgs",
        "Search package not installed. Install it with: uv add ddgs (or pip install ddgs)",
    )
    return None


def search_resources(
    client, term: str, max_results: int, query_suffix: str, blocked: set[str],
    retries: int, logger: logging.Logger, report: ErrorReport,
) -> list[dict] | None:
    """Results, [] for none found, or None if every attempt failed."""
    query = f"{term} {query_suffix}".strip()
    raw = None

    for attempt in range(1, retries + 2):
        try:
            raw = list(client.text(query, max_results=max_results) or [])
            break
        except Exception as exc:
            if "no results" in str(exc).lower():
                report.warning("search", term, "Search returned no results")
                return []
            if attempt > retries:
                logger.warning("Search failed for '%s': %s", term, exc)
                report.error("search", term, exc)
                return None
            time.sleep((2 ** attempt) + random.uniform(0, 1))

    collected: list[dict] = []
    seen: set[str] = set()
    for result in raw or []:
        if not isinstance(result, dict):
            continue
        url = normalize_url(result.get("href", ""))
        key = dedup_key(url)
        if not url or key in seen or is_blocked(url, blocked):
            continue
        seen.add(key)
        collected.append({
            "title": clean_text(result.get("title", "")),
            "url": url,
            "description": clean_text(result.get("body", "")),
        })
    if not collected:
        report.warning("search", term, "No usable results after filtering")
    return collected


# =========================================================
# METADATA EXTRACTION
# =========================================================

PREFERRED_JSONLD_TYPES = (
    "course", "learningresource", "videoobject", "audioobject", "book",
    "techarticle", "scholarlyarticle", "article", "creativework", "webpage",
)


def _iter_jsonld(data: Any) -> Iterator[dict]:
    queue = [data]
    while queue:
        item = queue.pop(0)
        if isinstance(item, list):
            queue.extend(item)
        elif isinstance(item, dict):
            yield item
            if item.get("@graph"):
                queue.append(item["@graph"])


def extract_jsonld(soup: BeautifulSoup) -> dict:
    best: dict = {}
    best_rank = len(PREFERRED_JSONLD_TYPES)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        for item in _iter_jsonld(data):
            if not (item.get("name") or item.get("headline")):
                continue
            raw_types = item.get("@type", [])
            types = raw_types if isinstance(raw_types, list) else [raw_types]
            ranks = [
                PREFERRED_JSONLD_TYPES.index(t.lower())
                for t in types
                if isinstance(t, str) and t.lower() in PREFERRED_JSONLD_TYPES
            ]
            if ranks and min(ranks) < best_rank:
                best, best_rank = item, min(ranks)
    return best


def get_meta_content(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        for attribute in ("name", "property"):
            tag = soup.find("meta", attrs={attribute: name})
            if tag and tag.get("content"):
                return clean_text(tag["content"])
    return ""


_CC_PATTERN = re.compile(
    r"creativecommons\.org/(licenses|publicdomain)/([a-z0-9\-]+)(?:/(\d+\.\d+))?", re.I
)


def parse_license_url(url: str) -> tuple[str, str]:
    match = _CC_PATTERN.search(url)
    if not match:
        return "", ""
    kind, code, version = match.group(1).lower(), match.group(2).lower(), match.group(3) or ""
    if kind == "publicdomain":
        return ("CC0" if code == "zero" else "Public Domain Mark"), version
    return f"CC {code.upper()}", version


def extract_license_metadata(
    soup: BeautifulSoup, jsonld: dict, base_url: str
) -> tuple[str, str, str]:
    name = url = ""
    value = jsonld.get("license")
    value = value[0] if isinstance(value, list) and value else value
    if isinstance(value, dict):
        name = clean_text(value.get("name", ""))
        url = clean_text(value.get("url", "") or value.get("@id", ""))
    elif isinstance(value, str):
        if value.startswith(("http://", "https://")):
            url = clean_text(value)
        else:
            name = clean_text(value)

    if not name:
        name = get_meta_content(soup, "license", "dcterms.rights", "rights")

    if not url:
        for tag in soup.find_all(["a", "link"], href=True):
            rel = tag.get("rel") or []
            rel = rel.split() if isinstance(rel, str) else rel
            if "license" in (r.lower() for r in rel):
                url = clean_text(tag["href"])
                break

    if url:
        url = urljoin(base_url, url)
        if not normalize_url(url):
            url = ""

    version = ""
    if url:
        derived_name, version = parse_license_url(url)
        name = name or derived_name
    return name, version, url


_ISO_DURATION = re.compile(
    r"^P(?:(?P<w>\d+(?:\.\d+)?)W)?(?:(?P<d>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<h>\d+(?:\.\d+)?)H)?(?:(?P<m>\d+(?:\.\d+)?)M)?(?:(?P<s>\d+(?:\.\d+)?)S)?)?$",
    re.I,
)


def extract_duration(jsonld: dict) -> tuple[str, str]:
    raw = jsonld.get("timeRequired") or jsonld.get("duration") or ""
    if not isinstance(raw, str):
        return "", ""
    match = _ISO_DURATION.match(raw.strip())
    if not match or not any(match.groupdict().values()):
        return "", ""

    p = {k: float(v) if v else 0.0 for k, v in match.groupdict().items()}
    minutes = p["w"] * 10080 + p["d"] * 1440 + p["h"] * 60 + p["m"] + p["s"] / 60
    if minutes <= 0:
        return "", ""
    total = round(minutes)
    if total >= 1440 and total % 1440 == 0:
        return str(total // 1440), "days"
    if total >= 60 and total % 60 == 0:
        return str(total // 60), "hours"
    return str(max(total, 1)), "minutes"


def detect_format(url: str, content_type: str) -> str:
    extension = Path(urlparse(url).path.lower()).suffix.lstrip(".")
    if extension in FILE_EXTENSIONS:
        fmt = FILE_EXTENSIONS[extension]
    else:
        ct = content_type.lower()
        if "pdf" in ct:
            fmt = "pdf"
        elif "video" in ct:
            fmt = "video"
        elif "audio" in ct:
            fmt = "audio"
        elif "html" in ct:
            fmt = "webpage"
        else:
            fmt = "unknown"
    return "video" if fmt == "webpage" and host_of(url) in VIDEO_HOSTS else fmt


# =========================================================
# FETCH ONE RESOURCE
# =========================================================

def fetch_resource_metadata(resource: dict, ctx: FetchContext) -> dict:
    """Never raises: on any failure it returns search-result metadata and records why."""
    url = resource["url"]
    metadata = {
        "url": url,
        "title": resource.get("title", ""),
        "provider": host_of(url),
        "licence_name": "", "licence_version": "", "licence_url": "",
        "fmt": detect_format(url, ""),
        "duration_value": "", "duration_unit": "",
        "instructor": "", "host_institute": "",
        "description": resource.get("description", ""),
        "source_note": "Metadata obtained from search results.",
    }

    try:
        if not ctx.robots.allowed(url):
            metadata["source_note"] = "Page not fetched (robots.txt). Metadata from search results only."
            ctx.report.warning("fetch", url, "Disallowed by robots.txt")
            return metadata

        ctx.throttle.wait(host_of(url))
        final_url, content_type, page = download_page(ctx.session, url, ctx.timeout)

        metadata.update(url=final_url, provider=host_of(final_url),
                        fmt=detect_format(final_url, content_type))

        if page is None:
            metadata["source_note"] = "Not an HTML document. Metadata from search results."
            return metadata

        body, encoding = page
        soup = BeautifulSoup(body, "html.parser", from_encoding=encoding)
        jsonld = extract_jsonld(soup)

        title = (
            as_text(jsonld.get("name") or jsonld.get("headline"))
            or get_meta_content(soup, "og:title", "twitter:title")
            or (clean_text(soup.title.get_text()) if soup.title else "")
        )
        if title:
            metadata["title"] = title

        description = as_text(jsonld.get("description")) or get_meta_content(
            soup, "description", "og:description", "twitter:description"
        )
        if description:
            metadata["description"] = description

        metadata["host_institute"] = "; ".join(
            names_from(jsonld.get("publisher") or jsonld.get("provider")))
        metadata["instructor"] = "; ".join(
            names_from(jsonld.get("author") or jsonld.get("creator") or jsonld.get("instructor")))

        (metadata["licence_name"], metadata["licence_version"],
         metadata["licence_url"]) = extract_license_metadata(soup, jsonld, final_url)
        metadata["duration_value"], metadata["duration_unit"] = extract_duration(jsonld)

        metadata["source_note"] = (
            "Metadata extracted from the resource webpage. "
            "Licence information, if present, requires manual verification."
        )

    except requests.RequestException as exc:
        ctx.logger.debug("Could not fetch %s: %s", url, exc)
        ctx.report.warning("fetch", url, exc)
        metadata["source_note"] = (
            f"Could not fetch webpage ({type(exc).__name__}). Metadata from search results."
        )
    except Exception as exc:
        ctx.logger.warning("Metadata extraction failed for %s: %s", url, exc)
        ctx.report.error("parse", url, exc, with_trace=True)
        metadata["source_note"] = (
            f"Metadata extraction error ({type(exc).__name__}). Metadata from search results."
        )
    return metadata


def create_resource_record(metadata: dict, retrieved_on: str) -> dict:
    url = metadata["url"]
    return {
        "id": generate_resource_id(url),
        "title": truncate(clean_text(metadata.get("title", "")), MAX_TITLE_CHARS),
        "provider": metadata.get("provider", ""),
        "licence_name": metadata.get("licence_name", ""),
        "licence_version": metadata.get("licence_version", ""),
        "licence_url": metadata.get("licence_url", ""),
        "licence_verified_on": "",
        "fmt": metadata.get("fmt", "unknown"),
        "duration_value": metadata.get("duration_value", ""),
        "duration_unit": metadata.get("duration_unit", ""),
        "url": url,
        "instructor": metadata.get("instructor", ""),
        "host_institute": metadata.get("host_institute", ""),
        "description": truncate(clean_text(metadata.get("description", "")), MAX_DESCRIPTION_CHARS),
        "source_url": url,
        "retrieved_on": retrieved_on,
        "source_type": "web_discovery_candidate",
        "source_note": metadata.get("source_note", ""),
        "verification_status": "needs_review",
        "verified_on": "",
        "verified_by": "",
    }


# =========================================================
# MERGING WITH EXISTING OUTPUT
# =========================================================

def _is_reviewed(row: dict) -> bool:
    status = row.get("verification_status", "").strip().lower()
    return status not in ("", "needs_review") or bool(
        row.get("verified_by") or row.get("verified_on") or row.get("licence_verified_on")
    )


def merge_with_existing(existing: list[dict], new_records: list[dict]) -> tuple[list[dict], dict]:
    merged: dict[str, dict] = {}
    for row in existing:
        key = dedup_key(row.get("url", ""))
        if key:
            merged[key] = row

    stats = {"added": 0, "refreshed": 0, "kept_reviewed": 0}
    for record in new_records:
        key = dedup_key(record["url"])
        old = merged.get(key)
        if old is None:
            stats["added"] += 1
            merged[key] = record
        elif _is_reviewed(old):
            stats["kept_reviewed"] += 1
        else:
            stats["refreshed"] += 1
            record["id"] = old.get("id") or record["id"]
            merged[key] = record
    stats["total"] = len(merged)
    return list(merged.values()), stats


def save_output(path: Path, rows: list[dict], logger: logging.Logger, report: ErrorReport) -> Path | None:
    """Write the CSV; if that fails, try a timestamped fallback file in the working directory."""
    try:
        write_csv(path, rows)
        return path
    except OSError as exc:
        report.error("write", str(path), exc)
        logger.error("Could not write %s: %s", path, exc)

    fallback = Path.cwd() / f"resources_web_candidates_{datetime.now():%Y%m%d_%H%M%S}.csv"
    try:
        write_csv(fallback, rows)
        report.warning("write", str(fallback), "Results saved to fallback location instead")
        logger.warning("Saved results to fallback file: %s", fallback)
        return fallback
    except OSError as exc:
        report.error("write", str(fallback), exc)
        return None


# =========================================================
# PIPELINE
# =========================================================

def _run(s: Settings, logger: logging.Logger, report: ErrorReport) -> int:
    if not s.data_dir.is_dir():
        report.error("input", str(s.data_dir), "Input directory does not exist or is not a directory")
        logger.error("Input directory not found: %s", s.data_dir)
        return 0

    terms = collect_search_terms(s.data_dir, s.max_terms, logger, report)
    if not terms:
        report.error("input", str(s.data_dir),
                     "No search terms found (need course_topics.csv, skills.csv or courses.csv). "
                     "Output left untouched.")
        logger.error("No search terms found. Output left untouched.")
        return 0

    blocked = BLOCKED_DOMAINS | {d.lower().lstrip(".") for d in s.block_domains}
    client = create_search_client(report)
    if client is None:
        logger.error("Search client unavailable - see error report.")
        return 0

    retrieved_on = datetime.now(timezone.utc).date().isoformat()

    # ---------------- Search ----------------
    discovered: dict[str, dict] = {}
    failed_searches = 0
    for index, term in enumerate(terms, start=1):
        logger.info("[%d/%d] Searching: %s", index, len(terms), term)
        try:
            results = search_resources(client, term, s.max_results, s.query_suffix,
                                       blocked, s.retries, logger, report)
        except Exception as exc:
            report.error("search", term, exc, with_trace=True)
            results = None
        if results is None:
            failed_searches += 1
            results = []
        logger.info("Found %d usable result(s).", len(results))
        for resource in results:
            discovered.setdefault(dedup_key(resource["url"]), resource)
        if index < len(terms) and s.delay > 0:
            time.sleep(s.delay + random.uniform(0, s.delay / 2))

    logger.info("Unique URLs discovered: %d", len(discovered))
    if not discovered:
        msg = (f"All {failed_searches} search(es) failed (rate limit or network?)"
               if failed_searches else "Searches returned no results")
        report.error("search", "ALL", msg + ". Output left untouched.")
        return 0

    # ---------------- Fetch ----------------
    session = create_session(s.user_agent, s.retries)
    ctx = FetchContext(
        session=session, throttle=DomainThrottle(s.delay),
        robots=RobotsChecker(session, s.respect_robots, min(s.timeout, 6)),
        timeout=s.timeout, logger=logger, report=report,
    )

    resources = list(discovered.values())
    by_index: dict[int, dict] = {}
    interrupted = False

    try:
        with ThreadPoolExecutor(max_workers=s.workers) as executor:
            futures = {executor.submit(fetch_resource_metadata, r, ctx): i
                       for i, r in enumerate(resources)}
            try:
                for done, future in enumerate(as_completed(futures), start=1):
                    i = futures[future]
                    try:
                        metadata = future.result()
                        by_index[i] = create_resource_record(metadata, retrieved_on)
                        logger.info("Fetched [%d/%d]: %s", done, len(resources), metadata["url"])
                    except Exception as exc:
                        report.error("record", resources[i]["url"], exc, with_trace=True)
            except KeyboardInterrupt:
                interrupted = True
                for future in futures:
                    future.cancel()
                raise
    finally:
        if by_index:
            records: dict[str, dict] = {}
            for i in sorted(by_index):
                records.setdefault(dedup_key(by_index[i]["url"]), by_index[i])

            existing = [] if s.fresh else read_csv(s.output_path, logger, report)
            final_records, stats = merge_with_existing(existing, list(records.values()))
            saved = save_output(s.output_path, final_records, logger, report)

            logger.info("=" * 60)
            logger.info("RESOURCE DISCOVERY SUMMARY%s", " (PARTIAL - interrupted)" if interrupted else "")
            logger.info("Search terms: %d (%d failed)", len(terms), failed_searches)
            logger.info("Unique URLs discovered: %d", len(discovered))
            logger.info("New: %d | refreshed: %d | reviewed rows preserved: %d | total rows: %d",
                        stats["added"], stats["refreshed"], stats["kept_reviewed"], stats["total"])
            logger.info("Output: %s", saved or "NOT WRITTEN (see error report)")

    return len(by_index)


@dataclass
class RunResult:
    count: int
    report: ErrorReport
    interrupted: bool = False


def run_discovery(settings: Settings, logger: logging.Logger) -> RunResult:
    """Run the pipeline. Never raises (except nothing); always writes the error report."""
    s = settings.normalize()
    report = ErrorReport()
    count, interrupted = 0, False
    try:
        count = _run(s, logger, report)
    except KeyboardInterrupt:
        interrupted = True
        report.warning("run", "", "Interrupted by user; partial results saved if any")
    except Exception as exc:
        logger.exception("Unexpected failure in resource discovery.")
        report.error("run", "", exc, with_trace=True)
    finally:
        report.write(s.report_path, logger)
        report.log_summary(logger, s.report_path)
    return RunResult(count, report, interrupted)


def discover_resources(
    data_dir: Path = DEFAULT_DATA_DIR,
    output_path: Path = DEFAULT_OUTPUT,
    max_terms: int = 30,
    max_results: int = 5,
    delay: float = 1.0,
    logger: logging.Logger | None = None,
    **options: Any,
) -> int:
    """Backward-compatible entry point (same signature as the original script).

    Returns the number of candidate records processed. Extra keyword options match
    the Settings fields (workers, timeout, retries, respect_robots, fresh, ...).
    """
    logger = logger or setup_logger()
    settings = Settings(data_dir=data_dir, output_path=output_path, max_terms=max_terms,
                        max_results=max_results, delay=delay, **options)
    result = run_discovery(settings, logger)
    if result.interrupted:
        raise KeyboardInterrupt
    return result.count


# =========================================================
# CLI
# =========================================================

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Discover learning resources from course topics and skills "
                    "and extract webpage metadata (lenient, with error report)."
    )
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--report", type=Path, default=None,
                   help="Error report CSV path (default: <out>_error_report.csv).")
    p.add_argument("--max-terms", type=int, default=30)
    p.add_argument("--max-results", type=int, default=5)
    p.add_argument("--delay", type=float, default=1.0,
                   help="Seconds between searches and minimum gap per domain.")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=float, default=REQUEST_TIMEOUT)
    p.add_argument("--retries", type=int, default=1)
    p.add_argument("--query-suffix", default=DEFAULT_QUERY_SUFFIX)
    p.add_argument("--block-domain", action="append", default=[], metavar="DOMAIN")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    p.add_argument("--respect-robots", action="store_true", help="Honour robots.txt (off by default).")
    p.add_argument("--fresh", action="store_true",
                   help="Ignore and overwrite existing output (discards review status!).")
    p.add_argument("--strict", action="store_true",
                   help="Exit with code 1 if any ERROR-level problem was recorded.")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger = setup_logger(args.verbose)

    settings = Settings(
        data_dir=args.data_dir, output_path=args.out, report_path=args.report,
        max_terms=args.max_terms, max_results=args.max_results, delay=args.delay,
        workers=args.workers, timeout=args.timeout, retries=args.retries,
        query_suffix=args.query_suffix, block_domains=args.block_domain,
        user_agent=args.user_agent, respect_robots=args.respect_robots, fresh=args.fresh,
    )
    logger.info("Starting learning resource discovery.")
    result = run_discovery(settings, logger)

    if result.interrupted:
        return 130
    logger.info("Resource discovery completed. %d candidate record(s) processed.", result.count)
    if args.strict and result.report.count("ERROR"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())