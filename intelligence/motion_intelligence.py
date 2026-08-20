"""Build Motion Intelligence from runtime evidence."""

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import (
    MotionIntelligence,
    PageAnalysis,
    ScrollMotionFinding,
    TechnologyDetection,
    WebsiteIntelligence,
)


def build_motion_intelligence(website: WebsiteIntelligence) -> MotionIntelligence:
    page = website.pages[0] if website.pages else None
    if not page:
        return MotionIntelligence(
            motion_summary="No page evidence available.",
            confidence=ConfidenceLevel.UNKNOWN,
        )

    gsap_status, st_status = _tech_status(website.technologies)
    findings = list(page.scroll_motion_findings)

    parallax = [f for f in findings if f.classification == "PARALLAX"]
    pinning = [f for f in findings if f.classification == "PINNED"]
    horizontal = [f for f in findings if f.classification == "HORIZONTAL_SCROLL"]
    scrolltrigger_like = [
        f for f in findings
        if f.classification in (
            "SCROLL_FADE",
            "SCROLL_LINKED_SCALE",
            "SCROLL_TRANSLATE",
            "SCROLL_CLIP_REVEAL",
            "PARALLAX",
            "PINNED",
            "HORIZONTAL_SCROLL",
            "CSS_FIXED",
        )
    ]

    text_anims = _text_animations(page)
    image_anims = _image_animations(page, findings)
    video_anims = _video_animations(page)
    hover = _hover_motion(page)
    micro = _micro_interactions(page)

    personality = _motion_personality(page, findings, gsap_status)
    hierarchy = _motion_hierarchy(page, findings)
    timeline = _complete_timeline(page, findings)
    hypotheses = _hypotheses(page, gsap_status, st_status, findings)
    mobile = _mobile_motion(page)

    summary = _summary(page, findings, personality)

    evidence = []
    if page.preloader.evidence:
        evidence.extend(page.preloader.evidence[:2])
    if page.page_load.evidence:
        evidence.extend(page.page_load.evidence[:2])
    evidence.append("runtime/scroll/findings.json")
    if page.cursor.evidence:
        evidence.extend(page.cursor.evidence[:1])

    return MotionIntelligence(
        motion_summary=summary,
        motion_personality=personality,
        preloader=page.preloader,
        page_load=page.page_load,
        hero_animation=page.page_load.hero_animation,
        navigation_animation=page.page_load.navigation_animation,
        scroll_system={
            "samples": len(page.scroll_observations),
            "findings": len(findings),
            "color_transitions": len(page.color_transitions),
        },
        scrolltrigger_analysis=scrolltrigger_like,
        parallax=parallax,
        pinning=pinning,
        horizontal_scroll=horizontal,
        text_animation=text_anims,
        image_animation=image_anims,
        video_animation=video_anims,
        hover_motion=hover,
        cursor=page.cursor,
        magnetic_interactions=_magnetic(page),
        micro_interactions=micro,
        section_transitions=_section_transitions(page),
        page_transitions=page.page_transitions,
        mobile_motion=mobile,
        motion_hierarchy=hierarchy,
        complete_timeline=timeline,
        gsap_status=gsap_status,
        scrolltrigger_status=st_status,
        implementation_hypotheses=hypotheses,
        confidence=ConfidenceLevel.INFERRED if findings or page.preloader.observed else ConfidenceLevel.OBSERVED,
        evidence=evidence,
    )


def _tech_status(techs: list[TechnologyDetection]) -> tuple[str, str]:
    gsap = next((t for t in techs if t.name == "GSAP"), None)
    gsap_status = gsap.status if gsap else "UNKNOWN"
    st_status = "UNKNOWN"
    if gsap and any("ScrollTrigger" in e for e in gsap.evidence):
        st_status = gsap.status
    elif gsap and gsap.status in ("DETECTED", "HIGH_CONFIDENCE"):
        st_status = "POSSIBLE"
    elif gsap and gsap.status == "POSSIBLE":
        st_status = "POSSIBLE"
    return gsap_status, st_status


