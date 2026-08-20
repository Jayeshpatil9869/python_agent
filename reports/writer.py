"""Report writer utilities."""

from pathlib import Path

from utils.filesystem import write_text


def write_report(path: Path, content: str) -> None:
    write_text(path, content)
