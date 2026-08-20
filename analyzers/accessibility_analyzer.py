"""Accessibility observational audit."""

from bs4 import BeautifulSoup

from intelligence.schema import AccessibilityData


def analyze_accessibility(html: str) -> AccessibilityData:
    soup = BeautifulSoup(html, "lxml")

    aria_count = sum(
        1 for el in soup.find_all(True) for attr in el.attrs if str(attr).startswith("aria-")
    )

    landmarks = [el.name for el in soup.find_all(["header", "nav", "main", "footer", "aside"])]

    heading_issues = []
    prev_level = 0
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(h.name[1])
        if prev_level and level - prev_level > 1:
            heading_issues.append(f"Skipped heading level before {h.name}")
        prev_level = level

    missing_alt = len([img for img in soup.find_all("img") if not img.get("alt")])

    form_issues = 0
    for inp in soup.find_all("input"):
        if inp.get("type") not in ("hidden", "submit", "button") and not inp.get("aria-label"):
            label = soup.find("label", attrs={"for": inp.get("id")}) if inp.get("id") else None
            if not label:
                form_issues += 1

    focusable = len(
        soup.find_all(["a", "button", "input", "select", "textarea", "[tabindex]"])
    )

    notes = []
    if missing_alt:
        notes.append(f"{missing_alt} images missing alt text")
    if form_issues:
        notes.append(f"{form_issues} form inputs may lack labels")

    return AccessibilityData(
        aria_usage=aria_count,
        landmarks=landmarks,
        heading_issues=heading_issues,
        missing_alt_images=missing_alt,
        form_label_issues=form_issues,
        focusable_elements=focusable,
        notes=notes,
    )
