"""Interaction analysis."""

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import InteractionRecord


async def analyze_interactions(page) -> list[InteractionRecord]:
    interactions: list[InteractionRecord] = []

    try:
        elements = await page.evaluate(
            """() => {
                const selectors = 'button, a, [role="button"], input, select, textarea, [tabindex]';
                return Array.from(document.querySelectorAll(selectors)).slice(0, 30).map(el => {
                    const style = getComputedStyle(el);
                    return {
                        tag: el.tagName.toLowerCase(),
                        text: (el.textContent || '').trim().slice(0, 40),
                        cursor: style.cursor,
                        hasTransition: style.transitionDuration !== '0s',
                        transition: style.transition,
                    };
                });
            }"""
        )

        for el in elements:
            behavior = "clickable"
            animation = el.get("transition", "") if el.get("hasTransition") else "none"
            interactions.append(
                InteractionRecord(
                    element=f"{el.get('tag')}: {el.get('text') or '(no text)'}",
                    trigger="click/hover",
                    behavior=behavior,
                    animation=animation[:80] if animation else "none",
                    mobile="unknown",
                    confidence=ConfidenceLevel.OBSERVED,
                    evidence=["computed styles"],
                )
            )
    except Exception:
        pass

    return interactions
