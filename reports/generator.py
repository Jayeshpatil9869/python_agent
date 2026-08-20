"""Markdown report generation."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from intelligence.schema import WebsiteIntelligence
from reports.writer import write_report


class ReportGenerator:
    def __init__(self, intelligence: WebsiteIntelligence, output_dir: Path) -> None:
        self.intelligence = intelligence
        self.output_dir = output_dir
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate_all(self) -> None:
        reports = {
            "WEBSITE-ANALYSIS.md": "website_analysis.md.j2",
            "DESIGN-INTELLIGENCE.md": "design_intelligence.md.j2",
            "DESIGN-SYSTEM.md": "design_system.md.j2",
            "MOTION-INTELLIGENCE.md": "motion_intelligence.md.j2",
            "RESPONSIVE-SPEC.md": "responsive_spec.md.j2",
            "ANIMATION-SPEC.md": "animation_spec.md.j2",
            "INTERACTION-MAP.md": "interaction_map.md.j2",
            "COMPONENT-MAP.md": "component_map.md.j2",
            "TECHNOLOGY-REPORT.md": "technology_report.md.j2",
            "RECONSTRUCTION-PROMPT.md": "reconstruction_prompt.md.j2",
        }
        context = self._build_context()
        for filename, template_name in reports.items():
            try:
                template = self.env.get_template(template_name)
                content = template.render(**context)
            except Exception:
                content = self._fallback_report(filename)
            write_report(self.output_dir / filename, content)

    def _build_context(self) -> dict:
        page = self.intelligence.pages[0] if self.intelligence.pages else None
        return {
            "website": self.intelligence,
            "page": page,
            "pages": self.intelligence.pages,
            "design_system": self.intelligence.design_system,
            "design": self.intelligence.design_intelligence,
            "motion": self.intelligence.motion_intelligence,
            "technologies": self.intelligence.technologies,
            "ai": self.intelligence.ai_interpretation,
        }

    def _fallback_report(self, name: str) -> str:
        return f"# {name.replace('.md', '').replace('-', ' ').title()}\n\nReport generation pending.\n"
