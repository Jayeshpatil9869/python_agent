"""Playwright browser management."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from config.settings import AnalysisOptions, Settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser lifecycle."""

    def __init__(self, settings: Settings, options: AnalysisOptions) -> None:
        self.settings = settings
        self.options = options
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        browser_type = getattr(self._playwright, self.options.browser, self._playwright.chromium)
        self._browser = await browser_type.launch(headless=self.options.headless)
        logger.info("Browser launched (%s, headless=%s)", self.options.browser, self.options.headless)

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    @asynccontextmanager
    async def new_context(
        self,
        viewport: tuple[int, int] | None = None,
        user_agent: str | None = None,
    ) -> AsyncIterator[BrowserContext]:
        if not self._browser:
            raise RuntimeError("Browser not started")

        vp = viewport or self.settings.desktop_viewport
        context = await self._browser.new_context(
            viewport={"width": vp[0], "height": vp[1]},
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/New_York",
            device_scale_factor=1,
        )
        context.set_default_timeout(self.options.timeout)
        try:
            yield context
        finally:
            await context.close()

    async def new_page(self, context: BrowserContext) -> Page:
        page = await context.new_page()

        async def _log_console(msg):
            if msg.type == "error":
                logger.debug("Console error on page: %s", msg.text)

        page.on("console", _log_console)
        page.on("pageerror", lambda err: logger.debug("Page error: %s", err))
        return page
