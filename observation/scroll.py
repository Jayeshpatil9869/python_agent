"""Scroll behavior observation with ScrollTrigger-like / parallax / pin / horizontal detection."""

import json
import logging
from pathlib import Path

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import ColorTransition, ScrollMotionFinding
from observation.screenshot import capture_viewport

logger = logging.getLogger(__name__)

TRACKED_SELECTORS = (
    "header, .hero, [class*='hero'], section, h1, h2, img, video, "
    "[data-parallax], [class*='pin'], [class*='horizontal'], [class*='gallery']"
)

SCROLL_SNAPSHOT_JS = """
(selectors) => {
    const tracked = Array.from(document.querySelectorAll(selectors)).slice(0, 14);
    const elements = tracked.map(el => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        let scale = 1;
        const m = s.transform.match(/matrix\\(([^)]+)\\)/);
        if (m) {
            const parts = m[1].split(',').map(Number);
            scale = Math.sqrt(parts[0] * parts[0] + parts[1] * parts[1]);
        }
        return {
            key: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
                (el.className ? '.' + String(el.className).split(' ')[0] : ''),
            tag: el.tagName.toLowerCase(),
            top: Math.round(r.top),
            left: Math.round(r.left),
            width: Math.round(r.width),
            height: Math.round(r.height),
            transform: s.transform,
            opacity: s.opacity,
            scale: Math.round(scale * 1000) / 1000,
            clipPath: s.clipPath,
            filter: s.filter,
            position: s.position,
            backgroundColor: s.backgroundColor,
        };
    });
    const sticky = Array.from(document.querySelectorAll('*')).filter(el => {
        const p = getComputedStyle(el).position;
        return (p === 'sticky' || p === 'fixed') && el.getBoundingClientRect().height > 40;
    }).slice(0, 8).map(el => ({
        key: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
        position: getComputedStyle(el).position,
        top: Math.round(el.getBoundingClientRect().top),
    }));
    return {
        scrollY: window.scrollY,
        bodyBg: getComputedStyle(document.body).backgroundColor,
        htmlBg: getComputedStyle(document.documentElement).backgroundColor,
        elements,
        sticky,
    };
}
"""

DEEP_SCROLL_PERCENTS = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100]
FAST_SCROLL_PERCENTS = [0, 25, 50, 75, 100]


async def observe_scroll(
    page,
    output_dir: Path,
    steps: int = 11,
    deep: bool = True,
) -> tuple[list[dict], list[ScrollMotionFinding], list[ColorTransition]]:
    observations: list[dict] = []
    findings: list[ScrollMotionFinding] = []
    color_transitions: list[ColorTransition] = []
    runtime_dir = output_dir / "runtime" / "scroll"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    percents = DEEP_SCROLL_PERCENTS if deep else FAST_SCROLL_PERCENTS
    if steps and not deep:
        percents = [int(i * 100 / (steps - 1)) for i in range(steps)] if steps > 1 else [0]

    try:
        scroll_height = await page.evaluate("() => document.documentElement.scrollHeight")
        viewport_height = await page.evaluate("() => window.innerHeight")
        max_scroll = max(0, scroll_height - viewport_height)

        history: dict[str, list[dict]] = {}
        prev_bg = None
        prev_scroll = 0

        for pct in percents:
            scroll_y = int(max_scroll * (pct / 100))
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await page.wait_for_timeout(350)

            snapshot = await page.evaluate(SCROLL_SNAPSHOT_JS, TRACKED_SELECTORS)
            bg = snapshot.get("bodyBg") or snapshot.get("htmlBg") or ""

            if prev_bg and bg and bg != prev_bg:
                color_transitions.append(
                    ColorTransition(
                        from_scroll=prev_scroll,
                        to_scroll=snapshot.get("scrollY", scroll_y),
                        from_color=prev_bg,
                        to_color=bg,
                        transition_type="section-based",
                        confidence=ConfidenceLevel.OBSERVED,
                        evidence=[f"runtime/scroll/scroll-{pct:03d}.json"],
                    )
                )
            prev_bg = bg
            prev_scroll = snapshot.get("scrollY", scroll_y)

            for el in snapshot.get("elements", []):
                key = el.get("key", "")
                history.setdefault(key, []).append(
                    {
                        "scroll_y": snapshot.get("scrollY", scroll_y),
                        "pct": pct,
                        **el,
                    }
                )

            screenshot_path = output_dir / "screenshots" / "scroll" / f"scroll-{pct:03d}.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            await capture_viewport(page, screenshot_path)

            observation = {
                "percent": pct,
                "scroll_y": snapshot.get("scrollY", scroll_y),
                "body_bg": bg,
                "sticky_elements": snapshot.get("sticky", []),
                "element_count": len(snapshot.get("elements", [])),
                "screenshot": f"screenshots/scroll/scroll-{pct:03d}.png",
            }
            observations.append(observation)
            (runtime_dir / f"scroll-{pct:03d}.json").write_text(
                json.dumps({"observation": observation, "snapshot": snapshot}, indent=2),
                encoding="utf-8",
            )

        findings = _analyze_motion_history(history, viewport_height)
        await page.evaluate("window.scrollTo(0, 0)")

        (runtime_dir / "findings.json").write_text(
            json.dumps([f.model_dump(mode="json") for f in findings], indent=2),
            encoding="utf-8",
        )
        (runtime_dir / "color_transitions.json").write_text(
            json.dumps([c.model_dump(mode="json") for c in color_transitions], indent=2),
            encoding="utf-8",
        )
        logger.info(
            "[SCROLL] %d steps, %d findings, %d color transitions",
            len(observations),
            len(findings),
            len(color_transitions),
        )
    except Exception as exc:
        logger.warning("[SCROLL] observation failed: %s", exc)
        observations.append({"error": str(exc)})

    return observations, findings, color_transitions


