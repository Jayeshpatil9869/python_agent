"""Depth-aware BFS website crawler with SPA/hydration-aware link discovery."""

import logging
from collections import deque
from urllib.parse import urlparse

from playwright.async_api import Page

from config.settings import AnalysisOptions
from crawler.page_loader import load_page
from crawler.sitemap import fetch_sitemap_urls
from crawler.url_utils import normalize_url, same_origin, score_page_importance
from intelligence.schema import CrawlPageRecord

logger = logging.getLogger(__name__)

LINK_DISCOVERY_JS = """
(base) => {
    const out = new Set();
    const add = (raw) => {
        if (!raw) return;
        try {
            const u = new URL(raw, base);
            if (u.protocol !== 'http:' && u.protocol !== 'https:') return;
            // Drop pure hash links that stay on same path
            const path = u.pathname.replace(/\\/$/, '') || '/';
            const basePath = new URL(base).pathname.replace(/\\/$/, '') || '/';
            if (path === basePath && !u.search) return;
            u.hash = '';
            out.add(u.href);
        } catch (e) {}
    };
    document.querySelectorAll('a[href]').forEach(a => add(a.href || a.getAttribute('href')));
    document.querySelectorAll('[data-href], [data-url], [data-link]').forEach(el => {
        add(el.getAttribute('data-href') || el.getAttribute('data-url') || el.getAttribute('data-link'));
    });
    // Next.js / router style
    document.querySelectorAll('[role="link"]').forEach(el => {
        add(el.getAttribute('href') || el.dataset?.href);
    });
    return Array.from(out);
}
"""


async def discover_links_from_page(page: Page, base_url: str) -> list[str]:
    links: set[str] = set()
    try:
        # Wait briefly for SPA hydration / late nav injection
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            await page.wait_for_timeout(800)

        hrefs = await page.evaluate(LINK_DISCOVERY_JS, base_url)
        for href in hrefs:
            normalized = normalize_url(href, base_url)
            if normalized and same_origin(normalized, base_url):
                # Skip identical seed variants
                if _path_key(normalized) == _path_key(base_url) and not urlparse(normalized).query:
                    continue
                links.add(normalized)
    except Exception as exc:
        logger.debug("Link discovery failed: %s", exc)
    return list(links)


def _path_key(url: str) -> str:
    p = urlparse(url)
    return (p.netloc.lower(), (p.path.rstrip("/") or "/").lower())


async def _discover_nav_links(page: Page, base_url: str) -> list[str]:
    selectors = [
        "nav a[href]",
        "header a[href]",
        "footer a[href]",
        "[role='navigation'] a[href]",
        "[class*='nav'] a[href]",
        "[class*='menu'] a[href]",
    ]
    links: set[str] = set()
    for selector in selectors:
        try:
            hrefs = await page.eval_on_selector_all(
                selector,
                "els => els.map(e => e.href || e.getAttribute('href')).filter(Boolean)",
            )
            for href in hrefs:
                normalized = normalize_url(href, base_url)
                if normalized and same_origin(normalized, base_url):
                    if _path_key(normalized) == _path_key(base_url):
                        continue
                    links.add(normalized)
        except Exception:
            continue
    return list(links)


async def crawl_with_depth(page: Page, options: AnalysisOptions) -> list[CrawlPageRecord]:
    """
    BFS crawl respecting --depth and --max-pages.

    depth 0 = seed URL only
    depth 1 = seed + direct links
    depth 2 = seed + links up to 2 hops
    """
    base_url = normalize_url(options.url) or options.url
    max_depth = options.depth
    max_pages = options.max_pages

    seed = CrawlPageRecord(url=base_url, depth=0, parent_url=None, discovery_source="seed", status="pending")
    queue: deque[CrawlPageRecord] = deque([seed])
    visited: set[str] = {base_url}
    queued: set[str] = {base_url}
    results: list[CrawlPageRecord] = []
    failed: set[str] = set()

    sitemap_urls = await fetch_sitemap_urls(base_url, options.same_origin)
    for url in sitemap_urls[: max_pages * 2]:
        if url not in queued and same_origin(url, base_url):
            if max_depth < 1:
                continue
            queued.add(url)
            queue.append(
                CrawlPageRecord(
                    url=url,
                    depth=1,
                    parent_url=base_url,
                    discovery_source="sitemap",
                    status="pending",
                )
            )

    while queue and len(results) < max_pages:
        current = queue.popleft()
        if current.depth > max_depth:
            continue

        try:
            if current.status == "pending":
                await load_page(page, current.url)
                current.status = "success"
        except Exception as exc:
            current.status = "failed"
            failed.add(current.url)
            logger.warning("[CRAWL] failed %s depth=%d: %s", current.url, current.depth, exc)
            results.append(current)
            continue

        results.append(current)
        logger.info("[CRAWL] depth=%d url=%s source=%s", current.depth, current.url, current.discovery_source)

        if current.depth >= max_depth:
            continue

        page_links = await discover_links_from_page(page, base_url)
        nav_links = await _discover_nav_links(page, base_url)
        child_links = set(page_links) | set(nav_links)
        logger.info("[CRAWL] discovered %d child links at depth %d", len(child_links), current.depth)

        for link in sorted(child_links, key=lambda u: (-score_page_importance(u), u)):
            if link in visited or link in queued:
                continue
            if len(results) + len(queue) >= max_pages:
                break
            visited.add(link)
            queued.add(link)
            source = "navigation" if link in nav_links else "link"
            queue.append(
                CrawlPageRecord(
                    url=link,
                    depth=current.depth + 1,
                    parent_url=current.url,
                    discovery_source=source,
                    status="pending",
                )
            )

    results.sort(key=lambda r: (r.depth, -score_page_importance(r.url), r.url))
    return results[:max_pages]


def crawl_depth_summary(records: list[CrawlPageRecord]) -> dict[int, int]:
    summary: dict[int, int] = {}
    for record in records:
        summary[record.depth] = summary.get(record.depth, 0) + 1
    return dict(sorted(summary.items()))
