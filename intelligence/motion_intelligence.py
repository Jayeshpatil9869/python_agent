"""Build site-wide Motion Intelligence from ALL analyzed pages."""

from __future__ import annotations

from urllib.parse import urlparse

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import (
    CursorObservation,
    MotionIntelligence,
    PageAnalysis,
    PageLoadTimeline,
    PreloaderObservation,
    ScrollMotionFinding,
    TechnologyDetection,
    TransitionObservation,
    WebsiteIntelligence,
)


def build_motion_intelligence(website: WebsiteIntelligence) -> MotionIntelligence:
    pages = website.pages or []
    if not pages:
        return MotionIntelligence(
            motion_summary="No page evidence available.",
            confidence=ConfidenceLevel.UNKNOWN,
        )

    gsap_status, st_status = _tech_status(website.technologies)

    # Aggregate scroll findings across all pages (dedupe by element+classification)
    findings = _dedupe_findings([f for p in pages for f in p.scroll_motion_findings])
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

    # Prefer homepage / seed for preloader + page-load when present
    primary = _primary_page(pages, website.url)
    preloader = _best_preloader(pages)
    page_load = _best_page_load(pages, primary)

    text_anims = _flatten([_text_animations(p) for p in pages])
    image_anims = _flatten([_image_animations(p, p.scroll_motion_findings) for p in pages])
    video_anims = _flatten([_video_animations(p) for p in pages])
    hover = _flatten([_hover_motion(p) for p in pages])
    micro = _flatten([_micro_interactions(p) for p in pages])
    section_transitions = _flatten([_section_transitions(p) for p in pages])
    page_transitions = _flatten([[t for t in p.page_transitions] for p in pages])
    cursor = _best_cursor(pages)

    personality = _motion_personality(pages, findings, gsap_status, preloader, page_load, cursor, hover)
    hierarchy = _motion_hierarchy(pages, findings, preloader, page_transitions, cursor, hover)
    timeline = _complete_timeline(pages, findings, preloader, page_load)
    hypotheses = _hypotheses(pages, gsap_status, st_status, findings)
    mobile = _mobile_motion(pages)

    total_interactions = sum(len(p.interactions) for p in pages)
    total_scroll_samples = sum(len(p.scroll_observations) for p in pages)
    total_color_tx = sum(len(p.color_transitions) for p in pages)

    summary = _summary(
        pages=pages,
        findings=findings,
        personality=personality,
        preloader=preloader,
        page_load=page_load,
        hover_count=len(hover),
        cursor=cursor,
    )

    evidence: list[str] = [
        "data/motion/site_motion.json",
        "data/experience_graph.json",
    ]
    evidence.extend(preloader.evidence[:2])
    evidence.extend(page_load.evidence[:2])
    if cursor.evidence:
        evidence.extend(cursor.evidence[:1])

    return MotionIntelligence(
        motion_summary=summary,
        motion_personality=personality,
        preloader=preloader,
        page_load=page_load,
        hero_animation=page_load.hero_animation,
        navigation_animation=page_load.navigation_animation,
        scroll_system={
            "pages": len(pages),
            "samples": total_scroll_samples,
            "findings": len(findings),
            "color_transitions": total_color_tx,
            "interactions_sitewide": total_interactions,
            "hover_sitewide": len(hover),
        },
        scrolltrigger_analysis=scrolltrigger_like[:40],
        parallax=parallax[:20],
        pinning=pinning[:20],
        horizontal_scroll=horizontal[:20],
        text_animation=text_anims[:30],
        image_animation=image_anims[:30],
        video_animation=video_anims[:15],
        hover_motion=hover[:40],
        cursor=cursor,
        magnetic_interactions=_magnetic(pages),
        micro_interactions=micro[:50],
        section_transitions=section_transitions[:20],
        page_transitions=page_transitions[:10],
        mobile_motion=mobile,
        motion_hierarchy=hierarchy,
        complete_timeline=timeline,
        gsap_status=gsap_status,
        scrolltrigger_status=st_status,
        implementation_hypotheses=hypotheses,
        confidence=(
            ConfidenceLevel.INFERRED
            if findings or preloader.observed or hover
            else ConfidenceLevel.OBSERVED
        ),
        evidence=evidence,
    )