def _analyze_motion_history(
    history: dict[str, list[dict]],
    viewport_height: int,
) -> list[ScrollMotionFinding]:
    findings: list[ScrollMotionFinding] = []

    for key, samples in history.items():
        if len(samples) < 3:
            continue

        scroll_deltas = []
        top_deltas = []
        left_deltas = []
        opacity_vals = []
        scale_vals = []
        clip_vals = []

        for i in range(1, len(samples)):
            sd = samples[i]["scroll_y"] - samples[i - 1]["scroll_y"]
            if sd <= 0:
                continue
            scroll_deltas.append(sd)
            top_deltas.append(samples[i]["top"] - samples[i - 1]["top"])
            left_deltas.append(samples[i]["left"] - samples[i - 1]["left"])
            opacity_vals.append(float(samples[i].get("opacity") or 1))
            scale_vals.append(float(samples[i].get("scale") or 1))
            clip_vals.append(samples[i].get("clipPath") or "none")

        if not scroll_deltas:
            continue

        avg_scroll = sum(scroll_deltas) / len(scroll_deltas)
        avg_top = sum(top_deltas) / len(top_deltas)
        avg_left = sum(abs(x) for x in left_deltas) / len(left_deltas)
        ratio = avg_top / avg_scroll if avg_scroll else 0

        positions = {s.get("position") for s in samples}
        sticky_like = "sticky" in positions or "fixed" in positions

        # Pin: element top stays near constant while scroll advances significantly
        top_variance = max(s["top"] for s in samples) - min(s["top"] for s in samples)
        scroll_range = samples[-1]["scroll_y"] - samples[0]["scroll_y"]
        pinned = sticky_like or (scroll_range > viewport_height and top_variance < 40)

        # Horizontal: left moves while scrolling vertically
        horizontal = avg_left > 20 and scroll_range > 100

        # Parallax: top moves slower/faster than scroll
        parallax = abs(ratio + 1) > 0.25 and abs(ratio) < 0.95 and not pinned

        # Scroll-linked opacity / scale / clip
        opacity_changed = max(opacity_vals) - min(opacity_vals) > 0.15 if opacity_vals else False
        scale_changed = max(scale_vals) - min(scale_vals) > 0.05 if scale_vals else False
        clip_changed = len(set(clip_vals)) > 1

        classifications: list[tuple[str, ConfidenceLevel]] = []
        if pinned:
            classifications.append(("PINNED", ConfidenceLevel.OBSERVED))
        if horizontal:
            classifications.append(("HORIZONTAL_SCROLL", ConfidenceLevel.OBSERVED))
        if parallax:
            classifications.append(("PARALLAX", ConfidenceLevel.OBSERVED))
        if opacity_changed:
            classifications.append(("SCROLL_FADE", ConfidenceLevel.OBSERVED))
        if scale_changed:
            classifications.append(("SCROLL_LINKED_SCALE", ConfidenceLevel.OBSERVED))
        if clip_changed:
            classifications.append(("SCROLL_CLIP_REVEAL", ConfidenceLevel.OBSERVED))
        if abs(avg_top) > 5 and not pinned and not parallax:
            classifications.append(("SCROLL_TRANSLATE", ConfidenceLevel.OBSERVED))

        scrub = "YES" if (opacity_changed or scale_changed or parallax or horizontal) else "UNKNOWN"

        for classification, conf in classifications:
            findings.append(
                ScrollMotionFinding(
                    element=key,
                    classification=classification,
                    scroll_start=samples[0]["scroll_y"],
                    scroll_end=samples[-1]["scroll_y"],
                    property_changes={
                        "avg_top_delta": round(avg_top, 2),
                        "avg_left_delta": round(avg_left, 2),
                        "parallax_ratio": round(ratio, 3),
                        "opacity_range": [min(opacity_vals), max(opacity_vals)] if opacity_vals else [],
                        "scale_range": [min(scale_vals), max(scale_vals)] if scale_vals else [],
                    },
                    scrub=scrub,
                    pin="YES" if pinned else "NO",
                    parallax_ratio=round(ratio, 3) if classification == "PARALLAX" else None,
                    confidence=conf,
                    evidence=["runtime/scroll/findings.json", f"element:{key}"],
                )
            )

    return findings
