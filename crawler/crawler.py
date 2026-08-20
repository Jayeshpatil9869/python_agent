"""Website crawling and page discovery."""

import logging
from collections import deque

from bs4 import BeautifulSoup
from playwright.async_api import Page

from config.settings import AnalysisOptions
from crawler.page_loader import load_page
from crawler.sitemap import fetch_sitemap_urls
from crawler.url_utils import normalize_url, same_origin, score_page_importance

logger = logging.getLogger(__name__)


async def discover_links_from_page(page: Page, base_url: str) -> list[str]:
    """Extract internal links from rendered page."""
    links: set[str] = set()

    try:
        hrefs = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
        )
        for href in hrefs:
            normalized = normalize_url(href, base_url)
            if normalized and same_origin(normalized, base_url):
                links.add(normalized)
    except Exception as exc:
        logger.debug("Link discovery failed: %s", exc)

    return list(links)


async def discover_pages(page: Page, options: AnalysisOptions) -> list[str]:
    """Discover important pages to analyze."""
    base_url = options.url
    await load_page(page, base_url)

    discovered: set[str] = {normalize_url(base_url) or base_url}

    page_links = await discover_links_from_page(page, base_url)
    discovered.update(page_links)

    sitemap_links = await fetch_sitemap_urls(base_url, options.same_origin)
    discovered.update(sitemap_links)

    nav_links = await _discover_nav_links(page, base_url)
    discovered.update(nav_links)

    filtered = [u for u in discovered if u and same_origin(u, base_url)]
    ranked = sorted(filtered, key=lambda u: (-score_page_importance(u), u))

    return ranked[: options.max_pages]


async def _discover_nav_links(page: Page, base_url: str) -> list[str]:
    selectors = ["nav a[href]", "header a[href]", "footer a[href]", "[role='navigation'] a[href]"]
    links: set[str] = set()
    for selector in selectors:
        try:
            hrefs = await page.eval_on_selector_all(
                selector,
                "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
            )
            for href in hrefs:
                normalized = normalize_url(href, base_url)
                if normalized and same_origin(normalized, base_url):
                    links.add(normalized)
        except Exception:
            continue
    return list(links)


def extract_links_from_html(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: set[str] = set()
    for tag in soup.find_all("a", href=True):
        normalized = normalize_url(tag["href"], base_url)
        if normalized and same_origin(normalized, base_url):
            links.add(normalized)
    return list(links)
