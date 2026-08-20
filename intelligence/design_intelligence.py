"""Build Design Intelligence from collected evidence."""

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import (
    ColorTransition,
    DesignIntelligence,
    DesignSystem,
    PageAnalysis,
    WebsiteIntelligence,
)


def build_design_intelligence(website: WebsiteIntelligence) -> DesignIntelligence:
    page = website.pages[0] if website.pages else None
    ds = website.design_system
    color_transitions: list[ColorTransition] = []
    if page:
        color_transitions = list(page.color_transitions)

    color_system = _build_color_system(ds)
    typography_hierarchy = [
        {
            "role": t.role,
            "font_family": t.font_family,
            "font_size": t.font_size,
            "font_weight": t.font_weight,
            "line_height": t.line_height,
            "letter_spacing": t.letter_spacing,
            "confidence": t.confidence.value,
        }
        for t in ds.typography[:12]
    ]

    layout = page.layout_summary if page else {}
    direction = _infer_design_direction(ds, color_transitions, page)
    relationship = _design_motion_relationship(website, direction)

    score = _experience_score(website)

    evidence = ["data/design.json", "DESIGN-SYSTEM.md"]
    if color_transitions:
        evidence.append("runtime/scroll/color_transitions.json")

    return DesignIntelligence(
        design_direction=direction,
        color_system=color_system,
        color_transitions=color_transitions,
        typography_hierarchy=typography_hierarchy,
        layout_system={
            "grid": ds.grid,
            "spacing": ds.spacing,
            "containers": ds.containers,
            "layout_summary": layout,
        },
        image_language=_image_language(page),
        visual_effects={
            "shadows": ds.shadows[:8],
            "gradients": ds.gradients[:8],
            "border_radius": ds.border_radius[:8],
        },
        section_rhythm=_section_rhythm(page),
        visual_hierarchy=_visual_hierarchy(ds, page),
        design_patterns=_design_patterns(ds, page),
        design_motion_relationship=relationship,
        experience_score=score,
        confidence=ConfidenceLevel.INFERRED,
        evidence=evidence,
    )


def _build_color_system(ds: DesignSystem) -> dict:
    roles = {c.role.lower(): c.value for c in ds.colors if c.role}
    return {
        "background": roles.get("background") or (ds.colors[0].value if ds.colors else "UNKNOWN"),
        "text": roles.get("text") or "UNKNOWN",
        "primary": roles.get("primary") or "UNKNOWN",
        "secondary": roles.get("secondary") or "UNKNOWN",
        "accent": roles.get("accent") or "UNKNOWN",
        "surface": roles.get("surface") or "UNKNOWN",
        "muted": roles.get("muted") or "UNKNOWN",
        "border": roles.get("border") or "UNKNOWN",
        "observed_palette": [{"role": c.role, "value": c.value, "count": c.count} for c in ds.colors[:12]],
        "gradient_usage": ds.gradients[:5],
    }


def _infer_design_direction(ds: DesignSystem, transitions: list, page: PageAnalysis | None) -> str:
    parts = []
    if ds.colors:
        parts.append(f"palette anchored by {ds.colors[0].value}")
    if ds.typography:
        hero = next((t for t in ds.typography if t.role in ("h1", "hero", "display")), ds.typography[0])
        parts.append(f"display type {hero.font_family} at {hero.font_size}")
    if transitions:
        parts.append(f"{len(transitions)} scroll-linked color transition(s) observed")
    if page and page.section_count:
        parts.append(f"{page.section_count} major sections")
    if not parts:
        return "Insufficient evidence for design direction."
    return "Editorial visual language suggested by " + "; ".join(parts) + "."


def _design_motion_relationship(website: WebsiteIntelligence, direction: str) -> str:
    mi = website.motion_intelligence
    motion_bits = []
    if mi.preloader.observed:
        motion_bits.append("preloader-gated entry")
    if mi.parallax:
        motion_bits.append("parallax depth")
    if mi.pinning:
        motion_bits.append("pinned sections")
    if mi.page_load.hero_animation.get("status") == "OBSERVED":
        motion_bits.append("choreographed hero reveal")
    if not motion_bits:
        return direction + " Motion relationship: limited motion evidence observed."
    return f"{direction} Combined with {', '.join(motion_bits)} to form the experience system."


def _image_language(page: PageAnalysis | None) -> dict:
    if not page:
        return {"status": "UNKNOWN"}
    return {
        "image_count": page.images_count,
        "video_count": page.videos_count,
        "assets_sample": [a.url for a in page.assets[:5]],
    }


def _section_rhythm(page: PageAnalysis | None) -> list[str]:
    if not page:
        return []
    rhythm = [f"Sections observed: {page.section_count}"]
    if page.color_transitions:
        rhythm.append(f"Color changes across scroll: {len(page.color_transitions)}")
    return rhythm


def _visual_hierarchy(ds: DesignSystem, page: PageAnalysis | None) -> list[str]:
    hierarchy = []
    for t in ds.typography[:5]:
        hierarchy.append(f"{t.role or 'text'}: {t.font_size} / {t.font_weight} ({t.font_family})")
    if page and page.headings:
        hierarchy.append(f"Heading counts: {page.headings}")
    return hierarchy


def _design_patterns(ds: DesignSystem, page: PageAnalysis | None) -> list[str]:
    patterns = []
    if ds.shadows:
        patterns.append("elevated surfaces via shadow")
    if ds.gradients:
        patterns.append("gradient accents")
    if ds.border_radius:
        patterns.append("rounded geometric language")
    if page and page.components:
        patterns.append(f"{len(page.components)} inferred components")
    return patterns or ["No strong pattern signals beyond base tokens"]


def _experience_score(website: WebsiteIntelligence) -> dict:
    """Internal heuristic Design Intelligence Motion Score — not an official Awwwards rating."""
    mi = website.motion_intelligence
    ds = website.design_system

    visual = min(20, 8 + len(ds.colors) + (4 if ds.gradients else 0))
    typography = min(10, 4 + min(6, len(ds.typography)))
    motion = 4
    if mi.preloader.observed:
        motion += 3
    if mi.page_load.hero_animation.get("status") == "OBSERVED":
        motion += 3
    motion += min(6, len(mi.scrolltrigger_analysis))
    motion += min(4, len(mi.parallax) + len(mi.pinning))
    motion = min(20, motion)

    interaction = min(15, 3 + min(6, len(mi.hover_motion)) + (3 if mi.cursor.custom_cursor else 0) + min(3, len(mi.micro_interactions)))
    scroll_exp = min(15, 3 + min(6, len(mi.scrolltrigger_analysis)) + (3 if mi.horizontal_scroll else 0) + (3 if mi.pinning else 0))
    responsive = min(10, 4 + (3 if website.responsive_system.get("viewports_tested") else 0) + (3 if mi.mobile_motion else 0))
    originality = min(10, 3 + (2 if mi.preloader.observed else 0) + (2 if mi.cursor.custom_cursor else 0) + (3 if mi.horizontal_scroll or mi.pinning else 0))

    total = visual + typography + motion + interaction + scroll_exp + responsive + originality
    return {
        "label": "Design Intelligence Motion Score — internal heuristic",
        "visual_design": visual,
        "typography": typography,
        "motion": motion,
        "interaction": interaction,
        "scroll_experience": scroll_exp,
        "responsive_motion": responsive,
        "originality_signals": originality,
        "total": total,
        "max": 100,
        "note": "Not an official Awwwards score. Derived only from observed evidence.",
    }
