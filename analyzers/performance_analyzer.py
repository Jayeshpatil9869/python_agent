"""Performance observational analysis."""

from intelligence.schema import PerformanceData


async def analyze_performance(page, load_metrics: dict | None = None) -> PerformanceData:
    perf = PerformanceData()

    try:
        resources = await page.evaluate(
            """() => performance.getEntriesByType('resource').map(r => ({
                name: r.name,
                type: r.initiatorType,
                size: r.transferSize || 0,
                duration: r.duration,
            }))"""
        )
        perf.resource_count = len(resources)
        perf.js_size_kb = round(
            sum(r["size"] for r in resources if r["type"] == "script") / 1024, 2
        )
        perf.css_size_kb = round(
            sum(r["size"] for r in resources if r["type"] == "css" or r["name"].endswith(".css"))
            / 1024,
            2,
        )
        perf.large_images = [
            r["name"]
            for r in resources
            if r["type"] in ("img", "image") and r["size"] > 200_000
        ][:10]
    except Exception:
        perf.notes.append("Resource timing unavailable")

    if load_metrics and load_metrics.get("performance"):
        p = load_metrics["performance"]
        perf.dom_content_loaded_ms = p.get("domContentLoaded")
        perf.load_ms = p.get("load")

    try:
        lazy = await page.evaluate(
            "() => document.querySelectorAll('img[loading=\"lazy\"]').length > 0"
        )
        perf.lazy_loading_detected = bool(lazy)
    except Exception:
        pass

    try:
        preload = await page.evaluate(
            "() => document.querySelectorAll('link[rel=\"preload\"]').length > 0"
        )
        perf.preload_detected = bool(preload)
    except Exception:
        pass

    if perf.dom_content_loaded_ms is None:
        perf.notes.append("Core Web Vitals not measured")

    return perf
