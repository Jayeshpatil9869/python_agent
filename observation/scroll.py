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
        let translateX = 0;
        let translateY = 0;
        const m = s.transform.match(/matrix\\(([^)]+)\\)/);
        if (m) {
            const parts = m[1].split(',').map(Number);
            scale = Math.sqrt(parts[0] * parts[0] + parts[1] * parts[1]);
            translateX = parts[4] || 0;
            translateY = parts[5] || 0;
        }
        const parent = el.parentElement;
        let parentScrollLeft = 0;
        let overflowX = 'visible';
        if (parent) {
            parentScrollLeft = parent.scrollLeft || 0;
            overflowX = getComputedStyle(parent).overflowX;
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
            translateX: Math.round(translateX),
            translateY: Math.round(translateY),
            clipPath: s.clipPath,
            filter: s.filter,
            position: s.position,
            backgroundColor: s.backgroundColor,
            parentScrollLeft: parentScrollLeft,
            parentOverflowX: overflowX,
        };
    });
    const sticky = Array.from(document.querySelectorAll('*')).filter(el => {
        const p = getComputedStyle(el).position;
        return (p === 'sticky' || p === 'fixed') && el.getBoundingClientRect().height > 40;
    }).slice(0, 8).map(el => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return {
            key: 'sticky:' + el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
                (el.className ? '.' + String(el.className).split(' ')[0] : ''),
            tag: el.tagName.toLowerCase(),
            top: Math.round(r.top),
            left: Math.round(r.left),
            width: Math.round(r.width),
            height: Math.round(r.height),
            transform: s.transform,
            opacity: s.opacity,
            scale: 1,
            translateX: 0,
            translateY: 0,
            clipPath: s.clipPath,
            filter: s.filter,
            position: s.position,
            backgroundColor: s.backgroundColor,
            parentScrollLeft: 0,
            parentOverflowX: 'visible',
            stickyCandidate: true,
        };
    });
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
            # Also sample first large section background for color transitions
            section_bg = await page.evaluate(
                """() => {
                    const section = document.querySelector('section, main, [class*="section"]');
                    if (!section) return null;
                    return getComputedStyle(section).backgroundColor;
                }"""
            )
            bg = section_bg or snapshot.get("bodyBg") or snapshot.get("htmlBg") or ""

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

            # Feed both tracked elements and sticky candidates into motion history
            for el in list(snapshot.get("elements", [])) + list(snapshot.get("sticky", [])):
                key = el.get("key", "")
                if not key:
                    continue
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
        translate_x_deltas = []
        parent_scroll_left_deltas = []
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
            translate_x_deltas.append(
                float(samples[i].get("translateX") or 0) - float(samples[i - 1].get("translateX") or 0)
            )
            parent_scroll_left_deltas.append(
                float(samples[i].get("parentScrollLeft") or 0)
                - float(samples[i - 1].get("parentScrollLeft") or 0)
            )
            opacity_vals.append(float(samples[i].get("opacity") or 1))
            scale_vals.append(float(samples[i].get("scale") or 1))
            clip_vals.append(samples[i].get("clipPath") or "none")

        if not scroll_deltas:
            continue

        avg_scroll = sum(scroll_deltas) / len(scroll_deltas)
        avg_top = sum(top_deltas) / len(top_deltas)
        avg_left = sum(abs(x) for x in left_deltas) / len(left_deltas)
        avg_tx = sum(abs(x) for x in translate_x_deltas) / len(translate_x_deltas) if translate_x_deltas else 0
        avg_parent_sl = (
            sum(abs(x) for x in parent_scroll_left_deltas) / len(parent_scroll_left_deltas)
            if parent_scroll_left_deltas
            else 0
        )
        ratio = avg_top / avg_scroll if avg_scroll else 0

        positions = {s.get("position") for s in samples}
        always_fixed = all(s.get("position") == "fixed" for s in samples)
        sticky_like = "sticky" in positions or "fixed" in positions

        top_variance = max(s["top"] for s in samples) - min(s["top"] for s in samples)
        scroll_range = samples[-1]["scroll_y"] - samples[0]["scroll_y"]

        # CSS fixed for entire page != ScrollTrigger pin
        css_fixed = always_fixed and top_variance < 8

        # Pin evidence: element stays visually stable while document continues scrolling
        locked_frames = sum(
            1 for i in range(1, len(samples)) if abs(samples[i]["top"] - samples[i - 1]["top"]) < 6
        )
        lock_ratio = locked_frames / max(1, len(samples) - 1)
        mid = samples[len(samples) // 2]
        mid_sticky = mid.get("position") in ("sticky", "fixed")
        pinned_section = (
            not css_fixed
            and sticky_like
            and scroll_range > viewport_height * 0.35
            and (
                (mid_sticky and top_variance < 80 and lock_ratio >= 0.35)
                or (samples[0].get("stickyCandidate") and top_variance < 40 and scroll_range > 100)
            )
        )

        # Horizontal scroll requires stronger evidence than left-box drift alone
        tx_range = max((s.get("translateX") or 0) for s in samples) - min(
            (s.get("translateX") or 0) for s in samples
        )
        parent_sl_range = max((s.get("parentScrollLeft") or 0) for s in samples) - min(
            (s.get("parentScrollLeft") or 0) for s in samples
        )
        overflow_scroll = any(
            (s.get("parentOverflowX") or "") in ("auto", "scroll", "overlay") for s in samples
        )
        horizontal = (
            scroll_range > 150
            and (
                (avg_tx > 8 and abs(tx_range) > 40)
                or (avg_parent_sl > 5 and abs(parent_sl_range) > 40)
                or (overflow_scroll and avg_left > 40 and abs(tx_range) > 20)
            )
            and not (abs(ratio + 1.0) < 0.12 and abs(tx_range) < 20)
        )

        # Normal document flow ≈ ratio -1.0; require differential movement for parallax
        normal_scroll = abs(ratio + 1.0) < 0.12
        parallax = (
            not normal_scroll
            and abs(ratio + 1) > 0.2
            and abs(ratio) < 0.9
            and not css_fixed
            and not pinned_section
            and scroll_range > 200
        )

        opacity_changed = max(opacity_vals) - min(opacity_vals) > 0.15 if opacity_vals else False
        scale_changed = max(scale_vals) - min(scale_vals) > 0.05 if scale_vals else False
        clip_changed = len({c for c in clip_vals if c and c != "none"}) > 0 and len(set(clip_vals)) > 1

        classifications: list[tuple[str, ConfidenceLevel]] = []
        if css_fixed:
            classifications.append(("CSS_FIXED", ConfidenceLevel.OBSERVED))
        elif pinned_section:
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
        # Do NOT emit SCROLL_TRANSLATE for normal 1:1 document scroll
        if (
            not normal_scroll
            and abs(avg_top) > 15
            and not css_fixed
            and not pinned_section
            and not parallax
            and (opacity_changed or scale_changed or clip_changed or abs(ratio + 1) > 0.2)
        ):
            classifications.append(("SCROLL_TRANSLATE", ConfidenceLevel.OBSERVED))

        if not classifications:
            continue

        scrub = "YES" if (opacity_changed or scale_changed or parallax or horizontal or clip_changed) else "NO"

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
                        "avg_translate_x_delta": round(avg_tx, 2),
                        "translate_x_range": round(tx_range, 2),
                        "parent_scroll_left_range": round(parent_sl_range, 2),
                        "parallax_ratio": round(ratio, 3),
                        "normal_scroll": normal_scroll,
                        "lock_ratio": round(lock_ratio, 3),
                        "opacity_range": [min(opacity_vals), max(opacity_vals)] if opacity_vals else [],
                        "scale_range": [min(scale_vals), max(scale_vals)] if scale_vals else [],
                    },
                    scrub=scrub,
                    pin="YES" if classification == "PINNED" else ("CSS_FIXED" if classification == "CSS_FIXED" else "NO"),
                    parallax_ratio=round(ratio, 3) if classification == "PARALLAX" else None,
                    confidence=conf,
                    evidence=["runtime/scroll/findings.json", f"element:{key}"],
                )
            )

    return findings
