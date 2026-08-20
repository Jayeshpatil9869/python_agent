"""Intelligence normalization."""

from collections import Counter
from typing import Any

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import (
    ColorToken,
    DesignSystem,
    PageAnalysis,
    TechnologyDetection,
    TypographyToken,
    WebsiteIntelligence,
)


def _assign_color_roles(colors: list[ColorToken]) -> list[ColorToken]:
    if not colors:
        return colors

    sorted_colors = sorted(colors, key=lambda c: c.count, reverse=True)
    roles = ["Background", "Text", "Primary", "Secondary", "Accent", "Surface", "Muted", "Border"]
    for i, color in enumerate(sorted_colors[: len(roles)]):
        if not color.role:
            color.role = roles[i]
    return sorted_colors


def aggregate_design_system(pages: list[PageAnalysis]) -> DesignSystem:
    color_counter: Counter[str] = Counter()
    color_usage: dict[str, str] = {}
    typo_map: dict[str, TypographyToken] = {}

    for page in pages:
        css = page.css_summary or {}
        for color, count in (css.get("color_frequency") or {}).items():
            color_counter[color] += count
            color_usage.setdefault(color, css.get("color_roles", {}).get(color, ""))

        for typo in css.get("typography_samples") or []:
            key = f"{typo.get('font_family')}|{typo.get('font_size')}|{typo.get('font_weight')}"
            if key not in typo_map:
                typo_map[key] = TypographyToken(
                    role=typo.get("role", ""),
                    font_family=typo.get("font_family", ""),
                    font_size=typo.get("font_size", ""),
                    font_weight=str(typo.get("font_weight", "")),
                    line_height=str(typo.get("line_height", "")),
                    letter_spacing=str(typo.get("letter_spacing", "")),
                    text_transform=typo.get("text_transform", ""),
                    count=1,
                    confidence=ConfidenceLevel.OBSERVED,
                )
            else:
                typo_map[key].count += 1

    colors = [
        ColorToken(value=c, count=n, usage=color_usage.get(c, ""), confidence=ConfidenceLevel.OBSERVED)
        for c, n in color_counter.most_common(20)
    ]

    layout = pages[0].layout_summary if pages else {}
    grid = layout.get("grid", {})
    containers = layout.get("containers", {})
    if isinstance(grid, list):
        grid = {"patterns": grid}
    if isinstance(containers, list):
        containers = {"observed": containers}
    return DesignSystem(
        colors=_assign_color_roles(colors),
        typography=sorted(typo_map.values(), key=lambda t: t.count, reverse=True)[:15],
        spacing=layout.get("spacing", {}) if isinstance(layout.get("spacing"), dict) else {},
        grid=grid,
        containers=containers,
        border_radius=layout.get("border_radius", []),
        shadows=layout.get("shadows", []),
        gradients=layout.get("gradients", []),
    )


def aggregate_technologies(pages: list[PageAnalysis]) -> list[TechnologyDetection]:
    tech_map: dict[str, TechnologyDetection] = {}
    for page in pages:
        for tech in page.technologies:
            if tech.name not in tech_map:
                tech_map[tech.name] = tech
            else:
                existing = tech_map[tech.name]
                existing.evidence = list(set(existing.evidence + tech.evidence))
                existing.confidence = max(existing.confidence, tech.confidence)
    return list(tech_map.values())


def normalize_website_intelligence(website: WebsiteIntelligence) -> WebsiteIntelligence:
    website.design_system = aggregate_design_system(website.pages)
    website.technologies = aggregate_technologies(website.pages)
    website.responsive_system = {
        "viewports_tested": sorted({r.width for p in website.pages for r in p.responsive}),
        "page_count": len(website.pages),
    }
    website.motion_system = {
        "animation_count": sum(len(p.animations) for p in website.pages),
        "interaction_count": sum(len(p.interactions) for p in website.pages),
    }
    return website
