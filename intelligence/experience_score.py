"""Internal Experience Intelligence Score (not an official Awwwards score)."""

from __future__ import annotations

from intelligence.schema import WebsiteIntelligence


def compute_experience_score(website: WebsiteIntelligence) -> dict:
    """
    Evidence-weighted score out of 100.

    Categories:
      Visual Design /20, Motion /25, Scroll /20, Interaction /15,
      Transitions /10, Responsive Motion /10
    """
    mi = website.motion_intelligence
    di = website.design_intelligence
    pages = website.pages or []

    visual = 0
    visual_notes = []
    if di and (di.color_system or di.typography_hierarchy):
        visual += 8
        visual_notes.append("color/typography tokens present")
    if di and di.layout_system:
        visual += 6
        visual_notes.append("layout system present")
    if website.design_system and website.design_system.colors:
        visual += 6
        visual_notes.append("design system colors")
    visual = min(20, visual)

    motion = 0
    motion_notes = []
    if mi and mi.preloader.observed:
        motion += 5
        motion_notes.append("preloader OBSERVED")
    if mi and (mi.hero_animation or {}).get("status") == "OBSERVED":
        motion += 6
        motion_notes.append("hero OBSERVED")
    elif mi and (mi.hero_animation or {}).get("status") == "LAYOUT_CHANGE":
        motion += 1
        motion_notes.append("hero LAYOUT_CHANGE only")
    if mi and mi.text_animation:
        motion += 4
        motion_notes.append("text animation candidates")
    if mi and mi.image_animation:
        motion += 4
        motion_notes.append("image animation candidates")
    if mi and mi.gsap_status in ("DETECTED", "HIGH_CONFIDENCE"):
        motion += 3
        motion_notes.append(f"GSAP {mi.gsap_status}")
    elif mi and mi.gsap_status == "POSSIBLE":
        motion += 1
    motion = min(25, motion)

    scroll = 0
    scroll_notes = []
    if mi:
        if mi.scrolltrigger_analysis:
            scroll += min(8, 2 + len(mi.scrolltrigger_analysis))
            scroll_notes.append(f"{len(mi.scrolltrigger_analysis)} scroll findings")
        if mi.parallax:
            scroll += 4
            scroll_notes.append("parallax")
        if mi.pinning:
            scroll += 4
            scroll_notes.append("pinning")
        if mi.horizontal_scroll:
            scroll += 4
            scroll_notes.append("horizontal")
    scroll = min(20, scroll)

    interaction = 0
    interaction_notes = []
    hover_n = len(mi.hover_motion) if mi else 0
    if hover_n:
        interaction += min(8, 2 + hover_n // 2)
        interaction_notes.append(f"{hover_n} hover")
    if mi and mi.cursor.custom_cursor:
        interaction += 4
        interaction_notes.append("custom cursor")
    if mi and mi.magnetic_interactions and mi.magnetic_interactions[0].get("status") == "OBSERVED":
        interaction += 3
        interaction_notes.append("magnetic")
    total_ix = sum(len(p.interactions) for p in pages)
    if total_ix and not hover_n:
        interaction += min(4, total_ix // 5)
        interaction_notes.append(f"{total_ix} interactions sitewide")
    interaction = min(15, interaction)

    transitions = 0
    transition_notes = []
    if mi and any(t.observed for t in mi.page_transitions):
        transitions += 6
        transition_notes.append("page transitions")
    if mi and mi.section_transitions:
        transitions += min(4, len(mi.section_transitions))
        transition_notes.append("section color transitions")
    transitions = min(10, transitions)

    responsive = 0
    responsive_notes = []
    vp_count = len({r.width for p in pages for r in p.responsive})
    if vp_count >= 3:
        responsive += 6
        responsive_notes.append(f"{vp_count} viewports")
    elif vp_count:
        responsive += 3
    if mi and (mi.mobile_motion or {}).get("status") == "COMPARED":
        responsive += 4
        responsive_notes.append("mobile motion compared")
    responsive = min(10, responsive)

    total = visual + motion + scroll + interaction + transitions + responsive
    return {
        "label": "Internal Experience Intelligence Score",
        "disclaimer": "Not an official Awwwards score. Derived from runtime evidence only.",
        "categories": {
            "visual_design": {"score": visual, "max": 20, "notes": visual_notes},
            "motion": {"score": motion, "max": 25, "notes": motion_notes},
            "scroll_experience": {"score": scroll, "max": 20, "notes": scroll_notes},
            "interaction": {"score": interaction, "max": 15, "notes": interaction_notes},
            "transitions": {"score": transitions, "max": 10, "notes": transition_notes},
            "responsive_motion": {"score": responsive, "max": 10, "notes": responsive_notes},
        },
        "total": total,
        "max": 100,
    }
