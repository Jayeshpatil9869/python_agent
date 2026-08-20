"""Performance observational analysis."""

from intelligence.schema import PerformanceData


async def analyze_performance(page, load_metrics: dict | None = None) -> PerformanceData:
    perf = PerformanceData()

    try:
        resources = await page.evaluate(
            """() => performance.getEntriesByType('resource').map(r => ({
                name: r.name,
                type: r.initiatorType,
                // transferSize is 0 for cached/cross-origin; fall back to encoded/decoded
                size: r.transferSize || r.encodedBodySize || r.decodedBodySize || 0,
                transferSize: r.transferSize || 0,
                encodedBodySize: r.encodedBodySize || 0,
                duration: r.duration,
            }))"""
        )
        perf.resource_count = len(resources)

        def _is_js(r: dict) -> bool:
            return r["type"] == "script" or r["name"].split("?")[0].endswith(".js")

        def _is_css(r: dict) -> bool:
            return r["type"] in ("css", "link") or r["name"].split("?")[0].endswith(".css")

        js_bytes = sum(r["size"] for r in resources if _is_js(r))
        css_bytes = sum(r["size"] for r in resources if _is_css(r))
        perf.js_size_kb = round(js_bytes / 1024, 2)
        perf.css_size_kb = round(css_bytes / 1024, 2)

        if perf.js_size_kb == 0 and any(_is_js(r) for r in resources):
            perf.notes.append("JS size unavailable (likely cross-origin cache; transferSize=0)")
        if perf.css_size_kb == 0 and any(_is_css(r) for r in resources):
            perf.notes.append("CSS size unavailable (likely cross-origin cache; transferSize=0)")

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
