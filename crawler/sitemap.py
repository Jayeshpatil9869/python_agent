"""Sitemap discovery."""

import logging
from xml.etree import ElementTree

import httpx

from crawler.url_utils import normalize_url, same_origin

logger = logging.getLogger(__name__)


async def fetch_sitemap_urls(base_url: str, same_origin_only: bool = True) -> list[str]:
    """Fetch URLs from sitemap.xml if available."""
    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
    urls: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(sitemap_url)
            if response.status_code != 200:
                return urls

            root = ElementTree.fromstring(response.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            for loc in root.findall(".//sm:loc", ns):
                if loc.text:
                    normalized = normalize_url(loc.text.strip())
                    if normalized and (not same_origin_only or same_origin(normalized, base_url)):
                        urls.append(normalized)

            if not urls:
                for loc in root.findall(".//loc"):
                    if loc.text:
                        normalized = normalize_url(loc.text.strip())
                        if normalized and (not same_origin_only or same_origin(normalized, base_url)):
                            urls.append(normalized)

    except Exception as exc:
        logger.debug("Sitemap fetch failed: %s", exc)

    return urls
