"""Responsive browser laboratory."""

import json
import logging
from pathlib import Path

from intelligence.analyzer_result import AnalyzerResult, Finding, StageStatus
from intelligence.schema import ResponsiveViewportData
from observation.screenshot import capture_full_page
from utils.timing import wait_for_stabilization

logger = logging.getLogger(__name__)

VIEWPORT_METRICS_JS = """
() => {
    const pick = (sel) => document.querySelector(sel);
    const styleOf = (el) => el ? getComputedStyle(el) : null;
    const rectOf = (el) => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
    };

    const header = pick('header, [role="banner"], nav');
    const main = pick('main, [role="main"]');
    const hero = pick('.hero, [class*="hero"], section:first-of-type, main > section:first-child');
    const h1 = pick('h1');
    const nav = pick('nav, [role="navigation"]');
    const body = document.body;
    const bodyStyle = styleOf(body);

    const sections = Array.from(document.querySelectorAll('section, header, main, footer')).slice(0, 12).map(el => ({
        tag: el.tagName.toLowerCase(),
        id: el.id || '',
        class: (el.className || '').toString().split(' ')[0] || '',
        rect: rectOf(el),
        display: styleOf(el)?.display || '',
        visibility: styleOf(el)?.visibility || '',
    }));

    return {
        viewport_width: window.innerWidth,
        viewport_height: window.innerHeight,
        document_width: document.documentElement.scrollWidth,
        document_height: document.documentElement.scrollHeight,
        horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth,
        vertical_overflow: document.documentElement.scrollHeight > window.innerHeight,
        body_width: body?.getBoundingClientRect().width || 0,
        header: { rect: rectOf(header), display: styleOf(header)?.display, height: rectOf(header)?.h || 0 },
        main: { rect: rectOf(main), width: rectOf(main)?.w || 0, display: styleOf(main)?.display },
        hero: { rect: rectOf(hero), height: rectOf(hero)?.h || 0 },
        h1: { font_size: styleOf(h1)?.fontSize || '', rect: rectOf(h1) },
        nav: {
            visible: nav ? nav.getBoundingClientRect().height > 0 : false,
            display: styleOf(nav)?.display || '',
            rect: rectOf(nav),
        },
        grid_sample: (() => {
            const grid = Array.from(document.querySelectorAll('*')).find(el => getComputedStyle(el).display === 'grid');
            if (!grid) return null;
            const s = getComputedStyle(grid);
            return { columns: s.gridTemplateColumns, gap: s.gap, display: s.display };
        })(),
        flex_sample: (() => {
            const flex = Array.from(document.querySelectorAll('main *, section *')).find(el => {
                const s = getComputedStyle(el);
                return s.display === 'flex' && el.getBoundingClientRect().width > 200;
            });
            if (!flex) return null;
            const s = getComputedStyle(flex);
            return { direction: s.flexDirection, gap: s.gap, display: s.display };
        })(),
        sections,
        body_padding: bodyStyle?.padding || '',
        body_margin: bodyStyle?.margin || '',
    };
}
"""


def _category_for_width(width: int) -> str:
    if width < 768:
        return "mobile"
    if width < 1024:
        return "tablet"
    return "desktop"


