"""Multi-page motion aggregation tests."""

from intelligence.confidence import ConfidenceLevel
from intelligence.experience_graph import build_experience_graph
from intelligence.motion_intelligence import build_motion_intelligence, page_motion_snapshot
from intelligence.schema import (
    InteractionRecord,
    PageAnalysis,
    ScrollMotionFinding,
    WebsiteIntelligence,
)


def test_motion_aggregates_hover_from_all_pages():
    home = PageAnalysis(url="https://example.com/", title="Home")
    about = PageAnalysis(
        url="https://example.com/about",
        title="About",
        interactions=[
            InteractionRecord(
                element="a.cta",
                trigger="hover",
                behavior="scale 1.05",
                confidence=ConfidenceLevel.OBSERVED,
            ),
            InteractionRecord(
                element="button.nav",
                trigger="hover",
                behavior="underline",
                confidence=ConfidenceLevel.OBSERVED,
            ),
        ],
        scroll_motion_findings=[
            ScrollMotionFinding(
                element="div.parallax",
                classification="PARALLAX",
                confidence=ConfidenceLevel.OBSERVED,
            )
        ],
    )
    website = WebsiteIntelligence(url="https://example.com/", pages=[home, about])
    mi = build_motion_intelligence(website)
    assert len(mi.hover_motion) == 2
    assert "site-wide" in mi.motion_summary.lower() or "2 page" in mi.motion_summary.lower()
    assert len(mi.parallax) == 1
    assert mi.scroll_system.get("hover_sitewide") == 2


def test_page_motion_snapshot_includes_interactions():
    page = PageAnalysis(
        url="https://example.com/works",
        interactions=[
            InteractionRecord(element=".card", trigger="hover", confidence=ConfidenceLevel.OBSERVED)
        ],
    )
    snap = page_motion_snapshot(page)
    assert snap["url"].endswith("/works")
    assert len(snap["interactions"]) == 1


def test_experience_graph_includes_inner_pages():
    website = WebsiteIntelligence(
        url="https://example.com/",
        pages=[
            PageAnalysis(url="https://example.com/"),
            PageAnalysis(
                url="https://example.com/about",
                interactions=[
                    InteractionRecord(element="a", trigger="hover", confidence=ConfidenceLevel.OBSERVED)
                ],
            ),
        ],
    )
    graph = build_experience_graph(website)
    assert graph["pages_analyzed"] == 2
    about = next(p for p in graph["pages"] if "about" in p["url"])
    assert any(c["type"] == "INTERACTIONS" for c in about["children"])