def _text_animations(page: PageAnalysis) -> list[dict]:
    results = []
    for anim in page.animations:
        el = (anim.element or "").lower()
        if any(x in el for x in ("h1", "h2", "title", "text", "heading")):
            results.append(
                {
                    "element": anim.element,
                    "trigger": anim.trigger,
                    "classification": anim.classification or anim.direction or "text_reveal_candidate",
                    "initial": anim.initial_state,
                    "final": anim.final_state,
                    "confidence": anim.confidence.value,
                    "evidence": anim.evidence,
                }
            )
    hero = page.page_load.hero_animation
    if hero.get("status") == "OBSERVED":
        results.append(
            {
                "element": hero.get("element", "hero heading"),
                "trigger": "page_load",
                "classification": "heading_reveal",
                "initial": hero.get("initial"),
                "final": hero.get("final"),
                "confidence": "OBSERVED",
                "evidence": page.page_load.evidence,
            }
        )
    return results


def _image_animations(page: PageAnalysis, findings: list[ScrollMotionFinding]) -> list[dict]:
    results = []
    for f in findings:
        if "img" in f.element.lower() or f.classification in ("SCROLL_LINKED_SCALE", "SCROLL_CLIP_REVEAL", "PARALLAX"):
            if "img" in f.element.lower() or f.classification == "SCROLL_CLIP_REVEAL":
                results.append(
                    {
                        "element": f.element,
                        "classification": f.classification,
                        "scrub": f.scrub,
                        "confidence": f.confidence.value,
                        "evidence": f.evidence,
                    }
                )
    for anim in page.animations:
        if "img" in (anim.element or "").lower() or "image" in (anim.element or "").lower():
            results.append(
                {
                    "element": anim.element,
                    "classification": anim.classification or "image_animation",
                    "confidence": anim.confidence.value,
                    "evidence": anim.evidence,
                }
            )
    return results


def _video_animations(page: PageAnalysis) -> list[dict]:
    if page.videos_count <= 0:
        return [{"status": "NOT_OBSERVED"}]
    return [
        {
            "status": "PRESENT",
            "video_count": page.videos_count,
            "confidence": "OBSERVED",
            "note": "Video elements present; playback control not fully instrumented",
        }
    ]


def _hover_motion(page: PageAnalysis) -> list[dict]:
    return [
        {
            "element": i.element,
            "trigger": i.trigger,
            "behavior": i.behavior[:200] if i.behavior else "",
            "confidence": i.confidence.value,
            "evidence": i.evidence,
        }
        for i in page.interactions
        if i.trigger == "hover"
    ]


def _micro_interactions(page: PageAnalysis) -> list[dict]:
    return [
        {
            "element": i.element,
            "trigger": i.trigger,
            "behavior": i.behavior[:200] if i.behavior else "",
            "confidence": i.confidence.value,
        }
        for i in page.interactions
    ]


def _magnetic(page: PageAnalysis) -> list[dict]:
    if page.cursor.magnetic:
        return [
            {
                "status": "OBSERVED" if page.cursor.details.get("magnetic") else "INFERRED",
                "details": page.cursor.details.get("magnetic") or {},
                "evidence": page.cursor.evidence,
            }
        ]
    return [{"status": "NOT_OBSERVED"}]


def _section_transitions(page: PageAnalysis) -> list[dict]:
    return [
        {
            "from_scroll": c.from_scroll,
            "to_scroll": c.to_scroll,
            "from_color": c.from_color,
            "to_color": c.to_color,
            "type": c.transition_type,
            "confidence": c.confidence.value,
        }
        for c in page.color_transitions
    ]


def _mobile_motion(page: PageAnalysis) -> dict:
    mobile_vp = next((r for r in page.responsive if r.width <= 480), None)
    desktop_vp = next((r for r in page.responsive if r.width >= 1280), None)
    result = {
        "status": "COMPARED" if mobile_vp and desktop_vp else "PARTIAL",
        "notes": [],
    }
    if mobile_vp and desktop_vp:
        m_nav = mobile_vp.navigation_state
        d_nav = desktop_vp.navigation_state
        if m_nav != d_nav:
            result["notes"].append(f"Navigation: desktop={d_nav}, mobile={m_nav}")
        result["notes"].append("Cursor systems are typically disabled on touch — confirm separately if custom cursor observed on desktop.")
        result["desktop_viewport"] = desktop_vp.width
        result["mobile_viewport"] = mobile_vp.width
    if page.cursor.custom_cursor:
        result["notes"].append("Custom cursor OBSERVED on analysis viewport; mobile likely removes cursor (reason: UNKNOWN unless compared).")
    if not result["notes"]:
        result["notes"].append("Insufficient paired evidence for detailed mobile motion divergence.")
    return result


