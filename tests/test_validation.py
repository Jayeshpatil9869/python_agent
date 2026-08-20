"""Tests for validation PASS/PARTIAL/FAIL."""

from pathlib import Path

from intelligence.validation import validate_analysis_output


def test_validation_fail_on_missing_pages(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "website.json").write_text('{"stage_results": {}}', encoding="utf-8")
    (data_dir / "pages.json").write_text("[]", encoding="utf-8")
    (data_dir / "responsive.json").write_text("[]", encoding="utf-8")
    (data_dir / "interactions.json").write_text("[]", encoding="utf-8")
    (data_dir / "animations.json").write_text("[]", encoding="utf-8")
    (data_dir / "technologies.json").write_text("[]", encoding="utf-8")

    result = validate_analysis_output(tmp_path)
    assert result["overall_status"] in ("FAIL", "PARTIAL")


def test_validation_pass_with_evidence(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "website.json").write_text(
        '{"stage_results": {"responsive": {"status": "success", "metrics": {"viewports_requested": 1, "viewports_analyzed": 1}}, '
        '"interactions": {"status": "skipped"}, "animations": {"status": "skipped"}}}',
        encoding="utf-8",
    )
    (data_dir / "pages.json").write_text('[{"url": "https://example.com"}]', encoding="utf-8")
    (data_dir / "responsive.json").write_text(
        '[{"width": 375, "screenshot": "screenshots/mobile/viewport-375.png", "dom_width": 375}]',
        encoding="utf-8",
    )
    (data_dir / "interactions.json").write_text("[]", encoding="utf-8")
    (data_dir / "animations.json").write_text("[]", encoding="utf-8")
    (data_dir / "technologies.json").write_text("[]", encoding="utf-8")

    shots = tmp_path / "screenshots" / "mobile"
    shots.mkdir(parents=True)
    (shots / "viewport-375.png").write_bytes(b"fake")

    for report in (
        "WEBSITE-ANALYSIS.md",
        "DESIGN-INTELLIGENCE.md",
        "DESIGN-SYSTEM.md",
        "MOTION-INTELLIGENCE.md",
        "RESPONSIVE-SPEC.md",
        "ANIMATION-SPEC.md",
        "INTERACTION-MAP.md",
        "COMPONENT-MAP.md",
        "TECHNOLOGY-REPORT.md",
        "RECONSTRUCTION-PROMPT.md",
    ):
        (tmp_path / report).write_text("# Report\n", encoding="utf-8")

    result = validate_analysis_output(tmp_path)
    assert result["overall_status"] == "PASS"
