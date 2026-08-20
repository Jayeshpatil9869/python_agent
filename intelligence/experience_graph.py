"""Site-wide experience graph connecting pages → sections → triggers → animations."""

from __future__ import annotations

from urllib.parse import urlparse

from intelligence.schema import WebsiteIntelligence


def build_experience_graph(website: WebsiteIntelligence) -> dict:
    """
    Build a hierarchical experience graph from aggregated evidence.

    Nodes are observational summaries — not fabricated choreography.
    """
    pages_nodes = []
    for page in website.pages or []:
        path = urlparse(page.url).path or "/"
        children: list[dict] = []

        if page.preloader.observed:
            children.append(
                {
                    "id": f"{path}#preloader",
                    "type": "PRELOADER",
                    "label": page.preloader.type,
                    "confidence": page.preloader.confidence.value,
                    "exits_to": "HERO",
                }
            )
        elif page.preloader.type not in ("NOT_OBSERVED", "", None):
            children.append(
                {
                    "id": f"{path}#overlay",
                    "type": page.preloader.type,
                    "label": "persistent overlay (not confirmed preloader)",
                    "confidence": "OBSERVED",
                }
            )

        hero = page.page_load.hero_animation or {}
        if hero.get("status") == "OBSERVED":
            children.append(
                {
                    "id": f"{path}#hero",
                    "type": "HERO",
                    "label": hero.get("element", "hero"),
                    "trigger": "page_load",
                    "confidence": "OBSERVED",
                    "children": [
                        {"type": "REVEAL", "label": "heading/media reveal", "trigger": "page_load"}
                    ],
                }
            )
        elif hero.get("status") == "LAYOUT_CHANGE":
            children.append(
                {
                    "id": f"{path}#hero",
                    "type": "HERO",
                    "label": hero.get("element", "hero"),
                    "status": "LAYOUT_CHANGE",
                    "confidence": "OBSERVED",
                }
            )

        scroll_by_class: dict[str, list[str]] = {}
        for f in page.scroll_motion_findings:
            scroll_by_class.setdefault(f.classification, []).append(f.element)
        if scroll_by_class:
            children.append(
                {
                    "id": f"{path}#scroll",
                    "type": "SCROLL_SYSTEM",
                    "children": [
                        {
                            "type": cls,
                            "elements": els[:8],
                            "count": len(els),
                            "confidence": "OBSERVED",
                        }
                        for cls, els in scroll_by_class.items()
                    ],
                }
            )

        hovers = [i for i in page.interactions if i.trigger == "hover"]
        if hovers:
            children.append(
                {
                    "id": f"{path}#hover",
                    "type": "INTERACTIONS",
                    "hover_count": len(hovers),
                    "samples": [i.element for i in hovers[:6]],
                    "confidence": "OBSERVED",
                }
            )

        if page.cursor.custom_cursor:
            children.append(
                {
                    "id": f"{path}#cursor",
                    "type": "CURSOR",
                    "magnetic": page.cursor.magnetic,
                    "confidence": page.cursor.confidence.value,
                }
            )

        for t in page.page_transitions:
            if t.observed:
                children.append(
                    {
                        "id": f"{path}#transition",
                        "type": "PAGE_TRANSITION",
                        "label": t.type or "transition",
                        "confidence": t.confidence.value,
                    }
                )

        pages_nodes.append(
            {
                "id": path,
                "url": page.url,
                "type": "PAGE",
                "children": children,
            }
        )

    mi = website.motion_intelligence
    global_layer = []
    if mi and mi.preloader.observed:
        global_layer.append({"type": "PRELOADER", "status": "OBSERVED"})
    if mi and mi.cursor.custom_cursor:
        global_layer.append({"type": "CURSOR", "status": "OBSERVED"})
    if mi and any(t.observed for t in mi.page_transitions):
        global_layer.append({"type": "PAGE_TRANSITIONS", "status": "OBSERVED"})

    return {
        "site": website.url,
        "pages_analyzed": len(website.pages or []),
        "global": global_layer,
        "pages": pages_nodes,
        "evidence_policy": "OBSERVED nodes require browser/runtime evidence",
    }