def page_motion_snapshot(page: PageAnalysis) -> dict:
    """Per-page motion export for data/motion/pages/*.json."""
    return {
        "url": page.url,
        "preloader": page.preloader.model_dump(mode="json"),
        "page_load": page.page_load.model_dump(mode="json"),
        "hero": page.page_load.hero_animation,
        "navigation": page.page_load.navigation_animation,
        "scroll_observations_count": len(page.scroll_observations),
        "scroll_findings": [f.model_dump(mode="json") for f in page.scroll_motion_findings],
        "color_transitions": [c.model_dump(mode="json") for c in page.color_transitions],
        "animations": [a.model_dump(mode="json") for a in page.animations],
        "interactions": [i.model_dump(mode="json") for i in page.interactions],
        "cursor": page.cursor.model_dump(mode="json"),
        "page_transitions": [t.model_dump(mode="json") for t in page.page_transitions],
    }


def _primary_page(pages: list[PageAnalysis], site_url: str) -> PageAnalysis:
    seed_path = urlparse(site_url).path.rstrip("/") or "/"
    for p in pages:
        path = urlparse(p.url).path.rstrip("/") or "/"
        if path == seed_path:
            return p
    return pages[0]


def _best_preloader(pages: list[PageAnalysis]) -> PreloaderObservation:
    observed = [p.preloader for p in pages if p.preloader.observed]
    if observed:
        return observed[0]
    # Prefer one with progress notes / timeline evidence
    with_timeline = [p.preloader for p in pages if p.preloader.timeline]
    return with_timeline[0] if with_timeline else pages[0].preloader


def _best_page_load(pages: list[PageAnalysis], primary: PageAnalysis) -> PageLoadTimeline:
    for p in [primary, *pages]:
        if p.page_load.hero_animation.get("status") == "OBSERVED":
            return p.page_load
    for p in [primary, *pages]:
        if p.page_load.phases:
            return p.page_load
    return primary.page_load


def _best_cursor(pages: list[PageAnalysis]) -> CursorObservation:
    for p in pages:
        if p.cursor.custom_cursor and p.cursor.confidence == ConfidenceLevel.OBSERVED:
            return p.cursor
    for p in pages:
        if p.cursor.custom_cursor:
            return p.cursor
    return pages[0].cursor


