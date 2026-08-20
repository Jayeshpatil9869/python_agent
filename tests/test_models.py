"""Tests for Pydantic models."""

from intelligence.confidence import ConfidenceLevel
from intelligence.normalizer import normalize_website_intelligence
from intelligence.schema import (
    ColorToken,
    DesignSystem,
    PageAnalysis,
    TechnologyDetection,
    WebsiteIntelligence,
)


def test_website_intelligence_serialization():
    website = WebsiteIntelligence(
        url="https://example.com",
        title="Example",
        pages=[PageAnalysis(url="https://example.com", title="Example")],
    )
    data = website.model_dump(mode="json")
    assert data["url"] == "https://example.com"
    assert len(data["pages"]) == 1


def test_confidence_levels():
    assert ConfidenceLevel.DETECTED.value == "DETECTED"
    assert ConfidenceLevel.UNKNOWN.value == "UNKNOWN"


def test_normalize_aggregates_design_system():
    page = PageAnalysis(
        url="https://example.com",
        css_summary={
            "color_frequency": {"#000": 5, "#fff": 3},
            "typography_samples": [
                {"font_family": "Arial", "font_size": "16px", "font_weight": "400", "role": "p"}
            ],
        },
    )
    website = WebsiteIntelligence(url="https://example.com", pages=[page])
    result = normalize_website_intelligence(website)
    assert len(result.design_system.colors) == 2
    assert result.design_system.colors[0].count == 5


def test_technology_detection_model():
    tech = TechnologyDetection(
        name="React",
        status="detected",
        confidence=0.9,
        confidence_level=ConfidenceLevel.DETECTED,
        evidence=["window.React"],
    )
    assert tech.name == "React"
    assert tech.confidence == 0.9
