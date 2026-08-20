"""Motion timeline reconstruction from observed phases (no fabricated timings)."""

from __future__ import annotations

from intelligence.schema import WebsiteIntelligence


def build_page_load_timeline(website: WebsiteIntelligence) -> list[dict]:
    """
    Reconstruct approximate page-load sequence from preloader + page_load evidence.

    Timings are marked ESTIMATED when derived, OBSERVED when sampled, UNKNOWN otherwise.
    """
    pages = website.pages or []
    if not pages:
        return []

    mi = website.motion_intelligence
    preloader = mi.preloader if mi else pages[0].preloader
    page_load = mi.page_load if mi else pages[0].page_load

    events: list[dict] = [
        {"t_ms": 0, "event": "page_initialized", "status": "OBSERVED"},
    ]

    if preloader.observed:
        start = 0
        end = preloader.duration_ms
        events.append(
            {
                "t_ms": start,
                "event": "preloader_start",
                "detail": preloader.type,
                "status": "OBSERVED",
            }
        )
        if end is not None:
            events.append(
                {
                    "t_ms": end,
                    "event": "preloader_exit",
                    "status": preloader.duration_status or "ESTIMATED",
                }
            )
        else:
            events.append({"t_ms": None, "event": "preloader_exit", "status": "UNKNOWN"})

    nav = page_load.navigation_animation or {}
    if nav.get("status") == "OBSERVED":
        events.append(
            {
                "t_ms": None,
                "event": "navigation_reveal",
                "detail": nav.get("element"),
                "status": nav.get("duration_status", "ESTIMATED"),
            }
        )

    hero = page_load.hero_animation or {}
    if hero.get("status") == "OBSERVED":
        events.append(
            {
                "t_ms": hero.get("reveal_at_ms"),
                "event": "hero_reveal",
                "detail": hero.get("element"),
                "status": hero.get("duration_status", "ESTIMATED"),
                "animated_properties": hero.get("animated_properties") or [],
            }
        )
    elif hero.get("status") == "LAYOUT_CHANGE":
        events.append(
            {
                "t_ms": None,
                "event": "hero_layout_change",
                "detail": hero.get("note"),
                "status": "OBSERVED",
            }
        )

    for phase in (page_load.phases or [])[-1:]:
        events.append(
            {
                "t_ms": phase.get("t"),
                "event": "idle_or_last_sample",
                "readyState": phase.get("readyState"),
                "status": "OBSERVED",
            }
        )

    # Sort known timings first
    def sort_key(e: dict):
        t = e.get("t_ms")
        return (0, t) if isinstance(t, (int, float)) else (1, 0)

    return sorted(events, key=sort_key)


def build_complete_motion_timeline(website: WebsiteIntelligence) -> list[dict]:
    """Merge page-load timeline with site-wide motion intelligence timeline."""
    base = build_page_load_timeline(website)
    mi = website.motion_intelligence
    extra = list(mi.complete_timeline) if mi else []
    return base + [{"source": "motion_intelligence", **e} for e in extra]
