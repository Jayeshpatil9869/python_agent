"""URL normalization and filtering utilities."""

import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "_ga",
    "ref",
}

SKIP_SCHEMES = {"mailto", "tel", "javascript", "data", "blob", "ftp"}
SKIP_EXTENSIONS = {
    ".pdf",
    ".zip",
    ".rar",
    ".exe",
    ".dmg",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".webp",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".css",
    ".js",
}


def normalize_url(url: str, base: str | None = None) -> str | None:
    """Normalize and clean a URL."""
    if not url or url.startswith("#"):
        return None

    if base:
        url = urljoin(base, url)

    parsed = urlparse(url.strip())
    if parsed.scheme and parsed.scheme.lower() in SKIP_SCHEMES:
        return None

    if not parsed.scheme:
        if base:
            url = urljoin(base, url)
            parsed = urlparse(url)
        else:
            return None

    if parsed.scheme not in ("http", "https"):
        return None

    path_lower = parsed.path.lower()
    for ext in SKIP_EXTENSIONS:
        if path_lower.endswith(ext):
            return None

    query = parse_qs(parsed.query, keep_blank_values=False)
    filtered = {k: v for k, v in query.items() if k.lower() not in TRACKING_PARAMS}
    clean_query = urlencode(filtered, doseq=True)

    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            parsed.params,
            clean_query,
            "",
        )
    )
    return normalized


def same_origin(url: str, origin: str) -> bool:
    """Check if URL belongs to the same origin."""
    u = urlparse(url)
    o = urlparse(origin)
    return u.scheme == o.scheme and u.netloc == o.netloc


def extract_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def is_valid_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def score_page_importance(url: str) -> int:
    """Heuristic score for page importance."""
    path = urlparse(url).path.lower()
    score = 0
    keywords = {
        "/": 100,
        "about": 80,
        "contact": 75,
        "services": 70,
        "projects": 70,
        "work": 70,
        "portfolio": 65,
        "blog": 60,
        "team": 55,
        "pricing": 50,
    }
    for keyword, value in keywords.items():
        if keyword == "/":
            if path in ("/", ""):
                score = max(score, value)
        elif keyword in path:
            score = max(score, value)
    return score
