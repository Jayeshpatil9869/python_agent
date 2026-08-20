"""Aggregate per-page motion into site_motion.json payloads."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from intelligence.motion_intelligence import page_motion_snapshot
from intelligence.schema import WebsiteIntelligence
from utils.filesystem import write_json


def _page_slug(url: str, index: int) -> str:
    path = urlparse(url).path.strip("/") or "home"
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in path)[:48]
    return safe or f"page-{index}"


def persist_motion_artifacts(website: WebsiteIntelligence, data_dir: Path) -> dict:
    """
    Write data/motion/pages/*.json and data/motion/site_motion.json.

    Returns the site_motion dict (also suitable for experience scoring).
    """
    motion_dir = data_dir / "motion"
    pages_dir = motion_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    page_files: list[str] = []
    page_snapshots: list[dict] = []
    for i, page in enumerate(website.pages or []):
        snap = page_motion_snapshot(page)
        slug = _page_slug(page.url, i)
        rel = f"motion/pages/{slug}.json"
        write_json(pages_dir / f"{slug}.json", snap)
        page_files.append(rel)
        page_snapshots.append(snap)

    mi = website.motion_intelligence
    site_motion = {
        "site": website.url,
        "pages": page_files,
        "page_count": len(page_snapshots),
        "aggregation": "site_wide",
        "preloader": mi.preloader.model_dump(mode="json") if mi else {},
        "page_load": mi.page_load.model_dump(mode="json") if mi else {},
        "hero_animation": mi.hero_animation if mi else {},
        "scroll_system": mi.scroll_system if mi else {},
        "scrolltrigger_analysis_count": len(mi.scrolltrigger_analysis) if mi else 0,
        "parallax_count": len(mi.parallax) if mi else 0,
        "pinning_count": len(mi.pinning) if mi else 0,
        "horizontal_scroll_count": len(mi.horizontal_scroll) if mi else 0,
        "hover_count": len(mi.hover_motion) if mi else 0,
        "interaction_count_sitewide": sum(len(p.interactions) for p in (website.pages or [])),
        "cursor": mi.cursor.model_dump(mode="json") if mi else {},
        "gsap_status": mi.gsap_status if mi else "UNKNOWN",
        "scrolltrigger_status": mi.scrolltrigger_status if mi else "UNKNOWN",
        "motion_hierarchy": mi.motion_hierarchy if mi else {},
        "complete_timeline": mi.complete_timeline if mi else [],
        "confidence": mi.confidence.value if mi else "UNKNOWN",
    }
    write_json(motion_dir / "site_motion.json", site_motion)
    write_json(data_dir / "motion.json", mi.model_dump(mode="json") if mi else {})
    return site_motion
