"""Page loading and stabilization."""

import logging

from playwright.async_api import Page

from utils.timing import wait_for_stabilization

logger = logging.getLogger(__name__)


async def load_page(page: Page, url: str, stabilization_ms: int = 1500) -> dict:
    """Navigate to URL and wait for stabilization."""
    metrics: dict = {"url": url, "errors": []}

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        metrics["status"] = response.status if response else None
    except Exception as exc:
        metrics["errors"].append(str(exc))
        logger.warning("Navigation issue for %s: %s", url, exc)

    await wait_for_stabilization(page, stabilization_ms)

    try:
        perf = await page.evaluate(
            """() => {
                const nav = performance.getEntriesByType('navigation')[0];
                return nav ? {
                    domContentLoaded: nav.domContentLoadedEventEnd,
                    load: nav.loadEventEnd,
                } : {};
            }"""
        )
        metrics["performance"] = perf
    except Exception:
        metrics["performance"] = {}

    return metrics
