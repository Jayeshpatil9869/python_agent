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


def test_css_fixed_header_not_pinned():
    history = _samples(
        "header.fixed",
        [(0, 0, "fixed"), (500, 0, "fixed"), (1000, 0, "fixed"), (2000, 0, "fixed")],
    )
    findings = _analyze_motion_history(history, viewport_height=900)
    assert any(f.classification == "CSS_FIXED" for f in findings)
    assert not any(f.classification == "PINNED" for f in findings)
