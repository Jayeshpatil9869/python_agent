"""Filesystem helpers."""

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def url_to_slug(url: str) -> str:
    """Convert URL to a filesystem-safe directory name."""
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    host = re.sub(r"^www\.", "", host)
    slug = re.sub(r"[^a-zA-Z0-9.-]", "-", host.lower())
    return slug.strip("-") or "website"


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
