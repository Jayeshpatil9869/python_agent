"""Component detection heuristics."""

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import ComponentRecord


COMPONENT_SELECTORS = {
    "Header": "header, [role='banner'], .header, #header",
    "Navigation": "nav, [role='navigation'], .nav, .navbar",
    "Hero": ".hero, [class*='hero'], section:first-of-type",
    "Footer": "footer, [role='contentinfo'], .footer",
    "Button": "button, .btn, [class*='button'], a[class*='btn']",
    "Card": ".card, [class*='card'], article",
    "Form": "form",
    "Modal": "[role='dialog'], .modal, [class*='modal']",
    "CTA": "[class*='cta'], a[class*='cta'], button[class*='cta']",
}


async def analyze_components(page) -> list[ComponentRecord]:
    components: list[ComponentRecord] = []

    for name, selector in COMPONENT_SELECTORS.items():
        try:
            info = await page.evaluate(
                """(selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return null;
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    const children = Array.from(el.children).slice(0, 8).map(c => c.tagName.toLowerCase());
                    return {
                        selector,
                        tag: el.tagName.toLowerCase(),
                        id: el.id || '',
                        classes: Array.from(el.classList).slice(0, 5),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        display: style.display,
                        children,
                    };
                }""",
                selector,
            )
            if info:
                components.append(
                    ComponentRecord(
                        name=name,
                        purpose=f"Detected {name.lower()} region",
                        selector=info.get("selector", selector),
                        visual_structure=f"{info.get('tag')} ({info.get('width')}x{info.get('height')})",
                        children=info.get("children", []),
                        styles={
                            "display": info.get("display"),
                            "classes": info.get("classes"),
                        },
                        confidence=ConfidenceLevel.INFERRED,
                    )
                )
        except Exception:
            continue

    return components
