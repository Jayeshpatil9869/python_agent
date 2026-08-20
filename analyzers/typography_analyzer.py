"""Typography analysis."""

from collections import Counter


def analyze_typography(css_summary: dict) -> list[dict]:
    samples = css_summary.get("typography_samples") or []
    families = Counter(s.get("font_family", "") for s in samples if s.get("font_family"))
    sizes = Counter(s.get("font_size", "") for s in samples if s.get("font_size"))

    roles = _infer_typography_roles(samples)

    return {
        "font_families": [{"family": f, "count": c} for f, c in families.most_common(10)],
        "font_sizes": [{"size": s, "count": c} for s, c in sizes.most_common(15)],
        "roles": roles,
    }


def _infer_typography_roles(samples: list[dict]) -> list[dict]:
    role_map = {
        "h1": "Display/H1",
        "h2": "H2",
        "h3": "H3",
        "h4": "H4",
        "p": "Body",
        "button": "Button",
        "a": "Navigation",
        "small": "Small",
        "label": "Caption",
    }
    results = []
    seen = set()
    for sample in samples:
        tag = sample.get("role", "")
        role = role_map.get(tag, "")
        if not role:
            continue
        key = f"{role}|{sample.get('font_size')}|{sample.get('font_family')}"
        if key in seen:
            continue
        seen.add(key)
        results.append({**sample, "role": role})
    return results[:12]