def _dedupe_findings(findings: list[ScrollMotionFinding]) -> list[ScrollMotionFinding]:
    seen: set[tuple[str, str]] = set()
    out: list[ScrollMotionFinding] = []
    for f in findings:
        key = (f.element, f.classification)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _flatten(lists: list[list]) -> list:
    out = []
    for items in lists:
        out.extend(items)
    return out


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
        if any(x in el for x in ("h1", "h2", "title", "text", "heading", "framer-text")):
            results.append(
                {
                    "page": page.url,
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
                "page": page.url,
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
        if "img" in f.element.lower() or f.classification in (
            "SCROLL_LINKED_SCALE",
            "SCROLL_CLIP_REVEAL",
            "PARALLAX",
        ):
            if "img" in f.element.lower() or f.classification == "SCROLL_CLIP_REVEAL":
                results.append(
                    {
                        "page": page.url,
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
                    "page": page.url,
                    "element": anim.element,
                    "classification": anim.classification or "image_animation",
                    "confidence": anim.confidence.value,
                    "evidence": anim.evidence,
                }
            )
    return results


def _video_animations(page: PageAnalysis) -> list[dict]:
    if page.videos_count <= 0:
        return []
    return [
        {
            "page": page.url,
            "status": "PRESENT",
            "video_count": page.videos_count,
            "confidence": "OBSERVED",
            "note": "Video elements present; playback control partially instrumented",
        }
    ]


def _hover_motion(page: PageAnalysis) -> list[dict]:
    return [
        {
            "page": page.url,
            "element": i.element,
            "trigger": i.trigger,
            "behavior": (i.behavior or "")[:200],
            "confidence": i.confidence.value,
            "evidence": i.evidence,
        }
        for i in page.interactions
        if i.trigger == "hover"
    ]


def _micro_interactions(page: PageAnalysis) -> list[dict]:
    return [
        {
            "page": page.url,
            "element": i.element,
            "trigger": i.trigger,
            "behavior": (i.behavior or "")[:200],
            "confidence": i.confidence.value,
        }
        for i in page.interactions
    ]


def _magnetic(pages: list[PageAnalysis]) -> list[dict]:
    for p in pages:
        if p.cursor.magnetic:
            return [
                {
                    "status": "OBSERVED" if p.cursor.details.get("magnetic") else "INFERRED",
                    "page": p.url,
                    "details": p.cursor.details.get("magnetic") or {},
                    "evidence": p.cursor.evidence,
                }
            ]
    return [{"status": "NOT_OBSERVED"}]


def _section_transitions(page: PageAnalysis) -> list[dict]:
    return [
        {
            "page": page.url,
            "from_scroll": c.from_scroll,
            "to_scroll": c.to_scroll,
            "from_color": c.from_color,
            "to_color": c.to_color,
            "type": c.transition_type,
            "confidence": c.confidence.value,
        }
        for c in page.color_transitions
    ]


def _mobile_motion(pages: list[PageAnalysis]) -> dict:
    notes = []
    compared = False
    for page in pages:
        mobile_vp = next((r for r in page.responsive if r.width <= 480), None)
        desktop_vp = next((r for r in page.responsive if r.width >= 1280), None)
        if mobile_vp and desktop_vp:
            compared = True
            if mobile_vp.navigation_state != desktop_vp.navigation_state:
                notes.append(
                    f"{page.url}: nav desktop={desktop_vp.navigation_state} mobile={mobile_vp.navigation_state}"
                )
        if page.cursor.custom_cursor:
            notes.append(f"{page.url}: custom cursor on analysis viewport; typically disabled on touch (reason UNKNOWN).")
    if not notes:
        notes.append("Insufficient paired evidence for detailed mobile motion divergence.")
    return {
        "status": "COMPARED" if compared else "PARTIAL",
        "notes": notes[:12],
        "pages_compared": len(pages),
    }


def _motion_personality(
    pages: list[PageAnalysis],
    findings: list,
    gsap_status: str,
    preloader: PreloaderObservation,
    page_load: PageLoadTimeline,
    cursor: CursorObservation,
    hover: list,
) -> list[str]:
    tags = []
    if preloader.observed:
        tags.append("cinematic")
    if any(f.classification == "PARALLAX" for f in findings):
        tags.append("depth-oriented")
    if any(f.classification == "PINNED" for f in findings):
        tags.append("editorial")
    if page_load.hero_animation.get("status") == "OBSERVED":
        tags.append("choreographed")
    if gsap_status == "DETECTED":
        tags.append("timeline-driven")
    if cursor.custom_cursor:
        tags.append("interaction-rich")
    if hover:
        tags.append("micro-interactive")
    if len(pages) > 1:
        tags.append("multi-page")
    return tags or ["restrained"]


def _motion_hierarchy(
    pages: list[PageAnalysis],
    findings: list,
    preloader: PreloaderObservation,
    transitions: list[TransitionObservation],
    cursor: CursorObservation,
    hover: list,
) -> dict[str, list[str]]:
    return {
        "LEVEL_1_GLOBAL": [
            x for x in [
                "Preloader" if preloader.observed else None,
                "Page transitions" if any(t.observed for t in transitions) else None,
                "Custom cursor" if cursor.custom_cursor else None,
            ] if x
        ] or ["NOT_OBSERVED"],
        "LEVEL_2_SECTION": [
            f.classification for f in findings if f.classification in ("PINNED", "HORIZONTAL_SCROLL", "PARALLAX")
        ] or ["scroll section reveals (if any)"],
        "LEVEL_3_COMPONENT": [
            f.classification for f in findings if f.classification.startswith("SCROLL_")
        ] + [
            f"hero reveal ({urlparse(p.url).path or '/'})"
            for p in pages
            if p.page_load.hero_animation.get("status") == "OBSERVED"
        ][:5],
        "LEVEL_4_MICRO": list({i.get("trigger", "") for i in hover[:12]})
        + (["custom cursor"] if cursor.custom_cursor else [])
        or ["NOT_OBSERVED"],
        "PAGES_ANALYZED": [p.url for p in pages],
    }


def _complete_timeline(
    pages: list[PageAnalysis],
    findings: list,
    preloader: PreloaderObservation,
    page_load: PageLoadTimeline,
) -> list[dict]:
    events = []
    if preloader.observed:
        events.append(
            {
                "phase": "PRELOADER",
                "detail": preloader.type,
                "confidence": preloader.confidence.value,
            }
        )
    if page_load.navigation_animation.get("status") == "OBSERVED":
        events.append({"phase": "PAGE_LOAD", "detail": "navigation reveal", "confidence": "OBSERVED"})
    if page_load.hero_animation.get("status") == "OBSERVED":
        events.append(
            {
                "phase": "PAGE_LOAD",
                "detail": f"hero reveal ({page_load.hero_animation.get('element')})",
                "confidence": "OBSERVED",
                "reveal_at_ms": page_load.hero_animation.get("reveal_at_ms"),
            }
        )
    for f in findings[:16]:
        events.append(
            {
                "phase": "SCROLL",
                "detail": f"{f.classification}: {f.element}",
                "scroll_start": f.scroll_start,
                "scroll_end": f.scroll_end,
                "confidence": f.confidence.value,
            }
        )
    for p in pages:
        for i in p.interactions[:4]:
            events.append(
                {
                    "phase": "INTERACTION",
                    "detail": f"{i.trigger}: {i.element}",
                    "page": p.url,
                    "confidence": i.confidence.value,
                }
            )
    return events


def _hypotheses(
    pages: list[PageAnalysis],
    gsap_status: str,
    st_status: str,
    findings: list,
) -> list[str]:
    hyps = []
    if gsap_status == "DETECTED":
        hyps.append("GSAP detected via runtime/resource evidence — timeline-based motion likely.")
    elif findings and gsap_status == "UNKNOWN":
        hyps.append(
            "Scroll-linked behavior OBSERVED; library unknown — could be Framer, GSAP, CSS, or custom RAF. Status: POSSIBLE."
        )
    if st_status in ("DETECTED", "HIGH_CONFIDENCE"):
        hyps.append("ScrollTrigger markers/globals suggest scrub/pin APIs.")
    elif any(f.scrub == "YES" for f in findings):
        hyps.append("Scrub-like coupling OBSERVED (scroll position ↔ transform/opacity). Implementation hypothesis only.")
    if any(p.preloader.observed for p in pages):
        hyps.append("Preloader suggests asset/font gate before hero choreography.")
    framer_dom = any("framer" in (a.element or "").lower() for p in pages for a in p.animations)
    framer_hero = any("framer" in str(p.page_load.hero_animation).lower() for p in pages)
    if framer_dom or framer_hero:
        hyps.append("Framer DOM markers observed (e.g. framer-text) — motion may be Framer Motion driven.")
    if not hyps:
        hyps.append("No strong library hypotheses beyond observed CSS/runtime changes.")
    return hyps


def _summary(
    pages: list[PageAnalysis],
    findings: list,
    personality: list[str],
    preloader: PreloaderObservation,
    page_load: PageLoadTimeline,
    hover_count: int,
    cursor: CursorObservation,
) -> str:
    return (
        f"Site-wide motion across {len(pages)} page(s). "
        f"Personality: {', '.join(personality)}. "
        f"Preloader: {'OBSERVED (' + preloader.type + ')' if preloader.observed else 'NOT_OBSERVED'}. "
        f"Hero: {page_load.hero_animation.get('status', 'UNKNOWN')}. "
        f"Scroll findings: {len(findings)}. "
        f"Hover interactions (site-wide): {hover_count}. "
        f"Custom cursor: {'OBSERVED' if cursor.custom_cursor else 'NOT_OBSERVED'}."
    )
