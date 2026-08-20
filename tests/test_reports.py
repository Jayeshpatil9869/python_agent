"""Tests for report generation."""

from pathlib import Path

from intelligence.schema import PageAnalysis, WebsiteIntelligence
from reports.generator import ReportGenerator


def test_report_generation(tmp_path):
    intelligence = WebsiteIntelligence(
        url="https://example.com",
        title="Example Site",
        pages=[
            PageAnalysis(
                url="https://example.com",
                title="Example Site",
                dom_depth=10,
                section_count=3,
            )
        ],
    )
    generator = ReportGenerator(intelligence, tmp_path)
    generator.generate_all()

    assert (tmp_path / "WEBSITE-ANALYSIS.md").exists()
    assert (tmp_path / "DESIGN-SYSTEM.md").exists()
    assert (tmp_path / "DESIGN-INTELLIGENCE.md").exists()
    assert (tmp_path / "MOTION-INTELLIGENCE.md").exists()
    assert (tmp_path / "TECHNOLOGY-REPORT.md").exists()
    assert (tmp_path / "RECONSTRUCTION-PROMPT.md").exists()

    content = (tmp_path / "WEBSITE-ANALYSIS.md").read_text(encoding="utf-8")
    assert "example.com" in content
    motion = (tmp_path / "MOTION-INTELLIGENCE.md").read_text(encoding="utf-8")
    assert "Motion Summary" in motion