def _motion_personality(page: PageAnalysis, findings: list, gsap_status: str) -> list[str]:
    tags = []
    if page.preloader.observed:
        tags.append("cinematic")
    if any(f.classification == "PARALLAX" for f in findings):
        tags.append("depth-oriented")
    if any(f.classification == "PINNED" for f in findings):
        tags.append("editorial")
    if page.page_load.hero_animation.get("status") == "OBSERVED":
        tags.append("choreographed")
    if gsap_status == "DETECTED":
        tags.append("timeline-driven")
    if page.cursor.custom_cursor:
        tags.append("interaction-rich")
    if not tags:
        tags.append("restrained")
    return tags


def _motion_hierarchy(page: PageAnalysis, findings: list) -> dict[str, list[str]]:
    return {
        "LEVEL_1_GLOBAL": [
            x for x in [
                "Preloader" if page.preloader.observed else None,
                "Page transitions" if any(t.observed for t in page.page_transitions) else None,
            ] if x
        ] or ["NOT_OBSERVED"],
        "LEVEL_2_SECTION": [
            f.classification for f in findings if f.classification in ("PINNED", "HORIZONTAL_SCROLL", "PARALLAX")
        ] or ["scroll section reveals (if any)"],
        "LEVEL_3_COMPONENT": [
            f.classification for f in findings if f.classification.startswith("SCROLL_")
        ] + (["hero reveal"] if page.page_load.hero_animation.get("status") == "OBSERVED" else []),
        "LEVEL_4_MICRO": [
            i.trigger for i in page.interactions[:8]
        ] + (["custom cursor"] if page.cursor.custom_cursor else []),
    }


def _complete_timeline(page: PageAnalysis, findings: list) -> list[dict]:
    events = []
    if page.preloader.observed:
        events.append({"phase": "PRELOADER", "detail": page.preloader.type, "confidence": page.preloader.confidence.value})
    if page.page_load.navigation_animation.get("status") == "OBSERVED":
        events.append({"phase": "PAGE_LOAD", "detail": "navigation reveal", "confidence": "OBSERVED"})
    if page.page_load.hero_animation.get("status") == "OBSERVED":
        events.append({"phase": "PAGE_LOAD", "detail": "hero reveal", "confidence": "OBSERVED"})
    for f in findings[:12]:
        events.append(
            {
                "phase": "SCROLL",
                "detail": f"{f.classification}: {f.element}",
                "scroll_start": f.scroll_start,
                "scroll_end": f.scroll_end,
                "confidence": f.confidence.value,
            }
        )
    for i in page.interactions[:6]:
        events.append({"phase": "INTERACTION", "detail": f"{i.trigger}: {i.element}", "confidence": i.confidence.value})
    return events


def _hypotheses(page: PageAnalysis, gsap_status: str, st_status: str, findings: list) -> list[str]:
    hyps = []
    if gsap_status == "DETECTED":
        hyps.append("GSAP detected via runtime/resource evidence — timeline-based motion likely.")
    elif findings and gsap_status == "UNKNOWN":
        hyps.append("Scroll-linked behavior OBSERVED; library unknown — could be GSAP ScrollTrigger, CSS sticky, or custom RAF. Status: POSSIBLE.")
    if st_status in ("DETECTED", "HIGH_CONFIDENCE"):
        hyps.append("ScrollTrigger markers/globals suggest scrub/pin APIs.")
    elif any(f.scrub == "YES" for f in findings):
        hyps.append("Scrub-like coupling OBSERVED (scroll position ↔ transform/opacity). Implementation hypothesis only.")
    if page.preloader.observed:
        hyps.append("Preloader suggests asset/font gate before hero choreography.")
    if not hyps:
        hyps.append("No strong library hypotheses beyond observed CSS/runtime changes.")
    return hyps


def _summary(page: PageAnalysis, findings: list, personality: list[str]) -> str:
    parts = [
        f"Motion personality signals: {', '.join(personality)}.",
        f"Preloader: {'OBSERVED (' + page.preloader.type + ')' if page.preloader.observed else 'NOT_OBSERVED'}.",
        f"Page-load hero: {page.page_load.hero_animation.get('status', 'UNKNOWN')}.",
        f"Scroll findings: {len(findings)}.",
        f"Custom cursor: {'OBSERVED' if page.cursor.custom_cursor else 'NOT_OBSERVED'}.",
    ]
    return " ".join(parts)
