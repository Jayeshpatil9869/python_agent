"""Screenshot capture."""

from pathlib import Path

from utils.filesystem import ensure_dir


async def capture_full_page(page, path: Path) -> Path:
    ensure_dir(path.parent)
    await page.screenshot(path=str(path), full_page=True)
    return path


async def capture_viewport(page, path: Path) -> Path:
    ensure_dir(path.parent)
    await page.screenshot(path=str(path), full_page=False)
    return path
