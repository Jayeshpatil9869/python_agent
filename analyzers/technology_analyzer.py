"""Technology and framework detection with evidence scoring."""

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import TechnologyDetection

# (name, signatures, weights per sig type)
TECH_SIGNATURES: dict[str, list[tuple[str, str, float]]] = {
    "Next.js": [
        ("script", "__NEXT_DATA__", 1.0),
        ("path", "/_next/", 0.9),
        ("global", "__NEXT_DATA__", 1.0),
    ],
    "React": [
        ("global", "React", 0.9),
        ("attr", "data-reactroot", 0.8),
        ("path", "react-dom", 0.7),
    ],
    "Vue": [
        ("global", "Vue", 0.9),
        ("attr", "data-v-", 0.85),
        ("path", "/vue.", 0.7),
    ],
    "Nuxt": [
        ("global", "__NUXT__", 1.0),
        ("path", "/_nuxt/", 0.95),
    ],
    "Angular": [
        ("attr", "ng-version", 1.0),
        ("path", "angular", 0.6),
    ],
    "Svelte": [
        ("attr", "svelte-", 0.9),
    ],
    "Astro": [
        ("attr", "data-astro-cid", 0.95),
    ],
    "WordPress": [
        ("path", "/wp-content/", 0.95),
        ("path", "/wp-includes/", 0.95),
        ("meta", "wordpress", 0.8),
    ],
    "Shopify": [
        ("path", "cdn.shopify.com", 0.95),
        ("global", "Shopify", 0.9),
    ],
    "Webflow": [
        ("meta", "webflow", 0.9),
        ("path", "webflow.io", 0.7),
        ("attr", "data-wf-", 0.85),
    ],
    "GSAP": [
        ("global", "gsap", 0.95),
        ("global", "ScrollTrigger", 0.9),
        ("path", "gsap", 0.8),
    ],
    "Three.js": [
        ("global", "THREE", 0.95),
        ("path", "three", 0.7),
    ],
    "Lenis": [
        ("global", "Lenis", 0.95),
    ],
    "Swiper": [
        ("global", "Swiper", 0.9),
        ("class", "swiper", 0.7),
    ],
    "Framer Motion": [
        ("attr", "data-framer-", 0.9),
        ("path", "framer", 0.6),
    ],
    "Tailwind CSS": [
        ("path", "tailwind", 0.8),
        ("class_score", "tailwind", 0.5),
    ],
    "Bootstrap": [
        ("path", "bootstrap", 0.85),
        ("class_score", "bootstrap", 0.5),
    ],
    "jQuery": [
        ("global", "jQuery", 0.9),
    ],
    "Lottie": [
        ("global", "lottie", 0.9),
        ("path", "lottie", 0.7),
    ],
    "Anime.js": [
        ("global", "anime", 0.85),
    ],
}


def _status_label(confidence: float, has_runtime_global: bool = False) -> str:
    if confidence >= 0.9 and has_runtime_global:
        return "DETECTED"
    if confidence >= 0.9:
        return "HIGH_CONFIDENCE"
    if confidence >= 0.7:
        return "HIGH_CONFIDENCE"
    if confidence >= 0.45:
        return "POSSIBLE"
    return "WEAK"


def _confidence_to_level(confidence: float, status: str) -> ConfidenceLevel:
    if status == "DETECTED":
        return ConfidenceLevel.DETECTED
    if status == "HIGH_CONFIDENCE":
        return ConfidenceLevel.INFERRED
    if status == "POSSIBLE":
        return ConfidenceLevel.ESTIMATED
    return ConfidenceLevel.UNKNOWN


async def analyze_technology(page, html: str) -> list[TechnologyDetection]:
    detections: list[TechnologyDetection] = []
    html_lower = html.lower()

    try:
        resource_urls = await page.evaluate(
            """() => performance.getEntriesByType('resource').map(r => r.name).slice(0, 200)"""
        )
    except Exception:
        resource_urls = []

    try:
        globals_found = await page.evaluate(
            """() => {
                const keys = [
                    'gsap', 'ScrollTrigger', 'THREE', 'Lenis', 'Swiper', 'React', 'Vue',
                    '__NEXT_DATA__', '__NUXT__', 'Shopify', 'lottie', 'anime', 'jQuery'
                ];
                return keys.filter(k => {
                    try { return typeof window[k] !== 'undefined' && window[k] !== null; }
                    catch (e) { return false; }
                });
            }"""
        )
    except Exception:
        globals_found = []

    combined_sources = html_lower + " " + " ".join(resource_urls).lower()

    for name, signatures in TECH_SIGNATURES.items():
        evidence: list[str] = []
        score = 0.0
        has_global = False
        has_strong_marker = False

        for sig_type, sig_value, weight in signatures:
            matched = False
            if sig_type == "global" and sig_value in globals_found:
                evidence.append(f"window.{sig_value}")
                matched = True
                has_global = True
            elif sig_type == "path" and sig_value.lower() in combined_sources:
                evidence.append(f"resource/path:{sig_value}")
                matched = True
            elif sig_type == "script" and sig_value.lower() in html_lower:
                evidence.append(sig_value)
                matched = True
                has_strong_marker = True
            elif sig_type == "meta" and sig_value.lower() in html_lower:
                evidence.append(f"meta:{sig_value}")
                matched = True
                has_strong_marker = True
            elif sig_type == "attr":
                try:
                    found = await page.evaluate(
                        f"() => document.querySelector('[{sig_value}]') !== null"
                    )
                    if found:
                        evidence.append(f"attr:{sig_value}")
                        matched = True
                        has_strong_marker = True
                except Exception:
                    pass
            elif sig_type == "class":
                try:
                    found = await page.evaluate(
                        f"() => document.querySelector('[class*=\"{sig_value}\"]') !== null"
                    )
                    if found:
                        evidence.append(f"class:{sig_value}")
                        matched = True
                except Exception:
                    pass
            elif sig_type == "class_score":
                try:
                    count = await page.evaluate(
                        f"() => document.querySelectorAll('[class*=\"{sig_value}\"]').length"
                    )
                    if count >= 5:
                        evidence.append(f"class_pattern:{sig_value} ({count} elements)")
                        matched = True
                        weight *= min(1.0, count / 20) * 0.5  # weaken generic class patterns
                except Exception:
                    pass

            if matched:
                score += weight

        if not evidence:
            continue

        # Path-only library hits (GSAP/Three without globals) capped as POSSIBLE
        only_path = all(e.startswith("resource/path:") for e in evidence)
        if only_path and not has_global:
            score = min(score, 0.55)

        confidence = min(0.98, score)
        if confidence < 0.45:
            continue

        status = _status_label(confidence, has_runtime_global=has_global or has_strong_marker)
        if only_path and not has_global:
            status = "POSSIBLE"

        detections.append(
            TechnologyDetection(
                name=name,
                status=status,
                confidence=round(confidence, 2),
                confidence_level=_confidence_to_level(confidence, status),
                evidence=evidence,
            )
        )

    return sorted(detections, key=lambda t: t.confidence, reverse=True)
