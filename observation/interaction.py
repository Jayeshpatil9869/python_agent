"""Interaction testing laboratory with hover, focus, and safe click flows."""

import json
import logging
from pathlib import Path

from intelligence.analyzer_result import AnalyzerResult, StageStatus
from intelligence.confidence import ConfidenceLevel
from intelligence.schema import InteractionRecord

logger = logging.getLogger(__name__)

CANDIDATE_SELECTORS = [
    "button",
    "a[href]",
    "[role='button']",
    "[role='tab']",
    "[aria-expanded]",
    "[aria-controls]",
    "summary",
    "[tabindex]",
    "nav a",
    "[class*='card']",
    "[class*='btn']",
    "[class*='cta']",
    "[class*='menu']",
    "[class*='accordion']",
    "[class*='carousel'] button",
]


async def _element_state(page, selector: str, index: int) -> dict | None:
    return await page.evaluate(
        """([selector, index]) => {
            const els = document.querySelectorAll(selector);
            const el = els[index];
            if (!el) return null;
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return {
                tag: el.tagName.toLowerCase(),
                text: (el.textContent || '').trim().slice(0, 50),
                classes: Array.from(el.classList).slice(0, 4),
                ariaExpanded: el.getAttribute('aria-expanded'),
                ariaControls: el.getAttribute('aria-controls'),
                role: el.getAttribute('role') || el.tagName.toLowerCase(),
                styles: {
                    color: s.color,
                    backgroundColor: s.backgroundColor,
                    transform: s.transform,
                    boxShadow: s.boxShadow,
                    opacity: s.opacity,
                    borderColor: s.borderColor,
                    visibility: s.visibility,
                    display: s.display,
                },
                box: { x: r.x, y: r.y, w: r.width, h: r.height },
            };
        }""",
        [selector, index],
    )


def _diff_states(before: dict, after: dict) -> dict:
    changes = {}
    for key, val in before.get("styles", {}).items():
        after_val = after.get("styles", {}).get(key)
        if val != after_val:
            changes[key] = {"before": val, "after": after_val}
    for attr in ("ariaExpanded", "ariaControls"):
        if before.get(attr) != after.get(attr):
            changes[attr] = {"before": before.get(attr), "after": after.get(attr)}
    return changes


def _is_unsafe_link(href: str) -> bool:
    href_lower = (href or "").lower()
    return any(x in href_lower for x in ("mailto:", "tel:", "javascript:"))


async def _record_interaction(
    interactions: list[InteractionRecord],
    runtime_dir: Path,
    idx: int,
    trigger: str,
    before: dict,
    after: dict,
    changes: dict,
    component_type: str = "",
) -> None:
    label = f"{before.get('tag')}: {before.get('text') or component_type or 'element'}"
    evidence_path = f"runtime/interactions/{trigger}-{idx:03d}.json"
    interactions.append(
        InteractionRecord(
            element=label,
            trigger=trigger,
            behavior=str(changes),
            animation="css transition/change",
            mobile="unknown",
            confidence=ConfidenceLevel.OBSERVED,
            evidence=[evidence_path, "before/after state diff"],
        )
    )
    (runtime_dir / f"{trigger}-{idx:03d}.json").write_text(
        json.dumps(
            {
                "trigger": trigger,
                "component_type": component_type,
                "before": before,
                "after": after,
                "changes": changes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


async def run_interaction_lab(
    page,
    output_dir: Path,
    max_candidates: int = 25,
) -> tuple[list[InteractionRecord], AnalyzerResult]:
    result = AnalyzerResult(stage="interactions")
    interactions: list[InteractionRecord] = []
    runtime_dir = output_dir / "runtime" / "interactions"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    candidates: list[tuple[str, int, str]] = []
    for selector in CANDIDATE_SELECTORS:
        try:
            count = await page.locator(selector).count()
            for i in range(min(count, 5)):
                candidates.append((selector, i, selector.split("[")[0]))
        except Exception:
            continue

    candidates = candidates[:max_candidates]
    result.metrics["candidates_discovered"] = len(candidates)
    logger.info("[INTERACTION] discovered %d candidates", len(candidates))

    tested = 0
    observed = 0
    action_idx = 0

    for selector, index, component_type in candidates:
        try:
            locator = page.locator(selector).nth(index)
            if not await locator.is_visible():
                continue

            before = await _element_state(page, selector, index)
            if not before:
                continue

            href = await locator.get_attribute("href") or ""
            if _is_unsafe_link(href):
                continue

            tested += 1

            # Hover
            try:
                await locator.hover(timeout=2000)
                await page.wait_for_timeout(300)
                after_hover = await _element_state(page, selector, index)
                if after_hover:
                    changes = _diff_states(before, after_hover)
                    if changes:
                        observed += 1
                        await _record_interaction(
                            interactions, runtime_dir, action_idx, "hover", before, after_hover, changes, component_type
                        )
                        action_idx += 1
                await page.mouse.move(0, 0)
            except Exception:
                pass

            # Focus (safe)
            try:
                await locator.focus(timeout=2000)
                await page.wait_for_timeout(200)
                after_focus = await _element_state(page, selector, index)
                if after_focus:
                    changes = _diff_states(before, after_focus)
                    if changes:
                        observed += 1
                        await _record_interaction(
                            interactions, runtime_dir, action_idx, "focus", before, after_focus, changes, component_type
                        )
                        action_idx += 1
            except Exception:
                pass

            # Safe click for toggles (accordion, tabs, aria-expanded, summary)
            is_toggle = (
                before.get("tag") == "summary"
                or before.get("ariaExpanded") is not None
                or before.get("role") == "tab"
                or "accordion" in component_type
                or "menu" in component_type
            )
            if is_toggle:
                try:
                    before_click = await _element_state(page, selector, index)
                    await locator.click(timeout=2000)
                    await page.wait_for_timeout(400)
                    after_click = await _element_state(page, selector, index)
                    if before_click and after_click:
                        changes = _diff_states(before_click, after_click)
                        if changes:
                            observed += 1
                            await _record_interaction(
                                interactions,
                                runtime_dir,
                                action_idx,
                                "click",
                                before_click,
                                after_click,
                                changes,
                                component_type,
                            )
                            action_idx += 1
                        # Restore toggle state when possible
                        try:
                            await locator.click(timeout=2000)
                            await page.wait_for_timeout(200)
                        except Exception:
                            pass
                except Exception:
                    pass

        except Exception as exc:
            result.warnings.append(f"{selector}[{index}]: {exc}")
            continue

    result.metrics["candidates_tested"] = tested
    result.metrics["state_changes_observed"] = observed

    if not candidates:
        result.mark_no_data("No interaction candidates discovered")
    elif tested == 0:
        result.mark_failed("Candidates found but none could be tested")
    elif observed == 0:
        result.mark_no_data("Tested interactions but no state changes observed")
    else:
        result.status = StageStatus.SUCCESS

    logger.info(
        "[INTERACTION] tested %d safe candidates, observed %d state changes",
        tested,
        observed,
    )
    return interactions, result