async def analyze_responsive(
    page,
    url: str,
    viewports: list[tuple[int, int]],
    output_dir: Path,
    stabilization_ms: int = 1500,
    reload_each: bool = True,
) -> tuple[list[ResponsiveViewportData], AnalyzerResult]:
    """Run responsive laboratory on an existing Playwright page."""
    result = AnalyzerResult(stage="responsive", metrics={"viewports_requested": len(viewports)})
    collected: list[ResponsiveViewportData] = []

    logger.info("[RESPONSIVE] started page=%s viewports=%d", url, len(viewports))

    for width, height in viewports:
        category = _category_for_width(width)
        logger.info("[RESPONSIVE] viewport: %dx%d", width, height)
        try:
            await page.set_viewport_size({"width": width, "height": height})
            if reload_each:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await wait_for_stabilization(page, stabilization_ms)

            screenshot_rel = f"screenshots/{category}/viewport-{width}.png"
            screenshot_path = output_dir / screenshot_rel
            await capture_full_page(page, screenshot_path)
            logger.info("[RESPONSIVE] screenshot captured %s", screenshot_rel)

            metrics = await page.evaluate(VIEWPORT_METRICS_JS)
            notes: list[str] = []
            if metrics.get("horizontal_overflow"):
                notes.append("Horizontal overflow detected")
            if not metrics.get("nav", {}).get("visible"):
                notes.append("Navigation hidden or collapsed")

            entry = ResponsiveViewportData(
                width=width,
                screenshot=screenshot_rel,
                dom_width=int(metrics.get("document_width") or 0),
                dom_height=int(metrics.get("document_height") or 0),
                navigation_state="visible" if metrics.get("nav", {}).get("visible") else "hidden",
                notes=notes,
                element_snapshots=metrics,
            )
            collected.append(entry)
            result.evidence.append({"width": width, "height": height, "screenshot": screenshot_rel})

            runtime_dir = output_dir / "runtime" / "responsive"
            runtime_dir.mkdir(parents=True, exist_ok=True)

            runtime_path = runtime_dir / f"viewport-{width}.json"
            runtime_path.write_text(
                json.dumps(
                    {
                        "viewport": {"width": width, "height": height, "category": category},
                        "screenshot": screenshot_rel,
                        "metrics": metrics,
                        "notes": notes,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("[RESPONSIVE] viewport %dx%d failed: %s", width, height, exc)
            result.errors.append(f"{width}x{height}: {exc}")
            collected.append(ResponsiveViewportData(width=width, notes=[f"Failed: {exc}"]))

    comparison = compare_responsive_viewports(collected)
    result.metrics["viewports_analyzed"] = len([v for v in collected if v.dom_width > 0])
    result.metrics["comparison"] = comparison
    result.findings.append(
        Finding(
            value=comparison,
            status="OBSERVED" if collected else "UNKNOWN",
            confidence=0.9 if collected else 0.0,
            evidence=[v.screenshot for v in collected if v.screenshot],
            source="responsive_lab",
        )
    )

    if not collected:
        result.mark_failed("No viewport evidence collected")
    elif result.errors:
        result.mark_partial(f"{len(result.errors)} viewport(s) failed")
    elif result.metrics["viewports_analyzed"] == 0:
        result.mark_failed("All viewport captures lacked DOM metrics")
    else:
        result.status = StageStatus.SUCCESS

    logger.info(
        "[RESPONSIVE] completed %d/%d viewports analyzed",
        result.metrics["viewports_analyzed"],
        len(viewports),
    )
    return collected, result


def compare_responsive_viewports(viewports: list[ResponsiveViewportData]) -> dict:
    """Compare layout metrics across viewports."""
    if len(viewports) < 2:
        return {"note": "Insufficient viewports for comparison"}

    sorted_vps = sorted(viewports, key=lambda v: v.width)
    changes: list[dict] = []

    def snap(vp: ResponsiveViewportData, key: str):
        return (vp.element_snapshots or {}).get(key)

    for i in range(1, len(sorted_vps)):
        prev, curr = sorted_vps[i - 1], sorted_vps[i]
        prev_snap = prev.element_snapshots or {}
        curr_snap = curr.element_snapshots or {}

        diff: dict = {"from": prev.width, "to": curr.width, "changes": []}

        prev_h1 = (prev_snap.get("h1") or {}).get("font_size")
        curr_h1 = (curr_snap.get("h1") or {}).get("font_size")
        if prev_h1 and curr_h1 and prev_h1 != curr_h1:
            diff["changes"].append(f"H1 font: {prev_h1} -> {curr_h1}")

        prev_nav = (prev_snap.get("nav") or {}).get("display")
        curr_nav = (curr_snap.get("nav") or {}).get("display")
        if prev_nav != curr_nav:
            diff["changes"].append(f"Nav display: {prev_nav} -> {curr_nav}")

        prev_grid = prev_snap.get("grid_sample") or {}
        curr_grid = curr_snap.get("grid_sample") or {}
        if prev_grid and curr_grid and prev_grid.get("columns") != curr_grid.get("columns"):
            diff["changes"].append(
                f"Grid columns: {prev_grid.get('columns')} -> {curr_grid.get('columns')}"
            )

        prev_flex = prev_snap.get("flex_sample") or {}
        curr_flex = curr_snap.get("flex_sample") or {}
        if prev_flex and curr_flex and prev_flex.get("direction") != curr_flex.get("direction"):
            diff["changes"].append(
                f"Flex direction: {prev_flex.get('direction')} -> {curr_flex.get('direction')}"
            )

        if prev.navigation_state != curr.navigation_state:
            diff["changes"].append(
                f"Navigation: {prev.navigation_state} -> {curr.navigation_state}"
            )

        if diff["changes"]:
            changes.append(diff)

    hero_heights = {
        vp.width: (vp.element_snapshots or {}).get("hero", {}).get("height")
        for vp in sorted_vps
        if (vp.element_snapshots or {}).get("hero")
    }

    return {"breakpoint_changes": changes, "hero_heights_by_viewport": hero_heights}
