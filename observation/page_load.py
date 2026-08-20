"""Page-load choreography observation."""

import json
import logging
from pathlib import Path

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import PageLoadTimeline

logger = logging.getLogger(__name__)

ELEMENT_SNAPSHOT_JS = """
() => {
    const pick = (sel) => document.querySelector(sel);
    const snap = (el) => {
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return {
            key: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
                (el.className ? '.' + String(el.className).split(' ')[0] : ''),
            opacity: s.opacity,
            transform: s.transform,
            visibility: s.visibility,
            top: Math.round(r.top),
            height: Math.round(r.height),
            clipPath: s.clipPath,
            filter: s.filter,
        };
    };
    return {
        readyState: document.readyState,
        nav: snap(pick('nav, header nav, [role="navigation"]')),
        hero: snap(pick('.hero, [class*="hero"], main > section:first-child, section:first-of-type')),
        h1: snap(pick('h1')),
        cta: snap(pick('a.btn, .cta, button, a[class*="btn"]')),
        media: snap(pick('.hero img, .hero video, [class*="hero"] img, [class*="hero"] video, main img')),
    };
}
"""


def _changed(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    return any(a.get(k) != b.get(k) for k in ("opacity", "transform", "top", "clipPath", "visibility"))


async def observe_page_load(
    page,
    output_dir: Path,
    sample_ms: int = 100,
    max_samples: int = 20,
) -> PageLoadTimeline:
    """Sample hero/nav/CTA states after load to reconstruct page-load timeline."""
    timeline = PageLoadTimeline()
    runtime_dir = output_dir / "runtime" / "page-load"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    phases: list[dict] = []

    logger.info("[PAGE-LOAD] observation started")
    try:
        first = None
        last = None
        for i in range(max_samples):
            t = i * sample_ms
            snap = await page.evaluate(ELEMENT_SNAPSHOT_JS)
            entry = {"t": t, **snap}
            phases.append(entry)
            (runtime_dir / f"t-{t:04d}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
            if first is None:
                first = snap
            last = snap
            await page.wait_for_timeout(sample_ms)

        hero_anim: dict = {"status": "NOT_OBSERVED"}
        nav_anim: dict = {"status": "NOT_OBSERVED"}

        if first and last:
            if _changed(first.get("h1"), last.get("h1")) or _changed(first.get("hero"), last.get("hero")):
                hero_anim = {
                    "status": "OBSERVED",
                    "element": (last.get("h1") or last.get("hero") or {}).get("key", "hero"),
                    "initial": first.get("h1") or first.get("hero"),
                    "final": last.get("h1") or last.get("hero"),
                    "trigger": "page_load",
                    "duration_status": "ESTIMATED",
                    "duration_ms": sample_ms * (max_samples - 1),
                }
            if _changed(first.get("nav"), last.get("nav")):
                nav_anim = {
                    "status": "OBSERVED",
                    "element": (last.get("nav") or {}).get("key", "nav"),
                    "initial": first.get("nav"),
                    "final": last.get("nav"),
                    "trigger": "page_load",
                    "duration_status": "ESTIMATED",
                }

            # Detect when opacity reaches ~1 for h1
            reveal_t = None
            for p in phases:
                h1 = p.get("h1") or {}
                if h1 and float(h1.get("opacity") or 0) >= 0.99:
                    reveal_t = p["t"]
                    break
            if reveal_t is not None and hero_anim.get("status") == "OBSERVED":
                hero_anim["reveal_at_ms"] = reveal_t
                hero_anim["duration_status"] = "OBSERVED"

        timeline.phases = [
            {
                "t": p["t"],
                "readyState": p.get("readyState"),
                "h1_opacity": (p.get("h1") or {}).get("opacity"),
                "nav_opacity": (p.get("nav") or {}).get("opacity"),
            }
            for p in phases
        ]
        timeline.hero_animation = hero_anim
        timeline.navigation_animation = nav_anim
        timeline.total_duration_ms = sample_ms * (max_samples - 1)
        timeline.duration_status = "ESTIMATED"
        timeline.evidence = [
            "runtime/page-load/t-0000.json",
            f"runtime/page-load/t-{sample_ms * (max_samples - 1):04d}.json",
        ]

        (runtime_dir / "summary.json").write_text(
            timeline.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.info(
            "[PAGE-LOAD] hero=%s nav=%s",
            hero_anim.get("status"),
            nav_anim.get("status"),
        )
    except Exception as exc:
        logger.warning("[PAGE-LOAD] failed: %s", exc)
        timeline.evidence = [str(exc)]

    return timeline
