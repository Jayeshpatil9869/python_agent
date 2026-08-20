"""Color analysis."""

from analyzers.css_analyzer import rank_colors


def analyze_colors(css_summary: dict) -> dict:
    frequency = css_summary.get("color_frequency") or {}
    ranked = rank_colors(frequency)

    palette = {
        "observed_colors": ranked,
        "primary": ranked[0]["color"] if ranked else None,
        "secondary": ranked[1]["color"] if len(ranked) > 1 else None,
        "accent": ranked[2]["color"] if len(ranked) > 2 else None,
    }
    return palette
