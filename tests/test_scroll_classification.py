"""Unit tests for scroll motion classification noise filtering."""

from intelligence.confidence import ConfidenceLevel
from observation.scroll import _analyze_motion_history


def _samples(key: str, points: list[tuple[int, float, str]]) -> dict:
    """points: (scroll_y, top, position)"""
    return {
        key: [
            {
                "scroll_y": sy,
                "pct": 0,
                "key": key,
                "top": top,
                "left": 0,
                "opacity": "1",
                "scale": 1.0,
                "clipPath": "none",
                "position": pos,
            }
            for sy, top, pos in points
        ]
    }


def test_normal_scroll_not_classified_as_translate():
    # Element moves 1:1 with scroll (document flow)
    history = _samples(
        "h1.title",
        [(0, 100, "static"), (500, -400, "static"), (1000, -900, "static"), (1500, -1400, "static")],
    )
    findings = _analyze_motion_history(history, viewport_height=900)
    assert findings == []


def test_parallax_detected_when_ratio_differs():
    history = _samples(
        "div.parallax",
        [(0, 200, "relative"), (500, 50, "relative"), (1000, -50, "relative"), (1500, -120, "relative")],
    )
    findings = _analyze_motion_history(history, viewport_height=900)
    assert any(f.classification == "PARALLAX" for f in findings)


def test_left_drift_alone_not_horizontal_scroll():
    """Bounding-box left drift without translateX/scrollLeft must not be HORIZONTAL_SCROLL."""
    history = {
        "h1.title": [
            {
                "scroll_y": sy,
                "pct": 0,
                "key": "h1.title",
                "top": 100 - sy,
                "left": 20 + (sy // 50),  # drifts left as layout reflows
                "opacity": "1",
                "scale": 1.0,
                "translateX": 0,
                "parentScrollLeft": 0,
                "parentOverflowX": "visible",
                "clipPath": "none",
                "position": "static",
            }
            for sy in (0, 400, 800, 1200, 1600)
        ]
    }
    findings = _analyze_motion_history(history, viewport_height=900)
    assert not any(f.classification == "HORIZONTAL_SCROLL" for f in findings)


def test_translate_x_scrub_is_horizontal_scroll():
    history = {
        "div.gallery": [
            {
                "scroll_y": sy,
                "pct": 0,
                "key": "div.gallery",
                "top": 100,
                "left": 0,
                "opacity": "1",
                "scale": 1.0,
                "translateX": -sy * 0.5,
                "parentScrollLeft": 0,
                "parentOverflowX": "visible",
                "clipPath": "none",
                "position": "relative",
            }
            for sy in (0, 400, 800, 1200, 1600)
        ]
    }
    findings = _analyze_motion_history(history, viewport_height=900)
    assert any(f.classification == "HORIZONTAL_SCROLL" for f in findings)


def test_sticky_candidate_can_pin():
    history = {
        "sticky:div.pin": [
            {
                "scroll_y": sy,
                "pct": 0,
                "key": "sticky:div.pin",
                "top": 40,
                "left": 0,
                "opacity": "1",
                "scale": 1.0,
                "translateX": 0,
                "parentScrollLeft": 0,
                "parentOverflowX": "visible",
                "clipPath": "none",
                "position": "sticky",
                "stickyCandidate": True,
            }
            for sy in (0, 500, 1000, 1500, 2000)
        ]
    }
    findings = _analyze_motion_history(history, viewport_height=900)
    assert any(f.classification == "PINNED" for f in findings)
