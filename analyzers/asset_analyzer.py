"""Asset detection."""

from intelligence.schema import AssetRecord


async def analyze_assets(page) -> list[AssetRecord]:
    assets: list[AssetRecord] = []

    try:
        images = await page.evaluate(
            """() => Array.from(document.querySelectorAll('img')).slice(0, 50).map(img => ({
                url: img.currentSrc || img.src,
                width: img.naturalWidth || img.width,
                height: img.naturalHeight || img.height,
                alt: img.alt || '',
                loading: img.loading || '',
                srcset: img.srcset || '',
            }))"""
        )
        for img in images:
            fmt = _detect_format(img.get("url", ""))
            assets.append(
                AssetRecord(
                    url=img.get("url", ""),
                    asset_type="image",
                    format=fmt,
                    width=img.get("width"),
                    height=img.get("height"),
                    alt=img.get("alt", ""),
                    loading=img.get("loading", ""),
                )
            )
    except Exception:
        pass

    try:
        videos = await page.evaluate(
            """() => Array.from(document.querySelectorAll('video, source')).slice(0, 20).map(v => ({
                url: v.src || v.getAttribute('src') || '',
                type: v.tagName.toLowerCase(),
            }))"""
        )
        for vid in videos:
            if vid.get("url"):
                assets.append(
                    AssetRecord(
                        url=vid["url"],
                        asset_type="video",
                        format=_detect_format(vid["url"]),
                    )
                )
    except Exception:
        pass

    try:
        svgs = await page.evaluate("() => document.querySelectorAll('svg').length")
        if svgs:
            assets.append(AssetRecord(url="", asset_type="svg", format="svg"))
    except Exception:
        pass

    return assets


def _detect_format(url: str) -> str:
    url_lower = url.lower().split("?")[0]
    for fmt in ("webp", "avif", "png", "jpg", "jpeg", "gif", "svg", "mp4", "webm"):
        if f".{fmt}" in url_lower:
            return fmt
    return "unknown"
